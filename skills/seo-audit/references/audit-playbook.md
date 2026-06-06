# Audit Playbook — templatized checks + smart LLM orchestration

> The reusable "what to look for and how" for a full audit. Phase 0
> (`business-intelligence.md`) runs first; this playbook is the main audit body.
> It is deliberately a **template**: each category has a fixed checklist so coverage
> is consistent across clients and nothing is silently skipped.

## Orchestration model (how to use the LLM efficiently)

1. **Main session = the evidence broker.** It pre-fetches all pages to disk, writes
   `business-profile.json`, then dispatches specialists. Specialists read local files
   only (Evidence Integrity Protocol). This is what keeps the audit cheap *and* honest.
2. **One specialist per dimension, in parallel.** Dispatch the agents below
   concurrently; each returns structured findings with `file:line` evidence and
   confidence tags. Don't run them sequentially — they're independent.
3. **Model tiering (cost-aware) — driven by the router (Feature 3).** Don't guess the
   model per task; ask the routing policy and spawn the subagent on what it returns:
   ```
   python ~/.claude/skills/seo/routing/model_router.py route --agent <specialist>
   ```
   | Task | Tier → model | Why |
   |---|---|---|
   | Mechanical extraction (titles, metas, status codes, alt text, schema presence) | extraction → Haiku | Pattern work; cheap, fast, parallel-friendly |
   | Reasoned judgement (E-E-A-T, intent match, SXO personas, business profile, learning) | reasoning → Sonnet | Needs synthesis + nuance |
   | Adversarial verification of a Critical/High finding | verification → Sonnet | Independent skeptic |
   | Final synthesis + prioritization + report | synthesis → Opus | Cross-dimension reasoning, dependency ordering |
   | The orchestrator / main loop | orchestration → Opus (**fixed**) | Switching the main model invalidates the prompt cache — keep it fixed; route only sub-work |
   Pre-fetching means even the cheap tier can't hallucinate — it's reading real files. The
   manager can inspect/override the policy via `/seo-models` (e.g. `--force-tier opus` for a
   flagship report).
4. **Adversarial verification on Critical/High findings.** Before a finding ships as
   Critical or High, a second pass tries to *refute* it from the same evidence. If it
   can't be refuted, it ships; if the evidence is ambiguous, it's downgraded or marked
   "Data pending". (This is the structural fix for the v1 fabrication incident.)
5. **No silent truncation.** If the crawl capped, a fetch failed, or a section needs
   an API that isn't configured, the report says so explicitly.

## Specialist dispatch matrix

| Specialist (agent) | Always? | Trigger | Loads |
|---|---|---|---|
| seo-technical | yes | — | robots, sitemaps, canonicals, status codes, security, mobile, JS |
| seo-content | yes | — | E-E-A-T, depth, thin/dupe, readability, helpfulness (QRG) |
| seo-schema | yes | — | JSON-LD from RAW html (grep `ld+json`), validity, coverage, deprecated types |
| seo-sitemap | yes | — | structure, redirecting/non-canonical URLs in sitemaps |
| seo-performance + seo-google | yes | Google key present | **CrUX field data** for CWV, not lab estimates |
| seo-geo | yes | — | AI-crawler policy, llms.txt, passage citability, entity presence |
| seo-sxo | yes | — | page-type vs intent mismatch, persona scoring against ICPs |
| **keyword research** | yes | DataForSEO present | full DataForSEO suite — see `keyword-research.md` |
| **seo-local + seo-maps** | conditional | `business-profile.is_local_business == true` | GBP, NAP, citations, reviews, map-pack — see `local-gbp-audit.md` |
| seo-backlinks | conditional | DataForSEO/Moz/Bing present | referring domains, anchors, toxicity, gap |
| seo-ecommerce | conditional | model == ecommerce | product schema, shopping, marketplace |
| seo-drift | conditional | baseline exists for URL | regression vs last snapshot |
| **seo-learn** | always (write-back) | runs LAST | distills durable client facts → knowledge store (Feature 2) |

## Per-category checklist templates

Each specialist returns findings against its template; the orchestrator aggregates.
Findings format: `severity | title | evidence(file:line / API field) | confidence | fix | effort`.

### Technical
- [ ] robots.txt: crawl directives, AI-bot policy, **contradictory groups** (e.g. duplicate UA Allow/Disallow), `Sitemap:` directive present
- [ ] Sitemaps: index resolves, child counts, **no 301/non-canonical/blocked URLs listed**
- [ ] Canonical: present, self-referencing, host (www vs non-www) consistent, no double-slash
- [ ] Indexability: meta robots, noindex audit, status codes (manifest.csv: any non-200)
- [ ] HTTPS, HSTS, mixed content, security headers
- [ ] Mobile: viewport, tap targets; charset, `lang`, hreflang (if multi-locale)
- [ ] JS rendering: is primary content/schema in raw HTML or JS-only?

### Content & E-E-A-T
- [ ] Named authors/experts with bios (not first-name-only schema bylines)
- [ ] Experience signals: original research, case studies, first-hand media
- [ ] Trust: NAP visible, HTTPS, dates, corrections; YMYL handling if applicable
- [ ] Depth per page (unique body words); thin pages; programmatic/doorway sets
- [ ] Helpfulness (QRG Who/How/Why); AI-mass-produced patterns
- [ ] Authority: marquee clients/logos surfaced to search (alt text!), memberships, awards

### Schema
- [ ] Grep RAW html for `application/ld+json` AND `ld+json` (catch unquoted Rank Math)
- [ ] Entity type correct (Organization vs LocalBusiness/ProfessionalService for local)
- [ ] Per-template coverage (Service/Product/Article/FAQ/Breadcrumb) consistent across page types
- [ ] Field validity: addresses (no trailing-dash artifacts), logo filename, geo/hours
- [ ] Deprecated types flagged (HowTo, etc.); FAQ restricted-eligibility check

### Performance (field-first)
- [ ] CrUX field p75 LCP/INP/CLS mobile+desktop → pass/fail (this is the ranking truth)
- [ ] TTFB share of LCP (server vs render bottleneck)
- [ ] Label lab artifacts as lab-only (e.g. throttled CLS) — never present as field truth

### AI Search / GEO
- [ ] AI-crawler policy coherence (Allow/Disallow conflicts), llms.txt presence
- [ ] Passage citability (self-contained 134–167-word answers), question headings
- [ ] Entity presence (Wikipedia/Reddit/YouTube/LinkedIn), attribution density

### SXO (against ICPs from Phase 0)
- [ ] Page-type vs dominant SERP intent for each money keyword
- [ ] Score key pages from each ICP persona's perspective; flag intent mismatch

## Scoring

Score only categories backed by live evidence. Categories needing an absent API are
**"Data pending"** and excluded from the composite (not estimated). Report the
composite as "on-site health" when off-site (backlinks/local/rankings) is pending,
and re-score once those land. State the exclusion explicitly.

## Report assembly order

**The report MUST follow `references/report-template.md` — the depth contract** (14
required sections extracted from the gold-standard Strokes Exhibits report), rendered
with the HTML skeleton at `assets/report-template.html` and delivered as a PDF. The
contract's floors are mandatory: per-page on-page table for ALL audited money pages,
position-distribution + ≥10-row quick-wins tables, multi-market seed table, competitor
gap table, field-vs-lab performance tables, per-category detail sections (Content,
Schema, AI-readiness), a "What's genuinely strong" section, the action plan, and the
API call-log appendix. A compressed summary-only report is a contract violation.

Section order: Cover → Data Integrity & Methodology → Executive summary (KPIs + score
+ scorecard + 5 moves) → Priority issues (adversarially verified, evidence cards) →
Strengths → Organic Visibility → **Keyword Research** → **Local SEO / GBP** (if
applicable; else a one-line skip note) → Competitive Landscape → On-Page detail →
Performance detail → per-category detail → action plan → appendix (call log, integrity
controls, corrections vs any prior report).

**Final write-back (always).** After the report is assembled, dispatch the **seo-learn**
agent to distill durable, evidence-tagged client facts into the knowledge store, supersede
any stale beliefs, and record the audit score on the history timeline (Feature 2 — see
`skills/seo-learn`). This is what makes the *next* audit start informed rather than cold.
