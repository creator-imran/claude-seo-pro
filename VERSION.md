# Claude SEO Pro — System Version & Provenance

**Product:** Claude SEO Pro · **Version:** `1.1.0` · **Date:** 2026-06-06
**Maintainer:** [creator-imran](https://github.com/creator-imran)
**Built on (upstream):** [`AgricIDaniel/claude-seo`](https://github.com/AgricIDaniel/claude-seo) `@ v2.0.0` · MIT

This file is the single source of truth for **what came from the source repo** versus
**what the system is now**. The companion machine-readable manifest is
[`system-version.json`](system-version.json); the pinned upstream tag is in
[`upstream.json`](upstream.json); the file-level changelog is in
[`docs/WHATS-DIFFERENT.md`](docs/WHATS-DIFFERENT.md).

---

## At a glance

| | Source (upstream `claude-seo` v2.0.0) | Claude SEO Pro 1.1.0 (now) |
|---|---|---|
| SEO sub-skills | 25 | 25 upstream **+ 5 added** = 30 |
| Specialist agents | 18 | 18 upstream **+ 1 added** = 19 |
| In-place edits to upstream files | — | **1** (`skills/seo-audit/SKILL.md`, via managed overlay) |
| Guided API onboarding | none | **yes** (7 providers, owner-only storage) |
| Persistent client memory | none | **yes** (knowledge store + data cache) |
| Model-cost routing | implicit | **yes** (dispatch-time policy) |
| Chat (Slack) interface | none | **yes** (headless connector) |
| Report depth contract + linter | n/a | **yes** (14 sections, machine-enforced) |
| White-label client reports | n/a | **yes** (`branding.json`) |
| CI regression gate | upstream's own | **yes, for the Pro layer** (push/PR) |
| Install drift detection | none | **yes** (`check_install.py` + manifest stamp) |
| Plugin-marketplace install | upstream's identity | **yes, rebranded** (one-command) |
| Upstream-sync mechanism | n/a | **yes** (overlay + PR workflow) |
| License | MIT | MIT (attribution in [`NOTICE`](NOTICE)) |

---

## 1. What was installed from the source repo (the baseline)

Vendored **verbatim** from `AgricIDaniel/claude-seo @ v2.0.0` (MIT). Content-identical to
upstream except the single file in §2. Verified by hash + normalized-content diff.

| Upstream component | What it is |
|---|---|
| `skills/seo/` + 24 `seo-*` sub-skills | The orchestrator + audit/content/schema/technical/geo/local/maps/sitemap/images/backlinks/cluster/sxo/drift/ecommerce/hreflang/plan/programmatic/competitor-pages/page/google + extension mirrors |
| `agents/` (18 `seo-*.md`) | Specialist subagents (technical, content, schema, performance, visual, geo, local, maps, google, backlinks, dataforseo, image-gen, cluster, sxo, drift, ecommerce, sitemap) |
| `scripts/` | Python execution scripts: Google APIs (PSI/CrUX/GSC/GA4/Indexing), backlinks (Moz/Bing/CommonCrawl), drift, schema, render/fetch/parse, etc. |
| `schema/`, `hooks/`, `pdf/`, `references/`, `extensions/` | Schema templates, quality-gate hooks, PDF reference, on-demand knowledge, optional MCP extension installers |
| `tests/`, `assets/`, `branding/`, `data/`, `docs/` | Upstream test suite, diagrams, brand kit, data, original docs |

> Org-specific upstream files intentionally **dropped** in this fork: `CODEOWNERS`,
> `CITATION.cff`, `.devcontainer/` (replaced by our own distribution conventions).

---

## 2. The single in-place modification to an upstream file

`skills/seo-audit/SKILL.md` — the only upstream-owned file we changed. Managed as an
**idempotent overlay** (`tools/apply_overlay.py`) so it survives every upstream sync.
Four anchored changes (all currently verified "present"):

| Change | What it does | Why |
|---|---|---|
| `pro-workflow` | Adds the "Pro Workflow" section (Phase 0 BI → playbook → keyword research → local/GBP) | Wires the enhanced 4-phase pipeline |
| `fetch-path` | Corrects the shared-script path to `~/.claude/skills/seo/scripts/fetch_page.py` + mandates pre-fetch | Upstream relative path resolves wrong once installed → caused blind subagents → fabrication |
| `evidence-protocol` | Inserts the 8-rule **Evidence Integrity Protocol** (no fabrication; cite evidence; never strip caveats; field-data CWV; etc.) | The anti-fabrication core lesson |
| `error-rows` | Adds WAF/subagent failure handling rows | Robust failure behavior |

---

## 3. What was added on top (features & enhancements)

All additions are **owned files** (protected from upstream sync via
`OVERLAY_PROTECTED` in `tools/sync_upstream.py`). Status legend: ✅ verified offline ·
⏳ built, live-validation pending (needs external creds/network).

### 3.1 Guided onboarding & secure credential storage
- `onboarding/` — `secure_store.py` (owner-only 0600 / Windows ACL, atomic writes),
  `providers.py` (provider registry), `validate.py` (live validators),
  `configure_mcp.py` (safe-merge MCP into `settings.json`), `setup_wizard.py`
  (collect→validate→store→wire; `--check/--from-env/--provider/--no-mcp/--no-validate`),
  `gbp_auth.py` (Google Business Profile OAuth + metrics).
- `skills/seo-setup/SKILL.md` — `/seo-setup` (verify | setup | rotate).
- **Providers onboarded:** DataForSEO, Google API key (PSI/CrUX), Google OAuth
  (GSC/Indexing/GA4), Google Business Profile, Firecrawl, Exa, Slack.
- Status: ✅ validators (DataForSEO/Google key live-tested earlier; format/auth checks
  for the rest). ⏳ OAuth browser flows (GSC/GA4/GBP) need real client_secret + access.

### 3.2 Evidence-first 4-phase audit pipeline
- `skills/seo-audit/references/business-intelligence.md` — **Phase 0**: infer business
  model, country, target markets, ICPs, seed keywords → `business-profile.json`; reads
  the knowledge store first.
- `audit-playbook.md` — templatized per-category checklists, model tiering, parallel
  dispatch, adversarial verification, report assembly.
- `keyword-research.md` + `scripts/keyword_research.py` — multi-locale DataForSEO
  keyword research (volume/CPC/KD/intent, opportunity tiers).
- `local-gbp-audit.md` — Tier A first-party GBP / Tier B DataForSEO / Tier 0 on-page.
- Status: ✅ docs + `keyword_research.py --plan` (cost preview). ⏳ live keyword
  fan-out (needs DataForSEO un-IP-blocked).

### 3.3 Feature 1 — Persistent knowledge store + data cache
- `knowledge/` — `store.py` (per-client business understanding + evidence-tagged facts +
  audit history; survives model switches & sessions), `cache.py` (TTL'd, provenance-
  tracked cache of expensive API results; expired = miss, no stale reads), `fsutil.py`.
- `skills/seo-knowledge/SKILL.md` — `/seo-knowledge` (recall | remember | history | cache).
- Status: ✅ verified (dedup, forced-low confidence, recall, cache hit/miss/expiry, provenance).

### 3.4 Feature 2 — Client-business learning agent
- `agents/seo-learn.md` + `skills/seo-learn/SKILL.md` + `knowledge/learn.py` (+ supersede
  support in `store.py`). Distills durable facts after each audit, supersedes stale ones,
  rejects transient metrics & secrets, preview-then-ingest.
- Status: ✅ verified (guards, dedup, supersede, downgrade, preview).

### 3.5 Feature 3 — Smart model-routing policy
- `routing/model_router.py` + `skills/seo-models/SKILL.md`. Dispatch-time tiering —
  Haiku (extraction) / Sonnet (reasoning, verification) / Opus (synthesis, orchestration —
  main loop kept **fixed** to preserve the prompt cache). Cost estimates + per-deployment
  overrides (`~/.config/claude-seo/model-policy.json`).
- Status: ✅ verified (routing, fallback, estimate, force-model/force-tier, reset).

### 3.6 Feature 4 — Chat connector (Slack → headless SEO)
- `connector/` — `auth.py` (Slack HMAC verify + replay window + deny-by-default authz),
  `commands.py` (parse → skill + prompt), `runner.py` (headless `claude -p`, pure builder +
  dry-run), `slack_bridge.py` (pure `handle_slash()` + stdlib HTTP server), `config.py`.
- `skills/seo-connect/SKILL.md` + `docs/CONNECTOR.md` + the `slack` onboarding provider.
- Status: ✅ security core verified offline (signature/parse/authz/builder/handle_slash).
  ⏳ live end-to-end (real Slack app + `claude -p` run) is the operator's deploy step.
- WhatsApp: documented as a future adapter on the same transport-agnostic runner.

### 3.7 Upstream-sync mechanism (keeps the fork current)
- `upstream.json` (pinned tag), `tools/apply_overlay.py` (re-applies §2 idempotently),
  `tools/sync_upstream.py` (re-vendors upstream, skips owned files, re-applies overlay),
  `.github/workflows/sync-upstream.yml` (weekly; opens a reviewable PR — never auto-merges).
- Status: ✅ overlay idempotent + 4/4 present; ⏳ live dry-run pending network.

### 3.8 Distribution, docs & install
- `README.md` (rewritten), `CLAUDE.md` (topology), `NOTICE` (MIT attribution),
  `.claude-plugin/plugin.json` + `marketplace.json` (rebranded for one-command
  `/plugin marketplace add creator-imran/claude-seo-pro`), self-contained
  `install.ps1`/`install.sh` (now stamping `install-manifest.json`),
  `publish-to-github.ps1` (with staged-secret guard), `docs/` (ONBOARDING, SECURITY,
  WHATS-DIFFERENT, PUBLISH, CONNECTOR, ROADMAP-7-to-9),
  `manual/Claude-SEO-Pro-User-Manual-v02.{html,pdf}` (v02 supersedes v01).

### 3.9 Quality & release engineering — NEW in 1.1.0
- **CI regression gate** — `.github/workflows/ci.yml` + `tests/test_owned_components.py`
  (the 68-assertion adversarial suite, in-repo) + `tests/test_repo_integrity.py`
  (compile-all · JSON validity · secret-scan · no-client-data) + overlay check +
  report-linter self-test. Runs on every push/PR; stdlib-only, offline. Status: ✅.
- **Install drift guard** — `tools/check_install.py` hashes the Pro-owned surface (repo
  vs `~/.claude`) and reports FRESH/STALE; installers stamp
  `~/.config/claude-seo/install-manifest.json`; wired into `/seo-setup verify`.
  Status: ✅ (caught a real stale-install incident on first run).
- **Report-contract linter** — `tools/lint_report.py`: deterministic enforcement of the
  14-section depth contract (FAIL on missing sections / leftover placeholders /
  summary-only compression; WARN on depth floors). Validated against ground truth:
  gold-depth report PASSes, the known-shallow report FAILs, raw template FAILs.
  Mandatory pre-delivery step. Status: ✅. (LLM-judge half deferred until calibrated.)
- **White-label branding** — `onboarding/branding.py` + `~/.config/claude-seo/branding.json`:
  agency rebrand of client reports (preparer, colors, logo, footer) with neutral
  defaults; report generation loads it as step 0. Status: ✅.
- **Roadmap & scope guardrail** — `docs/ROADMAP-7-to-9.md`: phased plan with an explicit
  refused-features list (no SaaS dashboard / own crawler / multi-tenant / SLAs).
- **Fix:** `scripts/keyword_research.py` preflight probed a non-existent endpoint
  (aborted every live run as "data pending"); replaced with a real minimal Labs probe,
  live-verified. The fan-out *execution* remains Phase-2 work (honest stub).

---

## 4. Verification status

| Check | Result |
|---|---|
| Adversarial component suite (`tests/test_owned_components.py`, in CI) | **68/68 pass** |
| Repo integrity (`tests/test_repo_integrity.py`, in CI) | **OK** — 99 .py compile, 8 JSON valid, secret-scan clean, no client data |
| Overlay integrity (idempotent) | **4/4 present** |
| Report-linter ground-truth matrix | **correct** (gold PASS / shallow FAIL / template FAIL) |
| Install drift | **FRESH** (repo ↔ `~/.claude` match) |
| Provenance (`sync_upstream.py --dry-run`) | **clean** — only the managed overlay differs |
| Live production runs | full 4-phase audit (US client) + live-data audit (Dubai client, 28 API calls $0.61) |
| **Pending (external):** | live keyword fan-out execution (Phase 2), GSC/GA4/GBP OAuth browser flows, Slack live e2e (operator deploy steps) |

---

## 5. Version history

| Version | Date | Summary |
|---|---|---|
| `1.1.0` | 2026-06-06 | **Hardening + quality release (Phase 1 + risk-free Phase 2).** Added: CI regression gate (`tests/` + `ci.yml`); install drift guard (`tools/check_install.py` + installer manifest stamp, wired into `/seo-setup verify`); white-label branding (`onboarding/branding.py` + report-template tokens); deterministic report-contract linter (`tools/lint_report.py`, mandatory pre-delivery, CI self-tested); plugin-marketplace distribution (rebranded `.claude-plugin/marketplace.json`, README one-command install); roadmap + refused-features guardrail (`docs/ROADMAP-7-to-9.md`); report depth contract (14 sections, extracted from the gold-standard client report) with HTML skeleton. Fixed: `keyword_research.py` dead-endpoint preflight (live-verified); `utcnow()` deprecations; stale-install incident (drift guard caught it). User Manual **v02** (exhaustive rewrite; supersedes v01). |
| `1.0.0` | 2026-06-06 | Initial Pro distribution (tag `v1.0.0`): vendored `claude-seo v2.0.0` + Evidence Integrity overlay + guided onboarding (7 providers) + 4-phase audit (BI, keyword research, local/GBP) + knowledge store/cache + learning agent + model routing + Slack connector + upstream-sync + User Manual v01. Verified by 68/68 adversarial assertions and two live client audits. Feature 5 (skills-enhancer) deferred by design. |

> **How to re-verify provenance** ("is this still upstream + our overlay only?"):
> run `python tools/sync_upstream.py --dry-run` — a clean run reports **only**
> `skills/seo-audit/SKILL.md` as changed, everything else protected.
