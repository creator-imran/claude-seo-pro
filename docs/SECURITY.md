# Security Model

How Claude SEO Pro handles the SEO manager's API credentials.

## Where secrets live

| Location | Contents | Permissions | In repo? |
|---|---|---|---|
| `~/.config/claude-seo/<provider>.json` | The API keys you onboard | `0600` (POSIX) / owner-only ACL (Windows) | No — gitignored, and outside the repo tree |
| `~/.claude/settings.json` | MCP server env (DataForSEO/Firecrawl/Exa keys are read by Claude Code from here) | restricted to owner by the wizard | No |
| `~/.claude/settings.json.claude-seo.bak` | One-time backup before the wizard's first change | owner | No |

Nothing else stores credentials. The repository never contains keys; `.gitignore`
additionally blocks `*-api.json`, `.env`, and provider config filenames as a
safety net in case a file is dropped in the working tree.

## Permission hardening

`onboarding/secure_store.py` enforces owner-only access on every write:
- **POSIX:** `os.chmod(path, 0o600)` for files, `0o700` for the config dir.
- **Windows:** `chmod` can't express NTFS ACLs, so it runs
  `icacls <path> /inheritance:r /grant:r <user>:F` to remove inheritance and
  grant only the current user.
- `setup_wizard.py --check` reports `PERMS TOO OPEN` if a file is group/other
  readable (POSIX), so drift is visible.

## Secrets never touch the chat transcript

The `/seo-setup` skill is explicitly instructed **not** to ask for or echo raw
key values. Secret entry happens in the user's terminal via `getpass` (masked).
If a user pastes a key into chat anyway, the skill warns them it is now in the
transcript and recommends rotation.

## What leaves the machine

Only calls to each provider's own API endpoint:
- DataForSEO → `api.dataforseo.com`
- Google → `googleapis.com`
- Firecrawl → `api.firecrawl.dev`
- Exa → `api.exa.ai`

No telemetry, no analytics, no third-party relay. Audits are local-first; the
APIs are opt-in enrichment.

## Validation is low-cost and auth-only

Validators are designed to prove a key without meaningful spend: DataForSEO hits
the account-status endpoint; Google sends a key-only PageSpeed request that the
API rejects for a *missing url* (proving the key) rather than running Lighthouse;
Firecrawl checks credit-usage; Exa runs a single 1-result query.

## SSRF / URL safety

Upstream's `validate_url()` (in `scripts/google_auth.py`) is preserved: scripts
that accept user URLs block private IPs, loopback, and cloud metadata endpoints.
The onboarding code only contacts fixed, known provider hosts.

## Removing everything

```bash
rm -rf ~/.config/claude-seo/                 # delete all stored keys
# then remove dataforseo/firecrawl/exa from "mcpServers" in ~/.claude/settings.json
```

## Reporting an issue

Found a security problem in the onboarding/storage code? Open a private security
advisory on the repo rather than a public issue.
