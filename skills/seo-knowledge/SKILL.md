---
name: seo-knowledge
description: "Persistent, model-independent client knowledge for Claude SEO Pro. Recall what we know about a client, record new facts, and cache expensive API results across sessions and model switches. Use when the user says recall, what do we know about, remember this about the client, client memory, knowledge, or /seo-knowledge. The full audit reads and updates this automatically."
user-invokable: true
argument-hint: "[recall|remember|history|cache-stats] <domain> ..."
license: MIT
metadata:
  author: creator-imran
  version: "1.0.0"
  category: seo
---

# Client Knowledge & Data Cache

This is the system's long-term memory about each client. It persists across **new
sessions and model switches** — unlike Anthropic's prompt cache, which is ephemeral and
model-scoped. Any model, any session, reads the same client knowledge to start informed.

**Where it lives (owner-only, never in the repo):** `~/.config/claude-seo/clients/<slug>/`
and `~/.config/claude-seo/cache/`. Engine: `~/.claude/skills/seo/knowledge/`.

> **Why this isn't the prompt cache.** Switching Claude models invalidates the prompt
> cache (it's model-scoped, ~5-min TTL) — but that cache is a cost optimisation, not
> memory. This store is real persisted knowledge + cached data on disk, independent of
> any model. That's what lets a Haiku extraction subagent and an Opus synthesis step
> share the same understanding of the client.

## What it stores (per client)
- **profile.json** — stable business understanding: model, country of origin, target
  markets, ICPs, seed keyword themes, `is_local_business`. Seeded from Phase-0
  `business-profile.json`; merge-updated each audit.
- **facts.jsonl** — append-only learned facts, each with **evidence + confidence +
  source** (Evidence Integrity: an unsourced fact is stored as `low` confidence, never
  asserted as fact).
- **history.jsonl** — audit/score timeline, so you can show progress over time.
- **cache/** — expensive API results (DataForSEO, PSI/CrUX, fetched HTML) keyed by
  params + date, with provenance, so repeat audits don't re-pay for unchanged data.

## Commands

### `recall <domain>` — what do we know?
Run and present the briefing:
```
! python ~/.claude/skills/seo/knowledge/store.py recall <domain>
```
Use `--json` for the structured form. If nothing is stored, it says "first engagement".

### `remember <domain>` — record a fact
Tell the user the fact will be stored with its evidence and confidence, then run:
```
! python ~/.claude/skills/seo/knowledge/store.py add-fact <domain> --text "..." --evidence "..." --confidence high --source "<where it came from>"
```
**Never store an unsourced claim as `high`** — leave `--evidence` empty and it's recorded
as `low` automatically. Don't put secrets in facts.

### `history <domain>` — score/audit timeline
`recall --json` includes `history`; summarise the score trend for the user.

### `cache-stats` / `cache-purge`
```
! python ~/.claude/skills/seo/knowledge/cache.py stats
! python ~/.claude/skills/seo/knowledge/cache.py purge --older-than-days 30
```

## How the audit pipeline uses this (automatic)

1. **Phase 0 — read first.** At the start of a full audit, run `store.py recall <domain>`.
   If knowledge exists, start the business-intelligence step *from it* (don't re-derive
   from scratch); if not, it's a first engagement.
2. **Reuse cached data.** Before an expensive API pull, check the cache
   (`DataCache(provider).get_or_call(op, params, fetch, ttl_seconds=...)`). Cached data
   carries provenance and is cited as "DataForSEO/<op>, cached <date>" — still a real
   source, never a guess. An expired entry is a miss → re-fetch (no stale reads).
3. **Write back after.** Update `profile.json` with anything newly learned, append
   notable findings as facts (with evidence), and add the audit score to `history`.

## Integrity rules
- Facts and profile fields carry evidence + confidence; unsourced → `low`, flagged.
- Cached data is real API data with a citable timestamp; an expired entry is re-fetched.
- This store holds client business knowledge, **not secrets** — API keys stay in the
  credential files, never in profiles or facts.
- It's all owner-only and outside the repo; nothing here is committed.
