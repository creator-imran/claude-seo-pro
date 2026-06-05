# Keyword Research — full DataForSEO suite (Audit Report section)

> New in Claude SEO Pro. Every full audit ends with an **intensive, brand-specific
> keyword research** section. It is driven by `business-profile.json` from Phase 0
> (seeds, country of origin, target markets, ICPs) and executed across the **full
> DataForSEO capability set**, then synthesized into prioritized recommendations with
> Global Volume, per-Country Volume, CPC, Keyword Difficulty, intent, and SERP features.

## Locale coverage

Run for the **country of origin + every detected target market** (multi-locale), in
each market's relevant languages. Example (Strokes, Dubai): UAE (en, ar), KSA (en, ar),
Qatar (en). Use DataForSEO `location_code` + `language_code` per market
(`serp_locations` / `kw_data_google_ads_locations` resolve codes). Global volume comes
from the worldwide aggregate; country volume from each location run.

## The suite (orchestrated by `scripts/keyword_research.py`)

The script fans out across these DataForSEO endpoints and merges them into one
normalized keyword table. Stages:

1. **Seed expansion** (breadth):
   - `dataforseo_labs_google_keyword_ideas` — ideas from seed themes
   - `dataforseo_labs_google_keyword_suggestions` — long-tail "contains seed"
   - `dataforseo_labs_google_related_keywords` — semantic "searches related to"
   - `keywords_data_google_ads_keywords_for_keywords` — Ads-network expansion
2. **Site & competitor mining** (relevance + gap):
   - `dataforseo_labs_google_keywords_for_site` — what the brand already ranks for
   - `dataforseo_labs_google_ranked_keywords` — current positions (quick wins = pos 4–20)
   - `dataforseo_labs_google_competitors_domain` — organic competitors
   - `dataforseo_labs_google_domain_intersection` — keywords competitors rank for but the brand doesn't (the gap)
3. **Metrics enrichment** (decision data) for the merged set:
   - `keywords_data_google_ads_search_volume` — volume, CPC, competition (global + per location)
   - `dataforseo_labs_bulk_keyword_difficulty` — KD (0–100)
   - `dataforseo_labs_google_search_intent` — informational/navigational/commercial/transactional
   - `keywords_data_dataforseo_trends_explore` — trend/seasonality
   - `dataforseo_labs_google_keyword_overview` — consolidated metrics + SERP features fallback
4. **SERP context** (winnability) for top candidates:
   - `serp_organic_live_advanced` — who ranks, SERP features (AI Overview, PAA, local pack, shopping)
5. **AI-search demand** (optional, if AI_OPTIMIZATION enabled):
   - `ai_optimization_keyword_data_search_volume` — AI-surface keyword volume

## Output: normalized keyword table

One row per keyword, merged across stages and markets:

| Field | Source |
|---|---|
| keyword | seed expansion |
| global_volume | Ads search_volume (worldwide) |
| country_volume{AE,SA,QA…} | Ads search_volume per location |
| cpc | Ads search_volume |
| competition (0–1) | Ads search_volume |
| keyword_difficulty (0–100) | Labs bulk_keyword_difficulty |
| search_intent | Labs search_intent |
| trend_12mo | trends_explore |
| serp_features | SERP advanced (AI Overview / PAA / local pack / shopping) |
| brand_current_rank | ranked_keywords (blank if unranked) |
| opportunity_tier | derived (see below) |

`scripts/keyword_research.py` writes `keyword-research.json` (full data) and
`KEYWORD-RESEARCH.md` (the report section). It runs `--plan` first to print the call
plan + estimated cost, then executes. **Cost note:** DataForSEO charges per call;
multi-locale × full suite is the most expensive part of the audit — the script logs
calls made and credits consumed, and never silently caps coverage.

## Opportunity tiering (how Claude turns data into recommendations)

Classify each keyword, then recommend by tier — don't just dump a list:

- **Quick wins:** brand_current_rank 4–20 AND volume meaningful AND KD ≤ market median.
  "You're on page 1–2; targeted on-page + internal links can move these fast."
- **Strategic targets:** high volume + high commercial/transactional intent, KD moderate,
  brand unranked → new/upgraded money pages.
- **Gap captures:** from domain_intersection — competitors rank, brand doesn't.
- **Long-tail / quick content:** low-KD, specific intent, lower volume → blog/FAQ fodder,
  good for AI-citation passages.
- **Demand to monitor:** rising trend but low current volume.

For each recommended keyword give: the metric row, the **intent-matched page type**
(from SXO logic), and whether it's a new page vs an existing page to optimize.

## Report section shape (`KEYWORD-RESEARCH.md`)

1. **Markets & method** — locales run, seeds used, endpoints called, credits spent.
2. **Headline opportunities** — top 10–20 by opportunity, full metric table.
3. **By tier** — quick wins / strategic / gap / long-tail tables.
4. **By ICP** — keywords mapped to the Phase-0 personas they serve.
5. **Per-market breakdown** — origin + each target market, with that market's volume/CPC/KD.
6. **Content/architecture implication** — clusters + which pages to create or optimize
   (hand off to seo-cluster / seo-content-brief if deeper planning is wanted).

## Honesty rules (Evidence Integrity Protocol applies here too)

- Every number is a real DataForSEO field — no invented volumes/KD/CPC.
- If DataForSEO is unconfigured or IP-blocked (40207), this section is **"Data pending —
  requires DataForSEO"**, not estimated. Tell the user exactly how to unblock.
- Distinguish Ads "search volume" (rounded ranges, Google Ads source) from clickstream
  estimates; state the source.
