# SPEC — Provider Switching: Claude credits ↔ OpenRouter (target: v1.2.0)

**Status:** DESIGN APPROVED, not yet built. This document is the build contract.
**Grounding:** Claude Code env-var surface (`code.claude.com/docs/en/env-vars`) +
OpenRouter's native Anthropic-compatible endpoint and official Claude Code cookbook
(`openrouter.ai/docs/cookbook/coding-agents/claude-code-integration`). Verified June 2026.

## 1. Goal & non-goals

**Goal.** The system always runs on Claude Code (the harness never changes). The
operator can switch the **model backend** on demand:

- `anthropic` — first-party (Claude subscription/credits). The default, and the
  quality reference.
- `openrouter` — an OpenRouter key; models per tier are mapped to **high-grade
  models only** (operator-informed, validated live). Primary use case: **continuity
  when Claude credits run out** — switch in under a minute, keep working, switch back.

**Non-goals (refused per ROADMAP):** no proxy/translation service of our own
(OpenRouter speaks Anthropic's Messages protocol natively); no auto-failover daemon
(manual one-command switch; a launcher wrapper may be considered later); no support
for low-grade models as a default path.

## 2. How the platform makes this possible (the mechanism)

Claude Code reads these env vars **once at process start** (from the `env` block of
`~/.claude/settings.json` or the shell):

| Var | Purpose |
|---|---|
| `ANTHROPIC_BASE_URL` | `https://openrouter.ai/api` → all traffic goes to OpenRouter |
| `ANTHROPIC_AUTH_TOKEN` | the OpenRouter API key |
| `ANTHROPIC_API_KEY` | must be set to `""` explicitly (prevents auth conflicts) |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | what the "opus" alias resolves to |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | what the "sonnet" alias resolves to |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | what the "haiku" alias resolves to |
| `CLAUDE_CODE_SUBAGENT_MODEL` | model for spawned subagents |

**Architectural luck:** our 19 agents and the model router operate on **aliases**
(haiku/sonnet/opus) — exactly the level these vars remap. The skills/agents/engines
layer needs zero changes.

Two documented operator gotchas the UX must surface loudly:
1. Env is read **once at startup** → every switch requires restarting Claude Code.
2. Cached Anthropic logins can conflict → run `/logout` before switching to
   OpenRouter, `/login` after switching back.

## 3. Components to build

### 3.1 Onboarding provider `openrouter` (deferrable) — `onboarding/providers.py` + `validate.py`
- `kind: secret`, **`deferrable: True`** → the wizard offers **[N]ow / [L]ater / [S]kip**,
  exactly like the Google OAuth providers. "Later" calls the existing
  `mark_pending('openrouter')`; `/seo-setup verify` then shows
  `openrouter: PENDING (attach later)`. Attaching later:
  `python …/setup_wizard.py --provider openrouter`.
- Field: `api_key` (format `sk-or-v1-…`), masked input, stored owner-only at
  `~/.config/claude-seo/openrouter.json`.
- **Live validation:** `GET https://openrouter.ai/api/v1/key` with the key — free,
  validates auth AND returns credit/limit info (display remaining credit at setup —
  nice operator signal). Network-fail → honest "could not validate (network)" with
  format-only check, same pattern as other providers.
- Wizard copy must state up front: *"Optional. This is your fallback backend if
  Claude credits run out, and a way to run other frontier models. You can skip and
  attach any time."*

### 3.2 The switcher — `tools/switch_provider.py` (new) + `/seo-provider` skill (new)

CLI surface (mirrored conversationally by the skill):

```
python tools/switch_provider.py status
python tools/switch_provider.py use anthropic
python tools/switch_provider.py use openrouter [--profile claude|custom]
python tools/switch_provider.py set-models --opus <slug> --sonnet <slug> --haiku <slug> [--subagent <slug>]
python tools/switch_provider.py restore        # restore settings.json from last backup
```

**`use openrouter` behavior, in order:**
1. Require `openrouter.json` (else exit with: "not configured — run
   `/seo-setup --provider openrouter` or attach later").
2. **Validate the key live** (`/api/v1/key`) — never write a backend switch with a
   dead key (that would brick the next session).
3. **Validate the model map live** against `GET /api/v1/models` — every slug in the
   active profile must exist on OpenRouter right now. Unknown slug → refuse with the
   closest matches listed.
4. **Back up** `~/.claude/settings.json` → `settings.json.bak-<utc-ts>` (keep last 5).
5. **Safe-merge** ONLY the seven env keys above into the `env` block (the same
   merge discipline as `configure_mcp.py`: parse-fail → refuse, never clobber other
   settings). If a foreign `ANTHROPIC_BASE_URL` already exists (some other gateway),
   warn and require `--force`.
6. Record active state in `~/.config/claude-seo/provider-state.json`
   (`{provider, profile, models, switched_utc}`).
7. Print the **mandatory operator steps**, big and unmissable:
   `① /logout in Claude Code  ② exit  ③ start claude again` — and why (env read once).

**`use anthropic`:** remove exactly those env keys (from backup-diff, not blind
delete), update state, print `restart + /login`.

**`status`:** active provider + profile + model map + key present/pending + remaining
OpenRouter credit (live, when reachable) + drift warnings (e.g., settings has
BASE_URL but state file says anthropic → flag inconsistency; openrouter.json deleted
while in openrouter mode → "broken, run `use anthropic`").

### 3.3 Profiles & the model-quality guardrail

Stored in `~/.config/claude-seo/provider-state.json`. Two profiles:

**Profile `claude` (DEFAULT for `use openrouter`)** — *the out-of-credits lifeline.*
Maps every alias to the same Claude family **via OpenRouter** (using OpenRouter's
`~anthropic/claude-*-latest` aliases so it tracks releases). Near-zero quality risk;
slight cost premium vs first-party (OpenRouter margin). This is what "I ran out of
credits" should use, and the spec's recommended default.

**Profile `custom`** — *any desired model, with guardrails:*
- The operator sets per-tier slugs via `set-models`.
- **Recommended-models list** (maintained as a section in the `/seo-provider`
  SKILL.md, not hardcoded in Python): frontier/high-grade models only — e.g.
  **Kimi K2.6 (moonshotai)**, current DeepSeek/Gemini/GPT frontier tiers. The skill
  presents this list when the operator asks; the switcher **warns** (not blocks)
  when a chosen slug is off-list: *"X is not on the recommended high-grade list —
  evidence-discipline quality is not guaranteed below frontier grade. Proceed?"*
- Exact slugs are **never hardcoded/guessed**: the live `/api/v1/models` check (3.2
  step 3) is the source of truth; the SKILL.md list is guidance text the operator
  can update.
- Tier sanity: orchestration/synthesis (the opus alias) must map to the strongest
  model in the chosen set — the switcher warns if the opus slot is mapped weaker
  than the haiku slot (pricing from `/api/v1/models` as the proxy for grade).

**Quality posture (the honest paragraph that ships in every doc):** Claude Code and
this product's Evidence Integrity Protocol are optimized for Anthropic models —
OpenRouter's own docs say compatibility with other providers is not guaranteed. The
report **linter** still enforces structure regardless of backend, and the report now
**discloses the backend** (3.5), but semantic quality on non-Claude models is the
operator's informed choice. Use frontier-grade models (Kimi K2.6 class) only.

### 3.4 Router integration — `routing/model_router.py`
- `route()` gains provider awareness (reads `provider-state.json`): when
  `provider=openrouter`, emit **aliases** (`haiku`/`sonnet`/`opus`) instead of full
  Claude IDs — the env vars resolve them. When `anthropic`, unchanged.
- `estimate()` v1: when openrouter, print the mapped slugs + a one-line disclaimer
  that costs vary by model (enhancement later: live pricing from `/api/v1/models`,
  which includes per-token pricing).

### 3.5 Report provenance — `report-template.md` + `.html`
Data Integrity & Methodology section gains one mandatory line:
*"Model backend: Anthropic first-party"* or
*"Model backend: OpenRouter — opus→…, sonnet→…, haiku→…"*.
The linter adds a WARN (not FAIL) if the line is absent. Transparency is the brand.

### 3.6 Tests (CI)
- Pure-function unit tests for the settings merge/unmerge (given settings dict +
  profile → expected dict; foreign-BASE_URL refusal; parse-fail refusal) and for
  profile resolution — added to `tests/test_owned_components.py`.
- No live network in CI (key validation paths mocked by injecting a fake fetcher).

## 4. Documentation deliverables (ship WITH the build, not before)

The exact on-demand switch recipe, verbatim in **README** (new subsection under
"Quality & release engineering" or Install), **Manual** (new §6.8 "OpenRouter
onboarding" + new §12.5 "Switching backends on demand" + 3 new troubleshooting
rows), and **docs/ONBOARDING.md**:

```text
# Claude credits ran out mid-engagement?  (~60 seconds)
python tools/switch_provider.py use openrouter     # default = same Claude models via OpenRouter
# in Claude Code:  /logout   → then exit
claude                                             # restart; you're now on OpenRouter

# Switch back later:
python tools/switch_provider.py use anthropic
# restart Claude Code, then /login
```

Plus: how to set a custom high-grade model map (`set-models`), the recommended-models
guidance (Kimi K2.6 class), `status`, `restore`, and the three gotchas (restart
required · /logout/login · slight cost premium on the claude profile).
Troubleshooting additions: auth-conflict symptoms, "model not found" (slug typo →
the live-validation message), "switched but nothing changed" (didn't restart).

## 5. Risk register

| Risk | Level | Mitigation in this design |
|---|---|---|
| Quality drop on non-Claude models (prompt-enforced evidence discipline weakens) | **High if ignored** | `claude` profile as default; recommended-list + off-list warning; linter unchanged; report provenance line; docs say frontier-grade only |
| Bad key/slug bricks the next session | Med | Live key + model validation BEFORE writing; backup + `restore` |
| settings.json corruption | Med | Parse-fail refusal; surgical merge of 7 keys only; timestamped backups (keep 5) |
| Operator confusion (env-read-once) | Med | Mandatory printed steps; `status` drift detection |
| Cost surprise | Low | claude-profile premium documented; custom pricing disclaimer |
| Upstream sync overwrite | Low | `skills/seo-provider/`, `tools/switch_provider.py` added to `OVERLAY_PROTECTED` |

## 6. Effort & sequencing

~1.5–2 days, all owned/additive files:
1. Provider + validator + wizard deferrable entry (S)
2. `switch_provider.py` with backups/validation/merge (M — the core)
3. `/seo-provider` SKILL.md incl. recommended-models section (S)
4. Router alias mode (S)
5. Report provenance + linter warn (XS)
6. Tests (S) → docs (S) → bump v1.2.0 in VERSION.md / system-version.json / plugin.json

Build on a feature branch; CI green before merge; tag `v1.2.0`.
