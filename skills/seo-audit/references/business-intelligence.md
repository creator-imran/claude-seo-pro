# Phase 0 — Business Intelligence (run FIRST, before any audit work)

> New in Claude SEO Pro. The moment a user runs a full audit, **before** crawling for
> SEO issues, Claude builds a structured understanding of the business. Everything
> downstream — which markets to research keywords in, which ICPs to evaluate intent
> for, whether local/GBP even applies — depends on this. A keyword report for the
> wrong country or persona is worse than none.
>
> This phase is **autonomous**: infer silently, write the profile artifact, and
> continue into the audit + keyword research without pausing. Surface the inferred
> profile in the final report's opening section so the manager can sanity-check it.

## Step 0a — Read the client knowledge store FIRST (persistent memory)

Before deriving anything, check what the system already knows about this client — that
memory survives across sessions and model switches (see the `seo-knowledge` skill):
```
python ~/.claude/skills/seo/knowledge/store.py recall <domain>
```
- **If knowledge exists:** start the business profile *from it* (don't re-derive from
  scratch); confirm/refresh fields against the current site rather than reinventing them.
- **If it's a first engagement:** build the profile fresh (below), then write it back.

Likewise, before any expensive API pull, prefer the data cache (provenance-tracked,
provider/op/date-keyed) so repeat audits don't re-pay for unchanged data:
`DataCache(provider).get_or_call(op, params, fetch, ttl_seconds=...)`.

## Inputs Claude reads (evidence-first, per the Evidence Integrity Protocol)

1. The pre-fetched homepage + key pages already on disk (never re-fetch / never guess).
2. Specifically mine: `<title>`, meta description, H1/H2s, hero copy, nav labels,
   footer (addresses, phones, registration numbers), `/about`, `/contact`,
   `/services`, `/our-company`, client/logo strips, testimonials, schema JSON-LD
   (Organization/LocalBusiness `address`, `areaServed`, `sameAs`), language/`hreflang`,
   currency and phone country codes, shipping / service-area statements.
3. If DataForSEO is available: `business_data` listing + `dataforseo_labs` ranked
   keywords give the *observed* country/language footprint to corroborate inference.

## What Claude infers (LLM reasoning, grounded in the above)

Produce a `business-profile.json` (write to the audit output dir) with these fields.
Every non-trivial field carries a `confidence` (high/medium/low) and the `evidence`
(file + snippet) it rests on — unsupported inferences are marked `low` and flagged,
never asserted.

```json
{
  "brand": "Strokes Exhibits",
  "legal_name": "Strokes Exhibits LLC",
  "one_line": "B2B exhibition-stand design & build contractor",
  "business_model": "B2B services",            // B2B | B2C | B2B2C | marketplace | SaaS | ecommerce | publisher
  "industry": "exhibition stand contractor",
  "industry_vertical": "events / experiential marketing",
  "country_of_origin": {"name": "United Arab Emirates", "code": "AE", "confidence": "high",
                         "evidence": "footer address 'Al Jaddaf, Dubai'; +971 phone; AED"},
  "primary_language": "en",
  "languages_observed": ["en", "ar"],
  "target_markets": [                            // ordered by inferred priority
    {"name": "United Arab Emirates", "code": "AE", "why": "HQ + most service pages", "confidence": "high"},
    {"name": "Saudi Arabia", "code": "SA", "why": "Riyadh/Jeddah service+blog pages", "confidence": "medium"},
    {"name": "Qatar", "code": "QA", "why": "Gulf event coverage", "confidence": "low"}
  ],
  "icps": [                                      // ideal customer profiles / segments
    {"name": "Enterprise exhibitors at Dubai trade shows", "needs": ["custom stands","turnkey build"],
     "buyer_role": "marketing/events manager", "confidence": "high"},
    {"name": "Overseas pavilion organizers", "needs": ["country pavilions","logistics"], "confidence": "medium"}
  ],
  "services_or_products": ["custom stands","modular stands","double-deck","pavilions","graphics","installation"],
  "is_local_business": true,                     // has a physical premises / service area -> triggers local+GBP
  "service_area": ["Dubai","Abu Dhabi","UAE","KSA"],
  "competitors_named_on_site": [],
  "differentiators": ["20+ yrs","45,000 sqft facility","IAEE/IFES member","Airbus/Samsung clients"],
  "seed_keyword_themes": [                        // feeds Phase: Keyword Research
    "exhibition stand contractor","exhibition stand design","trade show booth",
    "double deck exhibition stand","modular exhibition stand","country pavilion","stand builder"
  ],
  "notes_for_audit": ["programmatic Riyadh/event blog set — check thin-content risk"]
}
```

## How to reason well here (LLM guidance)

- **Country of origin ≠ only target market.** Read shipping/areaServed/currency/phone
  codes and language variants. A Dubai firm with Riyadh service pages is targeting KSA
  too — capture it as a target market (drives multi-locale keyword research).
- **Model dictates intent.** B2B → research commercial / transactional + comparison
  terms and longer-tail; B2C local → "near me", city-modified; ecommerce → product +
  category + "buy". Set `seed_keyword_themes` accordingly.
- **Decide `is_local_business` deliberately.** Physical premises, service area, GBP
  signals, "near me" relevance → true → the audit MUST run the Local SEO + GBP phase.
  Pure-online SaaS/publisher → false → skip local, note why.
- **ICPs drive persona scoring** later (seo-sxo) and the keyword *intent* filter.
- **Stay evidence-bound.** If the site doesn't reveal a target market, don't invent
  one — mark `low` confidence or omit. The profile is a hypothesis set, labelled as such.

## Output of Phase 0

0. **Write back to the knowledge store** so the next session/model starts informed:
   `store.py set-profile <domain> --file business-profile.json`, append notable findings
   as evidence-tagged facts (`add-fact`), and record the audit score (`add-history`).
1. `business-profile.json` on disk (consumed by Keyword Research + Local/GBP phases).
2. A short "Business Understanding" block reproduced at the top of the final report:
   model, country, target markets, ICPs, and the seed themes — each tagged with
   confidence — so the SEO manager can correct a wrong inference in one glance.

Then proceed automatically to the templatized audit (`audit-playbook.md`),
the keyword research (`keyword-research.md`), and — if `is_local_business` —
the local/GBP phase (`local-gbp-audit.md`).
