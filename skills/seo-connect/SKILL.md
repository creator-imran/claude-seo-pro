---
name: seo-connect
description: "Set up and operate the chat connector — run SEO audits from Slack (and later WhatsApp) instead of the terminal. Use when the user says Slack, chat connector, run from Slack, slash command, WhatsApp, or /seo-connect. The connector is a separate service; this skill helps configure and check it."
user-invokable: true
argument-hint: "[status|setup|test]"
license: MIT
metadata:
  author: creator-imran
  version: "1.0.0"
  category: seo
---

# Chat Connector (Slack → headless SEO)

Lets a manager who isn't comfortable in the terminal run audits from **Slack**:
`/seo audit https://client.com` → the connector verifies it's really from Slack,
checks the user is allow-listed, runs the audit **headlessly** (reusing the same `/seo`
skills via `claude -p`), and posts the result back to the channel.

It is a **separate service** (a small webhook server), not something that runs inside a
Claude session. Engine: `~/.claude/skills/seo/connector/`. Full deployment guide:
`docs/CONNECTOR.md`.

## `status` — is it configured?
```
! python ~/.claude/skills/seo/connector/config.py
```
Reports whether the Slack signing secret + bot token are present, whether an
authorization allow-list is set (deny-by-default until it is), and which commands are enabled.

## `setup` — wire it up (one-time)
Walk the user through these (details in `docs/CONNECTOR.md`):
1. **Create a Slack app** at https://api.slack.com/apps; add a `/seo` **slash command**
   whose Request URL is your connector's public `…/slack` endpoint.
2. **Onboard the Slack credentials** (stored owner-only, never in the repo):
   `! python ~/.claude/skills/seo/onboarding/setup_wizard.py --provider slack`
   (enter the app Signing Secret + Bot Token).
3. **Allow-list who can trigger runs** — edit `~/.config/claude-seo/connector.json`:
   `{"allowed_users": ["U…"], "allowed_channels": ["C…"], "enabled_commands": ["audit","page","schema","local","keyword"]}`
   Until this is set, **nobody** is authorized (audits cost credits — deny by default).
4. **Run the connector** on a host Slack can reach (and where Claude Code + your API key
   live): `python ~/.claude/skills/seo/connector/slack_bridge.py --port 8088`
   Put it behind HTTPS (reverse proxy / tunnel) and point the slash command at it.

## `test` — verify the logic without Slack
```
! python ~/.claude/skills/seo/connector/slack_bridge.py --selftest
```
Confirms signature verification (good / tampered / stale) offline. To preview what a
command *would* run without executing: the runner has a `dry_run`/`plan` path
(see `docs/CONNECTOR.md`).

## How it stays safe
- **Authenticity:** every request is HMAC-verified against the Slack signing secret;
  replays outside a 5-minute window are rejected.
- **Authorization:** deny-by-default; only allow-listed users/channels can trigger runs.
- **Secrets stay host-side:** API keys live in `~/.config/claude-seo/`, never sent to
  Slack or exposed to the run.
- **Async:** audits take minutes — the connector acks immediately, then posts the result
  to the command's `response_url`.

## WhatsApp
The runner is transport-agnostic. A WhatsApp adapter (via WhatsApp Business API / Twilio)
can reuse `connector/runner.py` — it's the heavier path (Meta approval, a number), so
Slack is the supported first transport. See `docs/CONNECTOR.md` → WhatsApp.
