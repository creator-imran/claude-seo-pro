# Audit Report Template — the depth contract (MANDATORY)

> Every full audit MUST produce a client-grade report matching the depth of the
> reference report (Strokes Exhibits v2+v3, June 2026 — the gold standard this
> template was extracted from). A report that compresses categories into a summary
> page (the "BayOne v1 problem") does not meet the contract. Use the HTML skeleton at
> `assets/report-template.html` (exact styling + placeholders), fill EVERY section
> below, then convert to PDF.

## Hard rules

1. **Every section below is REQUIRED**, in this order. A section whose data source is
   unavailable is rendered as **"Data pending"** with the exact error/cause and the
   unlock step — never omitted silently, never estimated.
2. **Every number cites its source** (evidence file:line, API response file, or named
   field). Tables carry a `Source:` line.
3. **Minimum table depth** is specified per section — these are floors, not targets.
4. **Findings are cards**, not bullets: severity tag + title + explanation + evidence
   block (verbatim code/selector/line) + fix + source line.
5. **Balance**: the report must contain a "What's genuinely strong" section — a
   findings-only report reads as a hit job and loses client trust.
6. **PDF output is part of the deliverable** (see §Generation), saved where the user
   can find it (Desktop or the audit output dir — tell them the path).

## Required sections & minimum depth

### 1. Cover (full page)
Client name, domain, "evidence-verified" method statement, prepared-for (with client
address if known), prepared-by, report version + date, supersedes-note if a prior
report exists.

### 2. Data Integrity & Methodology (full page)
- How the evidence was gathered: pages captured (count, all-200 confirmation),
  sitemaps/robots, CrUX field data, which live APIs (with call count + total cost).
- **Model backend line (mandatory):** state which backend produced this audit —
  `Model backend: Anthropic first-party` or
  `Model backend: OpenRouter — opus→…, sonnet→…, haiku→…`
  (read it from `python tools/switch_provider.py status`). Transparency about what
  generated the analysis is part of the evidence discipline; the linter warns if absent.
- **Pending-data policy stated up front** + a warn-callout per pending section
  (exact error code, e.g. `40204 backlinks subscription required`, and the unlock).
- Method notes: locations/language codes used, API quirks encountered (disclosed,
  not hidden).

### 3. Executive Summary (full page)
- Narrative paragraph: the strategic story in ≤120 words (pattern, root causes).
- **4 KPI cards** (the four most decision-relevant numbers).
- **Big score block** (N/100) + one-line scope note (what's included/excluded).
- **Full category scorecard** with bars — every weighted category + pending rows
  rendered as PENDING (greyed), with weights shown.
- "The five highest-leverage moves" — numbered, each tied to data.

### 4. Priority Issues (1–2 pages)
≥5 finding cards (Critical/High first). Each card: severity tag · title ·
2–4 sentence explanation · **evidence block** (verbatim selector/line/snippet) ·
concrete fix · source line.

### 5. What's Genuinely Strong (good-callout block)
≥4 verified strengths with evidence. Mandatory — see Hard rule 5.

### 6. Organic Search Visibility — Live data tag
- ETV + total keywords line.
- **Position-distribution table**: #1 / 2–3 / 4–10 / 11–20 / 21–30 buckets, each with
  a "read" column interpreting it.
- **Top quick-wins table** (≥10 rows where data allows): keyword | pos | vol | KD |
  intent.
- Strategy-read callout: what the distribution means for THIS business.

### 7. Keyword Research — multi-market — Live data tag
- **Seed-themes-by-market table** (≥8 seeds × all detected markets, vol + CPC).
- **Competitor-gap table** (≥7 rows): keyword | vol | KD | opportunity type, vs a
  REAL direct competitor (junk domains filtered — social/directories/platforms).
- **Opportunity tiers** list (quick wins / page-2-3 rescue / gap / secondary markets)
  with counts.
- Market-reality honesty: if a detected market has thin demand, say so.

### 8. Local SEO & GBP — Live data tag *(when `is_local_business`; else one line stating why skipped)*
- 4 KPI cards (rating, reviews, photos, categories).
- **Field-by-field GBP table** (≥8 fields) with per-field assessment tags.
- Cross-source NAP consistency callout (site schema vs GBP vs citations).
- Local action priorities.

### 9. Competitive Landscape — Live data tag
- **Competitor table** (≥7 rows): domain | shared keywords | type — with direct
  competitors tagged vs directories/platforms/venues classified.
- Read-callout: what the competitive field tells us.

### 10. On-Page Detail — PER-PAGE table
- **One row per audited money page (ALL of them, not a sample)**: page | title(len) |
  meta desc(len) | H1 | issues.
- Below the table: duplicate/cannibalization analysis, multi-H1 list, boilerplate-
  description patterns, items confirmed clean.

### 11. Performance Detail — Field vs Lab
- **Field table** (CrUX p75): LCP/INP/CLS/FCP/TTFB × mobile/desktop + verdict row.
- **Lab table**: perf score, LCP, CLS, TBT, SI × mobile/desktop.
- Diagnosis callout: the single highest-impact fix, **lab artifacts explicitly
  labelled** (never presented as field truth), culprit selectors where available.

### 12. Per-category detail — Content & E-E-A-T · Schema · AI Readiness
One subsection each (these are where the specialist agents' depth lands — do NOT
compress them into the exec summary):
- **Content & E-E-A-T**: author/byline status, leadership/trust signals, content
  depth word counts per page type, blog quality + intent alignment, top E-E-A-T gaps.
- **Schema**: per-page-type schema presence table, entity consistency, validation
  errors, top 5 opportunities.
- **AI Readiness**: crawler policy posture, llms.txt status (factual, not overstated),
  citability assessment, entity clarity, platform-specific notes.

### 13. Prioritised Action Plan (full page)
- **Quick-wins table**: # | action | effort | why (data-backed).
- **Strategic table**: same columns, compounding-return items.
- **Sequencing paragraph** (incl. the ~28-day CrUX re-measure note).
- **Data-to-unlock list** for pending sections.

### 14. Appendix — call log & integrity (full page)
- **API call-log table**: data class | endpoints | status (OK / Pending+code).
- **Integrity controls** list: what was verified how, junk filtered, quirks disclosed.
- Evidence corpus summary; corrections-vs-prior-report table when one exists.
- Footer: client · version · date · method · score · pending note.

## Generation

0. **Load white-label branding first:** run `python onboarding/branding.py show` (or read
   `~/.config/claude-seo/branding.json`). Substitute the cover/footer/preparer and the three
   CSS color tokens (`--brand`, `--brand2`, `--accent`) with the returned values. If no
   branding.json exists, the template's defaults ARE the neutral product branding — leave
   them. This is what lets an agency resell reports under its own brand without editing the
   template.
1. Copy `assets/report-template.html` to the audit output dir; replace every
   `{{PLACEHOLDER}}`; delete comment blocks of inapplicable conditional sections
   (e.g. Local/GBP for non-local businesses — replace with the one-line skip note).
2. Convert to PDF (Windows): headless Edge —
   `msedge --headless --disable-gpu --no-pdf-header-footer --print-to-pdf="<out>.pdf" "file:///<abs-path>.html"`
   (macOS/Linux: `chrome --headless` equivalent). WeasyPrint via
   `scripts/google_report.py` is an alternative when its deps are installed.
3. Name it `<domain>-seo-audit-<YYYY-MM>.pdf`, place it where the user will find it,
   and state the path in your summary.
4. Self-check before delivering — run the deterministic contract linter:
   `python tools/lint_report.py <report>.html` (from the repo) — it FAILS on missing
   sections, leftover `{{PLACEHOLDERS}}`, and summary-only compression, and warns on
   depth-floor shortfalls. **A FAIL means the report must not be delivered.** Then walk
   the content itself: a sourceless number is a defect, not a style choice.
