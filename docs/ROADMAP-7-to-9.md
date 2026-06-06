# Roadmap: 7 → 9, and the line we will not cross

This document is both a plan and a **guardrail**. The single biggest risk to this
project is not building too little — it's building the *wrong* "9/10" (a hosted SaaS)
and derailing a sharp, differentiated, local-first tool into a weak dashboard clone.
The refused-features list below is as important as the build list.

Grounded in a June 2026 market scan (AI-visibility tooling, agency white-label
requirements, LLM-eval practices, Claude Code plugin distribution) cross-referenced with
an internal capability/reliability ledger. Sources are cited inline in the research
thread; the verdict is summarized here.

## Where we are

- **~7/10** as a solo-operator / agency tool: stable, evidence-disciplined, two live
  client audits delivered, 68/68 adversarial tests, provenance-verified fork.
- The missing points are **reliability finishing** and **a few high-value capabilities**
  — not infrastructure.

## The guiding distinction (read this first)

There are two different "9/10"s, and only one is ours to chase:

| 9/10 as a **solo-operator / agency tool** (OUR TARGET) | 9/10 as a **commercial SaaS** (NOT our target) |
|---|---|
| Reachable — mostly *finishing built substrate* | Requires infrastructure we have no moat in |
| Preserves the local-first / evidence-first / no-lock-in differentiation | Destroys it — competes with Semrush/Ahrefs on their turf |
| Low derailment risk (owned files, additive) | High risk + high cost + abandons our advantage |

## Phase 1 — Low-risk hardening (7 → 8) · IN PROGRESS

All owned-files/config; none touch the vendored skills or the overlay; none add hosted
infra or auto-edit anything.

| # | Item | Status |
|---|---|---|
| 2 | Tag `v1.0.0` rollback point + branch discipline | ✅ tagged (push pending) |
| 1 | CI in the repo (component tests + integrity + overlay + provenance) | ✅ `.github/workflows/ci.yml` + `tests/` (68/68 + integrity) |
| 6 | This roadmap + refused-features list | ✅ |
| 4 | Installed-skill drift guard (`tools/check_install.py` + installer stamp) | ✅ caught a real stale install; now FRESH |
| 3 | White-label config (`onboarding/branding.py` → report template) | ✅ load/set/validate/reset + contract wired |
| 5 | Validate the 3 unvalidated paths | ✅ done — see outcome below |

### Item 5 outcome (validation surfaced the true state — honest, not faked)
- **Live keyword fan-out:** validation found a real preflight bug (probed a non-existent
  endpoint → every run aborted as "data pending"). **Fixed** (real cheap Labs probe) and
  **live-verified** against the whitelisted account (preflight returns OK). The full
  fan-out *execution* (multi-stage merge) was always an honest stub — it is genuine
  feature work and is moved to **Phase 2**, not claimed as done here.
- **GSC/GA4 OAuth e2e:** requires a human browser-consent step; cannot be headless-validated.
  The offline path (`--check`) and the wizard's attach-later flow stand; live run is an
  operator step. Unchanged, documented.
- **Slack connector e2e:** the security/parse/auth/runner core is now **unit-tested in CI**
  (handle_slash decision path, HMAC, deny-by-default). The live round-trip needs a real
  Slack app + a reachable host — an operator deploy step. Documented.

## Phase 2 — High-value capability (8 → 9)

**Risk-free items shipped first** (additive, deterministic, offline-verifiable): the
report-contract linter and marketplace distribution — see ✅ rows. The three items
involving **live API spend or unvalidated integrations** (keyword fan-out execution,
AI-visibility tracking, scheduled monitoring) remain gated on an explicit go-ahead,
each with its own design + checkpoint before build.

| Item | Why it's a 9/10 lever | Risk notes |
|---|---|---|
| **Live keyword fan-out execution** (the multi-stage merge behind `keyword_research.py`) | Productizes what's currently done by hand each audit | Preflight is fixed + live-verified; only the merge stages remain. Owned script → low risk. *(Surfaced during Phase-1 item 5.)* |
| **AI-visibility tracking** (ChatGPT/Perplexity/AIO citation monitoring) | The category's defining 2026 capability; now table-stakes for agency tools | New live-API integration; substrate exists (DataForSEO AI-mentions + seranking/profound extensions). Owned skill → low structural risk |
| **Scheduled monitoring + alerting** ("watch client weekly, alert on drops") | The #1 agency must-have; turns one-shot audits into retainers | Uses Claude Code cron/`/loop` + the Slack connector + drift snapshots. Owned |
| **Audit-quality eval harness** — deterministic half ✅ DONE | The trust bar for *any* LLM product; catches "the audit got dumber" | ✅ `tools/lint_report.py` ships: FAILs on missing sections / leftover placeholders / summary-only compression; validated against ground truth (gold-depth report PASSes, the known-shallow report FAILs, raw template FAILs); wired into the contract's self-check + a CI self-test. The **LLM-judge half stays deferred** — flaky until calibrated (≥100 labeled examples) |
| **Plugin-marketplace distribution** ✅ DONE | The ecosystem's front door; kills install friction | ✅ `.claude-plugin/marketplace.json` rebranded to `creator-imran-claude-seo-pro` (was upstream's verbatim); README documents `/plugin marketplace add creator-imran/claude-seo-pro`. Note: plugin install covers skills/agents; the engines + drift guard still come via the installer |

## ❌ Refused features — the line we will NOT cross

These are the "enterprise-vanity" 9/10 that would derail the build. Each is rejected with
its reason. **If a future request asks for one of these, point here first.**

- **A hosted web dashboard / multi-tenant SaaS.** Abandons local-first ("your data never
  leaves your machine"), our entire differentiation, to compete with Semrush/Ahrefs UIs
  where we have no moat.
- **Our own crawler at scale.** Screaming Frog / commercial crawlers exist and are better;
  building one is months of infra for a commoditized capability. We integrate, not rebuild.
- **Log-file analysis at enterprise scale.** Infrastructure-heavy, enterprise-vanity for a
  solo/agency tool.
- **Multi-tenant auth / SSO / per-seat billing infrastructure.** The distribution model is
  per-machine, per-seat by *install* — not a SaaS tenancy layer.
- **SLAs / uptime guarantees / a hosted backend.** There is no backend to have uptime; that
  is the point.
- **Autonomous skill self-modification** (the deferred "skills-enhancer", Feature 5, in its
  auto-apply form). The one feature class that edits the working system. Stays **deferred
  and PR-gated** — suggest-only, human-approved, never auto-applied.

## Operating rules while we climb

1. **`main` stays the proven release.** New work on feature branches; merge via PR after CI
   is green. (Tag `v1.0.0` is the rollback point.)
2. **Owned-files only for new capability.** Anything that needs to touch a vendored skill
   goes through the overlay (`apply_overlay.py`), which fails loudly on drift.
3. **Evidence discipline applies to us too.** Don't ship a capability whose output we can't
   verify; the eval harness (Phase 2) exists to enforce this on the audit output itself.
4. **Re-read the refused list before saying yes to scope.**
