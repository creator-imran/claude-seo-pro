#!/usr/bin/env python3
"""
model_router.py - dispatch-time model-routing policy for Claude SEO Pro (Feature 3).

This is the "smart model changer" in the form that actually works with Claude Code: NOT
a background daemon flipping the main session's model (which would fight the harness and
invalidate the prompt cache), but a POLICY the orchestrator consults when it spawns each
subagent/task — assigning the cheapest model that does the job well:

  * Haiku  -> mechanical extraction (titles, metas, status codes, schema presence,
              parsing pre-fetched files). High-volume, parallel, can't hallucinate off
              evidence. Cheap + fast.
  * Sonnet -> judgement/reasoning (E-E-A-T, intent match, SXO personas, the learning
              agent's fact extraction) and adversarial verification.
  * Opus   -> synthesis: cross-dimension prioritisation and the final report; and the
              orchestrator/main loop itself.

Cache rule (grounded in the Anthropic guidance): switching the model mid-session
invalidates the prompt cache, so KEEP THE MAIN LOOP ON ONE MODEL and route only
sub-work to cheaper tiers. This router encodes that — the `orchestration` tier is the
fixed main loop; everything else is a subagent dispatch.

Per-deployment overrides live at ~/.config/claude-seo/model-policy.json (a client can
pin models, force a tier for a quality/debug run, or remap an agent).

Usage:
  python model_router.py route --agent seo-technical
  python model_router.py route --task extraction
  python model_router.py show
  python model_router.py estimate --tier synthesis --in 40000 --out 8000
  python model_router.py set --agent seo-content --tier synthesis
  python model_router.py set --force-tier opus      # quality pass: everything on Opus
  python model_router.py reset
"""

from __future__ import annotations

import argparse
import json
import os

POLICY_PATH = os.path.expanduser("~/.config/claude-seo/model-policy.json")

# Model catalog (IDs + USD per 1M tokens, from the Claude API reference).
MODELS = {
    "haiku":  {"id": "claude-haiku-4-5",  "in": 1.0,  "out": 5.0},
    "sonnet": {"id": "claude-sonnet-4-6", "in": 3.0,  "out": 15.0},
    "opus":   {"id": "claude-opus-4-8",   "in": 5.0,  "out": 25.0},
}

# Task tier -> (model, effort, rationale). Effort: low|medium|high|xhigh|max.
TIERS = {
    "extraction":    {"model": "haiku",  "effort": "low",
                      "why": "mechanical reading of pre-fetched files; high-volume, parallel; cannot hallucinate off evidence"},
    "verification":  {"model": "sonnet", "effort": "medium",
                      "why": "independent adversarial check of a Critical/High finding"},
    "reasoning":     {"model": "sonnet", "effort": "high",
                      "why": "judgement: E-E-A-T, intent, personas, business profile, fact extraction"},
    "synthesis":     {"model": "opus",   "effort": "high",
                      "why": "cross-dimension synthesis, prioritisation, final report"},
    "orchestration": {"model": "opus",   "effort": "xhigh",
                      "why": "the main loop / orchestrator — keep FIXED to preserve the prompt cache"},
}

# Which tier each known specialist defaults to.
AGENT_TIER = {
    # extraction-leaning (read pre-fetched evidence / API JSON)
    "seo-technical": "extraction", "seo-schema": "extraction", "seo-sitemap": "extraction",
    "seo-images": "extraction", "seo-performance": "extraction", "seo-google": "extraction",
    "seo-dataforseo": "extraction", "seo-visual": "extraction",
    # judgement / reasoning
    "seo-content": "reasoning", "seo-geo": "reasoning", "seo-sxo": "reasoning",
    "seo-local": "reasoning", "seo-maps": "reasoning", "seo-backlinks": "reasoning",
    "seo-ecommerce": "reasoning", "seo-cluster": "reasoning", "seo-learn": "reasoning",
}

DEFAULT_TIER = "reasoning"


def load_policy() -> dict:
    try:
        with open(POLICY_PATH, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def save_policy(policy: dict) -> None:
    os.makedirs(os.path.dirname(POLICY_PATH), exist_ok=True)
    with open(POLICY_PATH, "w", encoding="utf-8") as fh:
        json.dump(policy, fh, indent=2, sort_keys=True)
    try:
        if os.name != "nt":
            os.chmod(POLICY_PATH, 0o600)
    except OSError:
        pass


def _tier_for(agent: str | None, task: str | None, policy: dict) -> tuple:
    """Return (tier, source) applying overrides in precedence order."""
    if policy.get("force_tier") in TIERS:
        return policy["force_tier"], "override:force_tier"
    if agent and agent in (policy.get("agent_tier") or {}):
        return policy["agent_tier"][agent], "override:agent_tier"
    if agent and agent in AGENT_TIER:
        return AGENT_TIER[agent], "default:agent"
    if task and task in TIERS:
        return task, "default:task"
    return DEFAULT_TIER, "default:fallback"


PROVIDER_STATE = os.path.expanduser("~/.config/claude-seo/provider-state.json")


def active_provider() -> str:
    """Which backend Claude Code is pointed at (set by tools/switch_provider.py)."""
    try:
        with open(PROVIDER_STATE, encoding="utf-8") as fh:
            return json.load(fh).get("provider", "anthropic")
    except (OSError, json.JSONDecodeError):
        return "anthropic"


def route(agent: str | None = None, task: str | None = None) -> dict:
    """The core call the orchestrator makes per dispatch."""
    policy = load_policy()
    tier, source = _tier_for(agent, task, policy)
    spec = TIERS[tier]
    model_key = spec["model"]
    provider = active_provider()
    # OpenRouter mode: emit the ALIAS (haiku/sonnet/opus). Claude Code's
    # ANTHROPIC_DEFAULT_*_MODEL env vars (written by switch_provider.py) resolve it
    # to whatever the active profile mapped — full IDs would bypass that mapping.
    if provider == "openrouter":
        model_id = model_key
        source += "@openrouter"
    else:
        # tier->model can be remapped per deployment
        model_id = (policy.get("tier_models") or {}).get(tier) or MODELS[model_key]["id"]
    # force_model pins the MODEL on every dispatch (e.g. "everything on Opus" for a
    # flagship report) — the tier still supplies effort/rationale.
    forced = False
    fm = policy.get("force_model")
    if fm:
        if provider == "openrouter":
            model_id = fm if fm in MODELS else fm  # alias or explicit slug, as given
        else:
            model_id = MODELS.get(fm, {}).get("id") or fm  # friendly name -> id, else assume id
        source += "+force_model"
        forced = True
    return {
        "agent": agent, "task": task, "tier": tier, "source": source,
        "model": model_id, "effort": spec["effort"], "rationale": spec["why"],
        "forced_model": forced, "provider": provider, "keep_main_loop_fixed": True,
    }


def estimate(tier: str, in_tokens: int, out_tokens: int) -> dict:
    """Cost of a call at this tier vs running it on Opus — the savings the router buys."""
    spec = TIERS.get(tier, TIERS[DEFAULT_TIER])
    m = MODELS[spec["model"]]
    cost = (in_tokens / 1e6) * m["in"] + (out_tokens / 1e6) * m["out"]
    opus = MODELS["opus"]
    opus_cost = (in_tokens / 1e6) * opus["in"] + (out_tokens / 1e6) * opus["out"]
    out = {"tier": tier, "model": m["id"], "usd": round(cost, 4),
           "usd_if_opus": round(opus_cost, 4), "saved_usd": round(opus_cost - cost, 4)}
    if active_provider() == "openrouter":
        out["note"] = ("backend is OpenRouter: estimates assume Anthropic first-party pricing; "
                       "actual cost depends on the mapped models (see openrouter.ai/models)")
    return out


def show() -> dict:
    return {"models": MODELS, "tiers": TIERS, "agent_tier": AGENT_TIER,
            "override_policy": load_policy(), "policy_path": POLICY_PATH}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Claude SEO Pro model-routing policy")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("route"); r.add_argument("--agent"); r.add_argument("--task")
    sub.add_parser("show")
    e = sub.add_parser("estimate"); e.add_argument("--tier", required=True)
    e.add_argument("--in", dest="intok", type=int, default=0); e.add_argument("--out", type=int, default=0)
    s = sub.add_parser("set"); s.add_argument("--agent"); s.add_argument("--tier")
    s.add_argument("--force-tier"); s.add_argument("--force-model"); s.add_argument("--main-loop")
    sub.add_parser("reset")
    args = ap.parse_args(argv)

    if args.cmd == "route":
        print(json.dumps(route(agent=args.agent, task=args.task), indent=2))
    elif args.cmd == "show":
        print(json.dumps(show(), indent=2))
    elif args.cmd == "estimate":
        print(json.dumps(estimate(args.tier, args.intok, args.out), indent=2))
    elif args.cmd == "set":
        pol = load_policy()
        if args.force_tier:
            if args.force_tier not in TIERS:
                print(f"[x] unknown tier {args.force_tier}; choices: {list(TIERS)}"); return 1
            pol["force_tier"] = args.force_tier
        if args.force_model:
            fm = args.force_model
            if fm not in MODELS and fm not in {m["id"] for m in MODELS.values()}:
                print(f"[x] unknown model {fm}; choices: {list(MODELS)} or a full model id"); return 1
            pol["force_model"] = fm
        if args.main_loop:
            pol["main_loop_model"] = args.main_loop
        if args.agent and args.tier:
            if args.tier not in TIERS:
                print(f"[x] unknown tier {args.tier}; choices: {list(TIERS)}"); return 1
            pol.setdefault("agent_tier", {})[args.agent] = args.tier
        save_policy(pol)
        print(f"[+] policy updated -> {POLICY_PATH}")
        print(json.dumps(pol, indent=2))
    elif args.cmd == "reset":
        if os.path.exists(POLICY_PATH):
            os.remove(POLICY_PATH)
        print("[+] policy reset to defaults")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
