"""
auth.py - request authentication + authorization for the chat connector.

Two independent gates, both required before any audit runs:
  1. verify_slack_signature() - proves the request really came from Slack (HMAC-SHA256
     over the raw body with your signing secret) and isn't a replay (timestamp window).
  2. is_authorized() - proves the human who triggered it is on the allow-list, so not
     anyone in a workspace can spend your DataForSEO / model credits.

Slack signing spec (v0):
  basestring = "v0:" + X-Slack-Request-Timestamp + ":" + raw_request_body
  expected   = "v0=" + hex(hmac_sha256(signing_secret, basestring))
  compare to X-Slack-Signature with a constant-time compare.

Stdlib only — fully unit-testable offline (no network).
"""

from __future__ import annotations

import hashlib
import hmac
import time


def verify_slack_signature(signing_secret: str, timestamp, body: str, signature: str,
                           max_age_seconds: int = 300, now: float = None) -> tuple:
    """Return (ok, reason). ok=False with a reason on any failure."""
    if not signing_secret:
        return False, "no signing secret configured"
    if not signature or not timestamp:
        return False, "missing signature or timestamp header"
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False, "bad timestamp"
    now = time.time() if now is None else now
    if abs(now - ts) > max_age_seconds:
        return False, "stale request (replay window exceeded)"
    base = f"v0:{ts}:{body}".encode("utf-8")
    expected = "v0=" + hmac.new(signing_secret.encode("utf-8"), base, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False, "signature mismatch"
    return True, "ok"


def is_authorized(user_id: str, channel_id: str, allowed_users, allowed_channels) -> tuple:
    """Deny-by-default: if BOTH allow-lists are empty, nobody is authorized."""
    allowed_users = allowed_users or []
    allowed_channels = allowed_channels or []
    if not allowed_users and not allowed_channels:
        return False, "no allow-list configured — add allowed_users/allowed_channels in connector.json"
    if user_id and user_id in allowed_users:
        return True, "user allow-listed"
    if channel_id and channel_id in allowed_channels:
        return True, "channel allow-listed"
    return False, "user/channel not on the allow-list"
