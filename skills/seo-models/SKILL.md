---
name: seo-models
description: "Inspect and tune the model-routing policy — which Claude model each audit task runs on (Haiku extraction, Sonnet reasoning, Opus synthesis). Use when the user says model routing, which model, model policy, make it cheaper/faster, run everything on opus, force a model, or /seo-models. The audit orchestrator applies this policy automatically per task."
user-invokable: true
argument-hint: "[show|route <agent>|estimate|set ...|reset]"
license: MIT
metadata:
  author: creator-imran
  version: "1.0.0"
  category: seo
---

# Model Routing Policy

The system runs each audit task on the **cheapest Claude model that does it well**, then
synthesises on the strongest. This is the "smart model changer" in the form that actually
works in Claude Code: a **dispatch-time policy** the orchestrator consults per subagent —
not a background daemon (which would fight the harness and trash the prompt cache).

Engine: `~/.claude/skills/seo/routing/model_router.py`. Override policy (optional):
`~/.config/claude-seo/model-policy.json`.

## The tiers (defaults)
| Tier | Model | Effort | Used for |
|---|---|---|---|
| extraction | Haiku 4.5 | low | mechanical reading of pre-fetched files (titles/metas/status/schema-presence). High-volume, parallel, can't hallucinate off evidence. |
| verification | Sonnet 4.6 | medium | independent adversarial check of a Critical/High finding |
| reasoning | Sonnet 4.6 | high | judgement: E-E-A-T, intent, personas, business profile, fact extraction |
| synthesis | Opus 4.8 | high | cross-dimension prioritisation + the final report |
| orchestration | Opus 4.8 | xhigh | the main loop — **kept fixed** to preserve the prompt cache |

## The cache rule (why we don't switch the main model)
Switching the main session's model **invalidates the prompt cache** (it's model-scoped,
~5-min TTL). So the orchestrator stays on one model and routes only *sub-work* to cheaper
tiers via subagents — the same pattern Claude Code's own Explore subagents use (Haiku).
This is why Feature 3 is a routing policy, not a model-switching daemon.

## How the orchestrator uses it (automatic)
When dispatching a specialist, it asks the router for the model + effort:
```
python ~/.claude/skills/seo/routing/model_router.py route --agent seo-technical
# -> {"tier":"extraction","model":"claude-haiku-4-5","effort":"low", ...}
```
and spawns that subagent on the returned model. Extraction specialists go to Haiku;
reasoning specialists (incl. seo-learn) to Sonnet; synthesis/report to Opus.

## Commands
- **See the whole policy:** `! python .../routing/model_router.py show`
- **What model would X use:** `! python .../routing/model_router.py route --agent seo-content`
- **Cost of a tier vs Opus:** `! python .../routing/model_router.py estimate --tier extraction --in 40000 --out 8000`
- **Quality pass — force every dispatch to Opus:** `! python .../routing/model_router.py set --force-model opus`
- **Force every dispatch to one tier:** `! python .../routing/model_router.py set --force-tier synthesis`
- **Remap one agent:** `! python .../routing/model_router.py set --agent seo-content --tier synthesis`
- **Back to defaults:** `! python .../routing/model_router.py reset`

## When to tune it
- **Cost-sensitive / large batches:** keep defaults (extraction on Haiku saves the most).
- **Highest-quality one-off (e.g. a flagship client report):** `--force-tier opus`.
- **A specific specialist underperforming on a tier:** bump just that agent with `set --agent`.

Estimates use the published per-million pricing (Haiku $1/$5, Sonnet $3/$15, Opus $5/$25),
so `estimate` shows the real saving the router buys versus running everything on Opus.
