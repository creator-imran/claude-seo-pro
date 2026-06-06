---
name: seo-learn
description: "Run a client-business learning pass. Reads audit evidence and distills durable, evidence-tagged facts about the client into the persistent knowledge store, making the system more well-versed in that client over time. Use when the user says learn about this client, update what we know, learning pass, study the client, or /seo-learn. Runs automatically at the end of a full audit."
user-invokable: true
argument-hint: "[domain]"
license: MIT
metadata:
  author: creator-imran
  version: "1.0.0"
  category: seo
---

# Client Learning Pass

Turns what an audit discovered into durable, evidence-backed **memory** about the client
(stored via the `seo-knowledge` layer). This is how the system gets smarter about each
client over time rather than starting cold every audit.

## When this runs
- **Automatically** as the final write-back step of a full `/seo audit` (the orchestrator
  dispatches the `seo-learn` agent).
- **On demand** via `/seo-learn <domain>` — useful after you've gathered new material,
  or to refresh memory without a full audit.

## How to run it (orchestrator / manual)
1. **Dispatch the learning agent** (`agents/seo-learn.md`). Point it at the client's
   evidence corpus + `business-profile.json` + the audit outputs. It reads the *current*
   knowledge first so it doesn't relearn what's known and can correct what's stale.
2. The agent emits a **candidate-facts JSON array** (each fact carries evidence +
   confidence + source; transient metrics and secrets are excluded).
3. **Preview, then commit** (review-then-write):
   ```
   ! python ~/.claude/skills/seo/knowledge/learn.py preview --domain <domain> --file candidates.json
   ! python ~/.claude/skills/seo/knowledge/learn.py ingest  --domain <domain> --file candidates.json
   ```
4. Record the audit score on the timeline:
   ```
   ! python ~/.claude/skills/seo/knowledge/store.py add-history <domain> --score <n> --note "<tag>"
   ```

## What gets learned (and what doesn't)
- **Durable facts** (stored): business model, services, differentiators, confirmed target
  markets, ICPs, competitors, key events, named experts, content patterns, per-market
  demand reality — each with its evidence.
- **Not stored as facts:** transient metrics ("score is 61", "ranks #4 today") → those go
  to history; unsourced guesses → only as `low` confidence; anything secret → rejected.

## Integrity & hygiene
- Every fact is evidence-tagged; unsourced → `low`, flagged (never asserted).
- Stale beliefs are **superseded** (via `replace_tag`), not left to contradict — so the
  memory gets *more* accurate, not just bigger.
- Preview before ingest so you can veto junk before it enters memory.

## See it work
After a pass, confirm what the system now knows:
```
! python ~/.claude/skills/seo/knowledge/store.py recall <domain>
```
