# Lap 2b pre-check — does NICE's search API expose the appraisal route?

**Question:** Lap 0 found the search service behind NICE's listing at
`search-api.nice.org.uk` and worked out its `om` filter array. Does it expose an
appraisal-process, route, or guidance-type facet that would hand over
cost-comparison / HST / fast-track directly — and make the Lap 3 route work cheap?

**Answer: no.** Three requests, cached under `data/raw/lap2b_api/`. Retrieved 20 Aug 2026.

## What the API does expose

The response carries a `navigators` array — the facets the site itself filters on. There are
**eight**, and every value in them is listed:

| Facet | Display name | Values |
|---|---|---|
| `ndt` | Type | Guidance · NICE advice · Quality standard |
| `ngt` | **Guidance programme** | 20 values — Technology appraisal guidance (1584), HealthTech guidance, Interventional procedures guidance, NICE guidelines, Clinical guidelines, **Highly specialised technologies guidance (37)**, … |
| `gst` | Status | Published (2586) · In development · Awaiting development · Topic prioritisation · In consultation · Deferred |
| `tt` | Prioritisation programme | None selected · Medicines evaluation · HealthTech · Interventional procedures · Guidelines · Quality standards |
| `aty` | HealthTech approach | Interventional procedure · Routine use · Early use · Existing use |
| `nat` | Advice programme | Medtech innovation briefings · Evidence summaries · NICE reviews |
| `nai` | Area of interest | Antimicrobial prescribing · COVID-19 |
| `tsd` | Decision | Not selected · Awaiting decision · Further information required · Not prioritised |

**None of them is the appraisal route.** There is no cost-comparison value, no fast-track value,
and no appraisal-process facet anywhere in the eight. `aty` is the closest-sounding — *HealthTech
approach* — and it applies to a different programme entirely.

## The one thing it settles

`ngt` lists **Highly specialised technologies guidance as its own programme, 37 items.** That
corroborates Lap 0 from a second direction: HSTs are not a *route within* technology appraisals,
they are a **separate programme with separate IDs**, so an `hst` value could never appear in the TA
spreadsheet or in this dataset. Of the four route values spec §9 asked for, one is definitionally
out of scope rather than merely missing.

## The document fields are emptier than the facets

Each result document carries **72 fields**, several of which sound decisive: `approachType`,
`publicationType`, `technologyType`, `consultationType`, `prioritisationProgramme`,
`niceResultType`, `terminatedDate`. Tallied across **all 927 published technology appraisals** the
API returns:

| Field | Populated |
|---|---|
| `approachType` · `publicationType` · `technologyType` · `consultationType` · `prioritisationProgramme` · `niceResultType` · `terminatedDate` · `evidenceTypes` · `primaryDrug` · `subject` | **0 / 927** |
| `guidanceStatus` | 927 / 927 — all `Published` |
| `publicationDate` · `lastUpdated` | 927 / 927 |

Every route-adjacent field is null on every published appraisal. The API returns a title, a URL, a
status and two dates — a strict subset of what Lap 2a already parsed from the overview pages, which
cover **1181** appraisals rather than 927.

## Consequences

- **`route` stays deferred.** Neither the spreadsheet (Lap 0), the overview page (Lap 2a), nor the
  search API (here) carries it. If it is anywhere in the open it is in chapter text or the
  committee papers — which is what Lap 2b's cache exists to let Lap 3 test, offline.
- **Nothing to re-plan.** The API is not a shortcut and not a better enumeration route; Lap 0
  already ruled out the syndication API on access grounds. The crawl stands as designed.
- **One number moved.** The published listing now returns **927**, where Lap 0 measured 925 five
  days ago — two new appraisals in a day and a half. The site moves and the spreadsheet trails it,
  which is why enumeration comes from the spine and every published figure carries a vintage stamp.

**Cost of this check: three requests and about five minutes.** Worth it — a route facet would have
made a chunk of Lap 3 free, and not checking would have left that assumption unexamined.
