# Data dictionary — NICE technology appraisal recommendation spine (v1)

**Table:** `data/processed/nice_ta_recommendations_spine.{csv,parquet}`
**Grain:** one row per **recommendation**. 1531 rows across 1181 appraisals.
**Built by:** `python -m hta.cli build` — offline, from the cached spreadsheet.
**Source vintage:** `ta-recommendations_2026-08-19.xlsx`,
sha256 `04fa1864d0f2e49b3c767e77b6fad1f6f710023f54109cd749913dedac9f377a`, retrieved 2026-08-19.

The grain is the point. 1531 recommendations sit under 1181 appraisals because multi-technology
and multi-population appraisals split; **counting appraisals instead loses 350 recommendations
(23%)**. The appraisal is a parent key, not the unit of analysis.

Two rules hold throughout:

1. **Verbatim beside normalised, never instead of.** Every `*_raw` column is NICE's own text,
   unmodified. Every derived column sits next to its source so a reader who disagrees with a
   normalisation can redo it. This is also a licence condition — the NICE UK Open Content Licence
   forbids amending the wording of published recommendations.
2. **Nothing is invented.** A field NICE's file does not contain is absent, not guessed. See
   *Deliberately absent* below.

## Fields

| # | Field | Type | Source | Notes |
|---|---|---|---|---|
| 1 | `recommendation_id` | string | **derived** — `appraisal_id` + within-appraisal sequence | `TA1121-01`. Stable across rebuilds: the sequence follows NICE's own `Rec no.` order. Built on the *padded* published ID so it sorts as NICE's file does. Widest appraisal is TA081 with 16. |
| 2 | `recommendation_seq` | int | NICE `Rec no.` | Contiguous 1–1531. NICE's own recommendation key; unique, and the join key to the cancer companion file. |
| 3 | `appraisal_id` | string | NICE `TA ID` | Verbatim, **zero-padded to at least 3 digits** as published: `TA001`, `TA081`, `TA1181`. The parent key. 1181 distinct, numerically gapless TA1–TA1181 — a complete census, not a sample. |
| 4 | `appraisal_url` | string | **derived** — de-padded `appraisal_id` | `TA081` → `https://www.nice.org.uk/guidance/ta81`. The canonical URL is unpadded; the padded form resolves via 1–2 redirects, so building from it would cost ~1,200 avoidable round-trips in Lap 2. |
| 5 | `technology_raw` | string | NICE `Technology` | Free text, verbatim. The drug, device or procedure appraised. |
| 6 | `technology_type_raw` | string | NICE `Technology type` | 6 raw values. ⚠️ **Two are the same category**: `Medical device` (46) and `Medical Device` (1). Schema v1 specifies no normalised sibling, so it ships verbatim — **fold case before stratifying on it.** |
| 7 | `condition_raw` | string | NICE `Indication` | Free text, verbatim. One null in the source file, preserved as null. |
| 8 | `sta_mta_process_raw` | string | NICE `STA/MTA process` | 6 values. ⚠️ **This is not the appraisal route.** It carries single-vs-multiple technology and review status; there is no cost-comparison, HST or fast-track value in it anywhere. |
| 9 | `recommendation_category_raw` | string | NICE `Categorisation (for specific recommendation)` | 12 raw values, three of them pure case variants. The outcome, in NICE's words. |
| 10 | `nice_comments_raw` | string | NICE `Comment` | A short standardised rationale or status note, not commentary — *"Recommendation in line with marketing authorisation"*, *"Guidance has been replaced by TAxx"* (121 rows), *"Moved to static list"* (7). One null, preserved. A partial patient-access-scheme signal and a supersession signal both live here; **neither is extracted in Lap 1** and neither would have full recall. |
| 11 | `year_published_raw` | string | NICE `Year of Publication` | **Fiscal-year string** `1999/00`–`2026/27`, 28 distinct, no gap years. **Not a date and never coerced into one.** Real publication dates are on the guidance pages → Lap 3. |
| 12 | `process_type` | string | **derived** from field 8 | `STA` · `MTA`. Single- vs multiple-technology appraisal. |
| 13 | `review_type` | string | **derived** from field 8 | `original` · `review` · `part-review` · `rapid review`. An unqualified `STA`/`MTA` is `original`. |
| 14 | `outcome` | string | **derived** from field 9 | 9 values: `recommended` · `optimised` · `cdf_recommended` · `cdf_optimised` · `imf_recommended` · `imf_optimised` · `only_in_research` · `not_recommended` · `terminated_non_submission`. Mapping is exhaustive and **raises on an unseen category** rather than nulling it. Validated against NICE's published 87% — see below. |
| 15 | `terminated_flag` | bool | **derived** from field 14 | `outcome == terminated_non_submission`. n=174 (11.4%). Exact and categorical in the source — no listing-text parsing. Never null. |
| 16 | `is_cancer` | bool | **NICE cancer companion file** — `ta-cancer-recommendations_2026-08-19.xlsx`, sha256 `593564f4…`, joined on `(TA ID, Rec no.)` | n=662 (43%). NICE-authored, not inferred: the companion has identical columns and its rows are an exact subset of the main file. `False` where absent, never null. |
| 17 | `source_file` | string | **provenance** | Filename of the cached workbook this row came from. |
| 18 | `retrieved_at` | date string | **provenance** — parsed from the cache filename | `2026-08-19`. The workbook carries no vintage of its own; an undated cache is refused at read time. |
| 19 | `source_sha256` | string | **provenance** | sha256 of the workbook. NICE re-issues this file without a version marker, so the digest *is* the version. The build refuses an unpinned digest unless `--allow-new-vintage` is passed. |

## The five denominators

Fixed, so no published percentage rests on the wrong one:

| n | Use |
|---|---|
| **1531** | All recommendations. The dataset denominator. |
| **1357** | Excluding the 174 non-submissions — "of appraisals that reached a judgement". |
| **1327** | Also excluding the 30 only-in-research. **NICE's own 87% denominator — use only when comparing to NICE.** |
| **1181** | Appraisals. Appraisal-level questions only. |
| **925** | **Never a denominator.** What NICE's listing currently displays; a moving target that omits 260 live appraisals. |

## The 87% check

NICE publishes *"87% of our recommendations have been positive (recommended, optimised, or
recommended for the Cancer Drugs Fund)"*. Positive here is the six recommended/optimised outcomes
including CDF and IMF: **1156 recommendations.**

| Denominator | Share |
|---|---|
| 1531 — all | 75.51% |
| 1357 — excluding non-submissions | 85.19% |
| **1327 — NICE's own** | **87.11%** ✓ |

This is the **external validity check** on the outcome normalisation: 87.11% is NICE's number, not
ours, and reproducing it recovers the denominator NICE does not state. It runs as a test
(`tests/test_reconcile.py::test_the_87_percent_check`) and as a hard failure inside
`hta.cli build`. **If it drifts, the mapping broke.**

## Deliberately absent

| Field | Why | When |
|---|---|---|
| `route` (cost-comparison / HST / fast-track) | Not in the file. `sta_mta_process_raw` carries no such value, and HSTs are a separate NICE programme entirely. Populating it from this file would mean inventing it. | Lap 3, from guidance HTML |
| `date_published` | The file has no date, only a fiscal year. `2026/27` → `2026-01-01` would be a fabrication. | Lap 3, from guidance pages |
| ICER, comparator, trial design, severity / end-of-life modifiers | Not in this file at all. They live in the committee-papers PDF bundle. | Phase 1.5 |
| Patient access scheme | Partially inferable from `nice_comments_raw`, with unknown recall. A partial field presented as complete is worse than no field. | Phase 1.5 |

## Attribution

Derived from NICE published data under the [NICE UK Open Content
Licence](https://www.nice.org.uk/reusing-our-content/nice-uk-open-content-licence). Information was
accurate at the date of retrieval stated above. **NICE does not endorse this work.** No NICE content
is redistributed by this repository — see `LICENSING.md`.
