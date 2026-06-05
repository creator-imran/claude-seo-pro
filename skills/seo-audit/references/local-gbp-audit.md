# Local SEO & Google Business Profile — audit phase

> New in Claude SEO Pro. The Strokes v2 audit shipped without a local/GBP section even
> though the client is a physical, local business — this phase closes that gap. It runs
> whenever Phase 0 sets `business-profile.is_local_business == true`.
>
> **Two-tier data sourcing (decided for this distribution):**
> 1. **Primary — client's Google Business Profile API** (first-party, owner-granted
>    OAuth). Deepest data: real impressions/calls/directions/bookings, profile
>    completeness, posts, Q&A.
> 2. **Fallback — DataForSEO via the `seo-maps` skill** (public map-pack/GBP data, no
>    ownership needed). Always available when DataForSEO is configured.
>
> If GBP OAuth isn't granted, run the fallback and clearly label the section
> "public-data tier (first-party GBP insights pending owner access)".

## Tier detection (at phase start)

```
python ~/.claude/skills/seo/onboarding/gbp_auth.py --check --json
```
- `configured: true`  → **Tier A (first-party)**: pull performance + profile via GBP API.
- `configured: false` → **Tier B (public)**: dispatch `seo-maps` (DataForSEO). If
  DataForSEO is also absent → **Tier 0**: on-page-only local signals via `seo-local`,
  everything else marked "Data pending — requires GBP OAuth or DataForSEO".

State the detected tier at the top of the section.

## Tier A — first-party GBP (owner access)

```
python ~/.claude/skills/seo/onboarding/gbp_auth.py --performance --location locations/<id> --days 30
```
Reports real metrics over the window:
- **Discovery:** impressions desktop/mobile × search/maps
- **Actions:** website clicks, call clicks, direction requests, bookings
- **Conversion read:** actions ÷ impressions; where customers act (search vs maps)

Combine with profile completeness (categories, hours, attributes, photos, products,
posts cadence, Q&A) and reviews. A 403 from the API means the OAuth account lacks
access to that location — report it and drop to Tier B (don't fabricate).

## Tier B — DataForSEO public (the seo-maps skill)

Dispatch `seo-maps` for the business + location. It already implements (do NOT
re-build): geo-grid rank tracking + Share-of-Local-Voice, GBP completeness audit
(25-field checklist with industry weights), review intelligence (velocity, the 18-day
rule, distribution, owner-response rate, fake-review signals), competitor radius
mapping, and cross-platform NAP. Show the geo-grid heatmap + SoLV.

## On-page local signals (always — the seo-local skill)

Independently of tier, dispatch `seo-local` on the pre-fetched HTML:
- NAP presence + consistency across pages (flag the trailing-dash class of artifact)
- LocalBusiness/ProfessionalService schema with geo + openingHours + areaServed
  (vs a bare Organization — a real finding from the Strokes audit)
- Location/service-area page quality; multi-location structure
- Local content depth; embedded map; click-to-call

## NAP consistency (cross-source)

Reconcile NAP across: on-page (seo-local), GBP (Tier A or B), and DataForSEO business
listings / other directories. Flag mismatches by severity: name (Critical), address
(High), phone (Medium). Note formatting inconsistencies (e.g. `+971 54 996 5467` vs
`+971 54 9965467`) and schema gaps (e.g. a landline missing from `contactPoint`).

## Local section output

1. **Tier detected** + what it covers / what's pending.
2. **GBP profile audit** — completeness score (field-by-field, industry-weighted).
3. **Performance** (Tier A only) — impressions/actions trend; conversion read.
4. **Reviews** — count, rating, velocity vs 18-day rule, response rate, distribution,
   fake-review flags.
5. **Map-pack visibility** (Tier B) — geo-grid heatmap, SoLV, top competitors in radius.
6. **NAP consistency** — cross-source table with severities.
7. **Local schema** — current vs recommended LocalBusiness JSON-LD (generated).
8. **Prioritized local actions** (Critical → Low), effort-tagged.

## New onboarding input this phase relies on

The `gbp` provider (Google Business Profile OAuth, `business.manage`) added to the
onboarding wizard. It is **deferrable** — skip → "attach later" → the phase runs Tier B
until the owner grants access. See `docs/ONBOARDING.md`.
