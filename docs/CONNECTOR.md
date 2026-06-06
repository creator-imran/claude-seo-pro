# Chat Connector — deployment guide (Feature 4)

Run SEO audits from **Slack** (and, later, WhatsApp) instead of the terminal. The
connector is a small, self-contained webhook service that reuses the same `/seo` skills.

> **Architecture (why it's built this way).** Chat platforms can't "drive the interactive
> CLI." The connector runs the SEO system **headlessly** via Claude Code's non-interactive
> print mode (`claude -p "<prompt>"`), so it executes the exact same skills a manager uses
> in the terminal — no agent loop reimplemented, no SDK signatures guessed. The runner is
> transport-agnostic; Slack is the first adapter, WhatsApp can reuse it.

```
Slack slash command  ──HTTPS──▶  connector (slack_bridge.py)
  /seo audit x.com                 1. verify Slack HMAC signature  (auth.py)
                                   2. parse + validate command     (commands.py)
                                   3. authorize user/channel       (auth.py, deny-by-default)
                                   4. ACK < 3s (ephemeral "running…")
                                   5. background: claude -p "<prompt>"   (runner.py)
                                   6. POST result to response_url   ──▶  back to Slack
```

## Prerequisites
- A host that **Slack can reach over HTTPS**, where **Claude Code is installed** and your
  **API key / credentials** live (the headless run uses them).
- Python 3.10+ (the connector is stdlib-only).
- Onboarded providers you want the audits to use (DataForSEO, Google, etc.).

## 1. Create the Slack app
1. https://api.slack.com/apps → **Create New App** → From scratch.
2. **Slash Commands** → Create `/seo`; Request URL = `https://<your-host>/slack`.
3. **OAuth & Permissions** → add bot scopes `commands` and `chat:write`; install to the
   workspace; copy the **Bot User OAuth Token** (`xoxb-…`).
4. **Basic Information** → copy the **Signing Secret**.

## 2. Store the Slack credentials (owner-only, never in repo)
```
python ~/.claude/skills/seo/onboarding/setup_wizard.py --provider slack
```
Writes `~/.config/claude-seo/slack.json` (`signing_secret`, `bot_token`), `0600`.

## 3. Configure operation + authorization
Create `~/.config/claude-seo/connector.json`:
```json
{
  "run_backend": "claude-cli",
  "claude_bin": "claude",
  "model": null,
  "permission_mode": "acceptEdits",
  "enabled_commands": ["audit", "page", "schema", "geo", "local", "keyword"],
  "allowed_users": ["U01ABCDEF"],
  "allowed_channels": ["C01GHIJK"],
  "timeout_seconds": 1800,
  "max_concurrent": 2
}
```
> **Deny-by-default:** with both allow-lists empty, **no one** is authorized. Add the
> Slack user IDs and/or channel IDs that may trigger runs (audits cost credits). Find a
> user ID via the Slack profile "Copy member ID".

## 4. Run it
```
python ~/.claude/skills/seo/connector/slack_bridge.py --port 8088
```
Expose it over HTTPS (reverse proxy like nginx/Caddy, or a tunnel like cloudflared/ngrok
for testing) and point the slash command's Request URL at `https://<host>/slack`.

Verify the security logic offline anytime:
```
python ~/.claude/skills/seo/connector/slack_bridge.py --selftest
```

## Usage in Slack
```
/seo audit https://client.com
/seo page https://client.com/pricing
/seo schema https://client.com
/seo local https://client.com
/seo recall client.com          # what the knowledge store knows
```
The connector acks immediately and posts the finished result to the channel.

## Security model
- **Authenticity:** Slack HMAC-SHA256 signature verified on every request (`v0:ts:body`),
  with a 5-minute replay window. Forged/stale requests → 401.
- **Authorization:** deny-by-default allow-list of users/channels.
- **Secrets stay host-side:** API keys live under `~/.config/claude-seo/`; they are never
  sent to Slack and never placed in the run prompt.
- **Command surface is fixed:** only `enabled_commands` run; targets are validated as
  URLs/domains; unknown actions are rejected.
- **Permission posture:** the headless run uses `permission_mode` (default `acceptEdits`).
  Use `bypassPermissions` only if you fully trust the fixed command surface.

## Cost control
Each audit consumes model + (optionally) DataForSEO credits. Keep the allow-list tight,
set a sane `timeout_seconds`, and consider routing audits to a cheaper model tier via the
Feature-3 router (`/seo-models`) when cost matters more than depth.

## What's validated vs. what you must test in your environment
- **Unit-tested here (offline):** Slack signature verification (good/tampered/stale),
  command parsing/validation, deny-by-default authorization, and the headless command
  construction (`runner.build_cli_command` / `plan`).
- **You must validate in your deployment (needs a real Slack app + Claude Code + network):**
  the end-to-end round-trip — Slack delivering to your HTTPS endpoint and the live
  `claude -p` run. Use a tunnel + the `/seo recall` command (cheap, no external API) as a
  first smoke test before running a full audit.

## WhatsApp (future adapter)
The runner (`connector/runner.py`) is transport-agnostic. A WhatsApp adapter via the
**WhatsApp Business API (Meta)** or **Twilio** would: receive the inbound message webhook,
verify it, map text → `commands.parse_command`, authorize, call `runner.run`, and reply via
the provider's send API. It's heavier than Slack (business verification, a phone number,
per-message cost), so Slack is the supported first transport.
