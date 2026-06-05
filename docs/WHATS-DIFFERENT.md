# What's different from upstream Claude SEO

This is an honest, file-level account of how Claude SEO Pro differs from the
upstream [`AgriciDaniel/claude-seo`](https://github.com/AgriciDaniel/claude-seo)
it is built on. The short version: **the 25 skills and 18 agents are upstream's
work, preserved. Our value is in onboarding, secure storage, and audit
integrity — not in rewriting the skill library.**

## Added (new in this distribution)

| Path | What it is |
|---|---|
| `onboarding/secure_store.py` | Owner-only (0600) credential storage under `~/.config/claude-seo/`, with Windows ACL hardening and atomic writes. |
| `onboarding/providers.py` | Registry of the four onboarded APIs (DataForSEO, Google, Firecrawl, Exa): fields, signup URLs, MCP specs, caveats. |
| `onboarding/validate.py` | Live connectivity validators per provider. Distinguishes bad credentials from valid-credentials-but-IP-blocked (DataForSEO `40207`). |
| `onboarding/configure_mcp.py` | Safe-merge MCP servers into `~/.claude/settings.json` (backup first, never clobbers existing keys). |
| `onboarding/setup_wizard.py` | The guided CLI: collect → validate → store → wire MCP. Interactive, `--check`, `--from-env`, per-provider, `--no-mcp` modes. |
| `skills/seo-setup/SKILL.md` | The `/seo-setup` Claude Code skill that drives onboarding conversationally and never handles raw secrets in chat. |
| `NOTICE` | MIT attribution to upstream + list of additions. |
| `docs/ONBOARDING.md`, `docs/SECURITY.md`, this file | Client-facing docs. |

## Changed

| Path | Change | Why |
|---|---|---|
| `skills/seo-audit/SKILL.md` | (1) Fixed the shared-script fetch path to `~/.claude/skills/seo/scripts/fetch_page.py` and mandated pre-fetch in the main session. (2) Added the **Evidence Integrity Protocol** (8 rules) + WAF/subagent error-handling rows. | The upstream relative path (`scripts/fetch_page.py`) resolves wrong once installed — subagents that can't fetch may guess. This was the root cause of a real fabricated audit. The protocol makes "no evidence → no finding" structural. |
| `install.ps1`, `install.sh` | Rewritten to be **self-contained** (install from this repo, not clone upstream) and to launch onboarding at the end. | A client distribution shouldn't depend on a third-party repo being available at install time. |
| `.claude-plugin/plugin.json` | Rebranded to `claude-seo-pro` with `based_on` attribution to upstream. | Identity + license clarity. |
| `.gitignore` | Added safety-net ignores for `*-api.json` / provider config filenames. | Prevent a client ever committing a key dropped in the working tree. |
| `CLAUDE.md` (repo topology section) | Replaced upstream's public/private dual-remote release workflow with this repo's single-remote model. | Upstream's workflow is specific to their org. |

## NOT changed (preserved from upstream, verbatim content)

- All 25 sub-skills' analysis logic and all 18 agents (aside from the two notes
  below).
- All Python scripts in `scripts/` (Google APIs, backlinks, drift, schema, etc.).
- Schema templates, references, hooks, PDF report generator, tests.

> **A note on the two upstream agents** `seo-dataforseo.md` and
> `seo-image-gen.md`: in some upstream installs these lost their `model:` and
> `maxTurns:` frontmatter during install-time copying. This distribution ships
> them as committed in upstream's repo. If you want those two agents pinned to a
> specific model or turn cap, add the frontmatter back explicitly.

## Staying current with upstream

This is a vendored fork, so upstream fixes don't appear by magic — but pulling them
in is a **single command**, and CI does it for you.

### How sync stays safe across a refresh

Our changes are split into two kinds so a re-vendor never loses them:

1. **Additive files we own** (`onboarding/`, `skills/seo-setup/`, `tools/`, our docs,
   installers, `NOTICE`, etc.). These are listed in `OVERLAY_PROTECTED` in
   `tools/sync_upstream.py` and are **never overwritten** by an upstream pull.
2. **The one in-place change** to `skills/seo-audit/SKILL.md` (Evidence Integrity
   Protocol + fetch-path fix). This is expressed as an **idempotent overlay** in
   `tools/apply_overlay.py` — after upstream's pristine file is vendored in, the
   overlay re-injects our content using text anchors. If upstream moves an anchor,
   the tool reports `FAILED` for that change so you fix it deliberately instead of
   silently losing it.

### Manual sync

```bash
python tools/sync_upstream.py --dry-run        # preview what upstream would change
python tools/sync_upstream.py --tag v2.1.0     # vendor that release + re-apply overlay
python tools/apply_overlay.py --check          # confirm the overlay is intact
# then: review `git diff`, run tests, commit
```
`upstream.json` records the currently pinned upstream tag.

### Automatic sync (CI)

`.github/workflows/sync-upstream.yml` runs every Monday (and on demand). It resolves
upstream's **latest release**, runs the sync, re-applies the overlay, and opens a
**pull request** — so upstream fixes arrive as a reviewable PR, never an unreviewed
push. If the overlay step fails, the PR body tells you exactly which anchor moved.

### Re-verifying the fork is still "upstream + overlay only"

To confirm nothing drifted: `python tools/sync_upstream.py --dry-run` should report
only `skills/seo-audit/SKILL.md` as changed (pristine-vs-overlaid) and zero other
content differences against the pinned tag.
