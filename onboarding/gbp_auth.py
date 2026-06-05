#!/usr/bin/env python3
"""
gbp_auth.py - Google Business Profile (first-party) OAuth + insights for Claude SEO Pro.

The GBP APIs require the OAuth scope https://www.googleapis.com/auth/business.manage
and the authenticating user must have access (owner/manager) to the business location.
Upstream's google_auth.py covers GSC/GA4/Indexing scopes but NOT business.manage, so
this owned module handles GBP separately. Token is stored at
~/.config/claude-seo/gbp-token.json (0600).

Modes:
  python gbp_auth.py --auth --creds client_secret.json   # one-time browser OAuth
  python gbp_auth.py --check [--json]                     # is GBP wired up?
  python gbp_auth.py --performance --location locations/123 [--days 30]

Capabilities used:
  * Account/location discovery  -> mybusinessaccountmanagement / mybusinessbusinessinformation
  * Performance metrics         -> businessprofileperformance.googleapis.com
                                   (searches, views, calls, direction requests, bookings)

Falls back gracefully: if GBP is not configured, the local SEO audit uses the
DataForSEO path (the seo-maps skill) on public GBP/map-pack data instead. This module
never fabricates metrics — if the token or access is missing, it says so.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

try:
    from . import secure_store
except ImportError:
    import secure_store

TOKEN_PATH = os.path.expanduser("~/.config/claude-seo/gbp-token.json")
SCOPE = "https://www.googleapis.com/auth/business.manage"
REDIRECT_URI = "http://localhost:8086"


# ---------- auth ----------

def run_auth(client_secret_path: str) -> int:
    """Run the installed-app OAuth flow and persist the refresh token."""
    path = os.path.expanduser(client_secret_path)
    if not os.path.exists(path):
        print(f"[x] client_secret.json not found: {path}")
        return 1
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("[x] google-auth-oauthlib not installed. Run: pip install google-auth-oauthlib")
        return 1
    flow = InstalledAppFlow.from_client_secrets_file(path, scopes=[SCOPE], redirect_uri=REDIRECT_URI)
    creds = flow.run_local_server(port=8086, prompt="consent")
    data = {
        "refresh_token": creds.refresh_token,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "token_uri": creds.token_uri,
        "scopes": list(creds.scopes or [SCOPE]),
    }
    secure_store.save("gbp-token", data)  # 0600
    # also remember the client_secret path in the gbp config for re-auth
    secure_store.merge("gbp", {"client_secret_path": client_secret_path})
    secure_store.clear_pending("gbp")
    print(f"[+] GBP OAuth complete. Token stored at {TOKEN_PATH}")
    return 0


def _access_token() -> str | None:
    """Exchange the stored refresh token for an access token. None if not set up."""
    tok = secure_store.load("gbp-token")
    if not tok.get("refresh_token"):
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        print("[x] google-auth not installed. Run: pip install google-auth", file=sys.stderr)
        return None
    creds = Credentials(
        None,
        refresh_token=tok["refresh_token"],
        client_id=tok.get("client_id"),
        client_secret=tok.get("client_secret"),
        token_uri=tok.get("token_uri", "https://oauth2.googleapis.com/token"),
        scopes=tok.get("scopes", [SCOPE]),
    )
    creds.refresh(Request())
    return creds.token


# ---------- checks / data ----------

def check(as_json: bool = False) -> int:
    tok = secure_store.load("gbp-token")
    gbp_cfg = secure_store.load("gbp")
    state = {
        "configured": bool(tok.get("refresh_token")),
        "token_path": TOKEN_PATH if os.path.exists(TOKEN_PATH) else None,
        "location": gbp_cfg.get("location"),
        "fallback": "DataForSEO (seo-maps) public GBP/map-pack data" if not tok.get("refresh_token") else None,
    }
    if as_json:
        print(json.dumps(state, indent=2))
    else:
        if state["configured"]:
            print(f"[+] GBP configured. Location: {state['location'] or '(not set)'}")
        else:
            print("[!] GBP not configured. Local SEO will use the DataForSEO fallback (seo-maps).")
            print("    Set up: python gbp_auth.py --auth --creds <client_secret.json>")
    return 0 if state["configured"] else 2


def performance(location: str, days: int = 30) -> int:
    """Fetch first-party GBP performance metrics. Honest failure if not set up."""
    import urllib.request
    import urllib.error
    import datetime

    token = _access_token()
    if not token:
        print(json.dumps({"error": "GBP not configured",
                          "fallback": "run the seo-maps skill (DataForSEO) for public GBP/map-pack data"}, indent=2))
        return 2
    loc = location or secure_store.load("gbp").get("location")
    if not loc:
        print(json.dumps({"error": "no location set; pass --location locations/<id>"}, indent=2))
        return 1

    end = datetime.date.today()
    start = end - datetime.timedelta(days=days)
    metrics = [
        "BUSINESS_IMPRESSIONS_DESKTOP_SEARCH", "BUSINESS_IMPRESSIONS_MOBILE_SEARCH",
        "BUSINESS_IMPRESSIONS_DESKTOP_MAPS", "BUSINESS_IMPRESSIONS_MOBILE_MAPS",
        "CALL_CLICKS", "WEBSITE_CLICKS", "BUSINESS_DIRECTION_REQUESTS", "BUSINESS_BOOKINGS",
    ]
    base = f"https://businessprofileperformance.googleapis.com/v1/{loc}:fetchMultiDailyMetricsTimeSeries"
    q = "&".join([f"dailyMetrics={m}" for m in metrics] + [
        f"dailyRange.start_date.year={start.year}", f"dailyRange.start_date.month={start.month}",
        f"dailyRange.start_date.day={start.day}", f"dailyRange.end_date.year={end.year}",
        f"dailyRange.end_date.month={end.month}", f"dailyRange.end_date.day={end.day}",
    ])
    req = urllib.request.Request(f"{base}?{q}", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        print(json.dumps({"error": f"HTTP {e.code}", "detail": body[:500],
                          "hint": "403 usually means the OAuth account lacks access to this location."}, indent=2))
        return 1
    print(json.dumps(data, indent=2))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Google Business Profile OAuth + insights")
    ap.add_argument("--auth", action="store_true")
    ap.add_argument("--creds", help="path to GBP OAuth client_secret.json")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--performance", action="store_true")
    ap.add_argument("--location", help="locations/<id>")
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args(argv)

    if args.auth:
        if not args.creds:
            print("[x] --auth requires --creds <client_secret.json>")
            return 1
        return run_auth(args.creds)
    if args.performance:
        return performance(args.location, args.days)
    return check(as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
