#!/usr/bin/env python3
"""
slack_bridge.py - the Slack webhook for the Claude SEO Pro connector (Feature 4).

Flow for an incoming Slack slash command (`/seo audit https://x.com`):
  1. Verify the Slack signature (auth.verify_slack_signature) — reject forgeries/replays.
  2. Parse + validate the command (commands.parse_command) against enabled_commands.
  3. Authorize the user/channel (auth.is_authorized) — deny-by-default.
  4. ACK within Slack's 3s window with an ephemeral "working on it" message.
  5. Run the headless SEO task in the background and POST the result to `response_url`
     (or via chat.postMessage with the bot token) — audits take minutes, so this is async.

`handle_slash()` is a PURE function — (headers, raw_body) -> (http_status, json_ack,
job|None) — so the entire decision path (verify → parse → authorize → ack) is
unit-testable WITHOUT binding a socket or talking to Slack. The HTTP server and the
background worker are thin wrappers around it.

Run:  python slack_bridge.py --port 8088        (serve)
      python slack_bridge.py --selftest          (offline logic check)

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import threading
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    from . import auth, commands, config, runner
except ImportError:
    import auth, commands, config, runner


def _ack(text: str) -> dict:
    return {"response_type": "ephemeral", "text": text}


def handle_slash(headers: dict, raw_body: str, now: float = None) -> tuple:
    """Pure decision path. Returns (status, ack_json, job_or_None).
    `job` (when present) = {"parsed":..., "response_url":...} for the worker to run."""
    sc = config.slack_creds()
    cfg = config.connector()

    sig = headers.get("X-Slack-Signature") or headers.get("x-slack-signature")
    ts = headers.get("X-Slack-Request-Timestamp") or headers.get("x-slack-request-timestamp")
    ok, reason = auth.verify_slack_signature(sc["signing_secret"], ts, raw_body, sig, now=now)
    if not ok:
        return 401, _ack(f"unauthorized: {reason}"), None

    form = {k: v[0] for k, v in urllib.parse.parse_qs(raw_body).items()}
    text = form.get("text", "")
    user_id, channel_id = form.get("user_id", ""), form.get("channel_id", "")
    response_url = form.get("response_url", "")

    parsed, err = commands.parse_command(text, enabled=cfg.get("enabled_commands"))
    if err:
        return 200, _ack(f":warning: {err}"), None

    authed, areason = auth.is_authorized(user_id, channel_id, cfg.get("allowed_users"),
                                         cfg.get("allowed_channels"))
    if not authed:
        return 200, _ack(f":lock: not authorized: {areason}"), None

    job = {"parsed": parsed, "response_url": response_url}
    return 200, _ack(f":hourglass_flowing_sand: Running *{parsed['action']}* on "
                     f"`{parsed['target']}` — I'll post the result here shortly."), job


def _post_response(response_url: str, text: str) -> None:
    if not response_url:
        return
    data = json.dumps({"response_type": "in_channel", "text": text}).encode("utf-8")
    req = urllib.request.Request(response_url, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception:
        pass  # delayed-response delivery is best-effort


def run_job(job: dict, dry_run: bool = False) -> None:
    """Background worker: run the headless task and deliver the result to Slack."""
    parsed = job["parsed"]
    result = runner.run(parsed, dry_run=dry_run)
    _post_response(job["response_url"], runner.format_for_chat(result, parsed))


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        headers = {k: v for k, v in self.headers.items()}
        status, ack, job = handle_slash(headers, body)
        payload = json.dumps(ack).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
        if job:
            threading.Thread(target=run_job, args=(job,), daemon=True).start()

    def log_message(self, *args):
        pass  # quiet


def selftest() -> int:
    """Offline logic check — no socket, no Slack, no network."""
    import auth as A
    secret = "test-signing-secret"
    body = "command=%2Fseo&text=audit+https%3A%2F%2Fexample.com&user_id=U1&channel_id=C1&response_url=https%3A%2F%2Fhooks.slack.test%2Fx"
    import time as _t
    ts = str(int(_t.time()))
    base = f"v0:{ts}:{body}".encode()
    import hmac, hashlib
    good_sig = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    print("signature verify (good):", A.verify_slack_signature(secret, ts, body, good_sig))
    print("signature verify (tampered):", A.verify_slack_signature(secret, ts, body, good_sig[:-1] + "0"))
    print("signature verify (stale):", A.verify_slack_signature(secret, "1", body, good_sig))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Claude SEO Pro Slack connector")
    ap.add_argument("--port", type=int, default=8088)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    cfg = config.is_configured()
    if not cfg["slack_signing_secret"]:
        print("[!] No Slack signing secret configured. Run onboarding (`slack` provider) first.")
    print(f"[i] Claude SEO Pro connector listening on :{args.port}/slack")
    HTTPServer(("0.0.0.0", args.port), _Handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
