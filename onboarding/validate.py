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


VALIDATORS = {
    "dataforseo": validate_dataforseo,
    "google-api": validate_google_api,
    "firecrawl": validate_firecrawl,
    "exa": validate_exa,
}


def validate(provider_id: str, cfg: dict) -> dict:
    fn = VALIDATORS.get(provider_id)
    if not fn:
        return {"ok": False, "detail": "no validator for provider", "warn": None}
    return fn(cfg)
