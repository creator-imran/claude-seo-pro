"""
validate.py - cheap, live connectivity checks for each onboarded provider.

Each validator returns: {"ok": bool, "detail": str, "warn": str|None}
  ok    -> credentials authenticated successfully
  detail-> human-readable result (balance, credit count, or the error)
  warn  -> non-fatal caveat to surface (e.g. DataForSEO IP whitelist)

Stdlib-only (urllib). Validators are designed to consume zero or near-zero
provider credits: they hit status/auth endpoints, or craft a request that the
provider rejects for a reason that still proves the key is valid.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

TIMEOUT = 25


def _request(url, *, method="GET", headers=None, data=None):
    """Return (status_code, parsed_json_or_text). Never raises on HTTP error."""
    req = urllib.request.Request(url, method=method, headers=headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=body, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw
    except Exception as e:  # DNS, timeout, TLS, offline
        return None, str(e)


def validate_dataforseo(cfg: dict) -> dict:
    user, pw = cfg.get("username", ""), cfg.get("password", "")
    if not user or not pw:
        return {"ok": False, "detail": "username/password missing", "warn": None}
    token = base64.b64encode(f"{user}:{pw}".encode()).decode()
    status, body = _request(
        "https://api.dataforseo.com/v3/appendix/user_data",
        headers={"Authorization": f"Basic {token}"},
    )
    if status is None:
        return {"ok": False, "detail": f"network error: {body}", "warn": None}
    if status == 401:
        return {"ok": False, "detail": "invalid credentials (HTTP 401)", "warn": None}
    if not (isinstance(body, dict) and body.get("status_code") == 20000):
        msg = body.get("status_message") if isinstance(body, dict) else str(body)
        return {"ok": False, "detail": f"auth failed: {msg}", "warn": None}

    # HTTP 200 + top-level 20000 => the Basic-auth credentials were accepted.
    # But DataForSEO reports IP-whitelist denial at the TASK level, not the top level,
    # so we MUST inspect tasks[0].status_code (checking only the top level is a
    # false-positive trap).
    task = (body.get("tasks") or [{}])[0]
    tstatus = task.get("status_code")
    if tstatus == 20000:
        try:
            result = task["result"]
            if isinstance(result, list):
                result = result[0]
            bal = result["money"]["balance"]
        except Exception:
            bal = "?"
        return {"ok": True, "detail": f"authenticated, balance ${bal}", "warn": None}
    if tstatus == 40207:
        # Credentials are valid; only the IP is blocked. Storing the key is correct -
        # the manager fixes the whitelist in the panel.
        return {
            "ok": True,
            "detail": "credentials valid, but data is blocked: IP not whitelisted (40207)",
            "warn": ("Add this machine's public IP at https://app.dataforseo.com/api-access "
                     "(or disable the whitelist). Until then, every DataForSEO data call fails."),
        }
    return {"ok": False, "detail": f"task error: {task.get('status_message', tstatus)}", "warn": None}


def validate_google_api(cfg: dict) -> dict:
    key = cfg.get("api_key", "")
    if not key:
        return {"ok": False, "detail": "api_key missing", "warn": None}
    # Call PSI WITHOUT a url. A valid key -> 400 'required parameter: url'.
    # An invalid key -> 400 reason 'keyInvalid' / 'API_KEY_INVALID'. This proves the
    # key without paying for a full Lighthouse run.
    status, body = _request(
        f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?key={key}"
    )
    reason = ""
    if isinstance(body, dict):
        err = body.get("error", {})
        errs = err.get("errors") or []
        if errs:
            reason = (errs[0].get("reason") or "").lower()
        reason = reason or (err.get("status") or "").lower()
    bad = {"keyinvalid", "api_key_invalid", "forbidden", "permission_denied"}
    if reason in bad or "api key not valid" in str(body).lower():
        return {"ok": False, "detail": f"invalid API key ({reason or 'rejected'})", "warn": None}
    if status in (400, 200):
        return {
            "ok": True,
            "detail": "API key accepted by PageSpeed Insights",
            "warn": "Confirm 'PageSpeed Insights API' + 'Chrome UX Report API' are enabled on the key's project.",
        }
    return {"ok": False, "detail": f"unexpected response (HTTP {status})", "warn": None}


def validate_firecrawl(cfg: dict) -> dict:
    key = cfg.get("api_key", "")
    if not key:
        return {"ok": False, "detail": "api_key missing", "warn": None}
    status, body = _request(
        "https://api.firecrawl.dev/v1/team/credit-usage",
        headers={"Authorization": f"Bearer {key}"},
    )
    if status is None:
        return {"ok": False, "detail": f"network error: {body}", "warn": None}
    if status == 200:
        credits = ""
        if isinstance(body, dict):
            credits = body.get("data", {}).get("remaining_credits", body.get("remaining_credits", ""))
        return {"ok": True, "detail": f"authenticated{(', credits: ' + str(credits)) if credits != '' else ''}", "warn": None}
    if status in (401, 403):
        return {"ok": False, "detail": "invalid API key", "warn": None}
    # Endpoint shape can change; treat other 2xx-ish as ok with a note.
    return {"ok": False, "detail": f"unexpected response (HTTP {status})", "warn": None}


def validate_exa(cfg: dict) -> dict:
    key = cfg.get("api_key", "")
    if not key:
        return {"ok": False, "detail": "api_key missing", "warn": None}
    status, body = _request(
        "https://api.exa.ai/search",
        method="POST",
        headers={"x-api-key": key},
        data={"query": "claude seo connectivity test", "numResults": 1},
    )
    if status is None:
        return {"ok": False, "detail": f"network error: {body}", "warn": None}
    if status == 200:
        return {"ok": True, "detail": "authenticated", "warn": None}
    if status in (401, 403):
        return {"ok": False, "detail": "invalid API key", "warn": None}
    return {"ok": False, "detail": f"unexpected response (HTTP {status})", "warn": None}


def validate_google_oauth(cfg: dict) -> dict:
    """OAuth can't be completed headlessly here. Validate setup readiness instead:
    a usable client_secret.json (or an already-minted token), without doing the
    browser dance. Honest about what's left to do."""
    import os
    token = os.path.expanduser("~/.config/claude-seo/oauth-token.json")
    if os.path.exists(token):
        return {"ok": True, "detail": "OAuth token present (GSC/GA4 ready)", "warn": None}
    path = (cfg.get("client_secret_path") or "").strip()
    if not path:
        return {"ok": True, "detail": "recorded; attach later (run the OAuth auth step to finish)",
                "warn": "No token yet. Run the auth_cmd to mint one before GSC/GA4 sections work."}
    if not os.path.exists(os.path.expanduser(path)):
        return {"ok": False, "detail": f"client_secret.json not found at {path}", "warn": None}
    return {"ok": True, "detail": "client_secret found; run the auth step to mint the token",
            "warn": "Validation here is filesystem-only (no browser OAuth in headless mode)."}


def validate_gbp(cfg: dict) -> dict:
    """Same model as google_oauth, for the GBP business.manage token."""
    import os
    token = os.path.expanduser("~/.config/claude-seo/gbp-token.json")
    if os.path.exists(token):
        return {"ok": True, "detail": "GBP OAuth token present (first-party insights ready)", "warn": None}
    path = (cfg.get("client_secret_path") or "").strip()
    if not path:
        return {"ok": True, "detail": "recorded; attach later (or rely on DataForSEO fallback)",
                "warn": "No GBP token. Local SEO will use the DataForSEO (seo-maps) fallback until you complete OAuth."}
    if not os.path.exists(os.path.expanduser(path)):
        return {"ok": False, "detail": f"client_secret.json not found at {path}", "warn": None}
    return {"ok": True, "detail": "client_secret found; run the GBP auth step to mint the token",
            "warn": "Owner/manager access to the business location is required for this to return data."}


def validate_slack(cfg: dict) -> dict:
    """Optionally confirm the bot token via Slack auth.test; always sanity-check formats."""
    secret = (cfg.get("signing_secret") or "").strip()
    token = (cfg.get("bot_token") or "").strip()
    if not secret:
        return {"ok": False, "detail": "signing_secret missing", "warn": None}
    warn = None if token.startswith("xoxb-") else "bot token should start with 'xoxb-'"
    if not token:
        return {"ok": True, "detail": "signing secret stored (no bot token — delayed replies via response_url only)",
                "warn": "Add a bot token if you want richer chat.postMessage replies."}
    status, body = _request("https://slack.com/api/auth.test", method="POST",
                            headers={"Authorization": f"Bearer {token}",
                                     "Content-Type": "application/x-www-form-urlencoded"})
    if isinstance(body, dict) and body.get("ok"):
        return {"ok": True, "detail": f"bot token valid (team: {body.get('team', '?')})", "warn": warn}
    if isinstance(body, dict) and body.get("error"):
        return {"ok": False, "detail": f"bot token rejected: {body['error']}", "warn": None}
    # network/other — store anyway; signing secret is what the webhook needs
    return {"ok": True, "detail": "stored (could not reach Slack to verify bot token)",
            "warn": warn or "bot token unverified (network)"}


def validate_openrouter(cfg: dict) -> dict:
    """Validate the key via OpenRouter's free key-info endpoint (no token spend).
    On success, surface remaining credit - useful signal for the fallback use case."""
    key = (cfg.get("api_key") or "").strip()
    if not key:
        return {"ok": False, "detail": "api_key missing", "warn": None}
    warn = None if key.startswith("sk-or-") else "key usually starts with 'sk-or-'"
    status, body = _request(
        "https://openrouter.ai/api/v1/key",
        headers={"Authorization": f"Bearer {key}"},
    )
    if status is None:
        return {"ok": True, "detail": "stored (could not reach OpenRouter to verify)",
                "warn": warn or f"unverified (network: {body})"}
    if status == 200 and isinstance(body, dict):
        data = body.get("data", {}) if isinstance(body.get("data"), dict) else {}
        usage, limit = data.get("usage"), data.get("limit")
        credit = f"used ${usage:.2f}" if isinstance(usage, (int, float)) else "usage n/a"
        if isinstance(limit, (int, float)):
            credit += f" of ${limit:.2f} limit"
        return {"ok": True, "detail": f"authenticated ({credit})", "warn": warn}
    if status in (401, 403):
        return {"ok": False, "detail": "invalid API key", "warn": None}
    return {"ok": False, "detail": f"unexpected response (HTTP {status})", "warn": None}


VALIDATORS = {
    "dataforseo": validate_dataforseo,
    "google-api": validate_google_api,
    "google-oauth": validate_google_oauth,
    "gbp": validate_gbp,
    "firecrawl": validate_firecrawl,
    "exa": validate_exa,
    "openrouter": validate_openrouter,
    "slack": validate_slack,
}


def validate(provider_id: str, cfg: dict) -> dict:
    fn = VALIDATORS.get(provider_id)
    if not fn:
        return {"ok": False, "detail": "no validator for provider", "warn": None}
    return fn(cfg)
