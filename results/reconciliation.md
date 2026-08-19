# Reconciliation — NICE technology appraisal recommendations spine

Written by `python -m hta.cli build`. Every number here is computed from the
built table, not copied from a document.

## Source

| File | sha256 | Retrieved |
|---|---|---|
| `ta-recommendations_2026-08-19.xlsx` | `04fa1864d0f2e49b…` | 2026-08-19 |
| `ta-cancer-recommendations_2026-08-19.xlsx` | `593564f478e46625…` | 2026-08-19 |

NICE re-issues this spreadsheet without a version marker and it trails the
website, so every figure below is stamped to that vintage.

## Counts

| Quantity | n |
|---|---|
| Recommendations (rows) | **1531** |
| Appraisals (parent key) | **1181** |
| Appraisal numbers | TA1–TA1181, gapless: True |
| Appraisals with one recommendation | 1012 |
| Appraisals with more than one | 169 (widest: 16) |
| **Recommendations lost by counting appraisals** | **350** |
| Cancer recommendations (`is_cancer`) | 662 |
| Terminated non-submissions | 174 |
| Fiscal years covered | 1999/00–2026/27 |

## Outcomes

| Outcome | n |
|---|---|
| `recommended` | 653 |
| `optimised` | 439 |
| `cdf_recommended` | 48 |
| `cdf_optimised` | 13 |
| `imf_recommended` | 1 |
| `imf_optimised` | 2 |
| `only_in_research` | 30 |
| `not_recommended` | 171 |
| `terminated_non_submission` | 174 |

## The 87% check — external validity of the outcome mapping

NICE publishes: *"87% of our recommendations have been positive (recommended,
optimised, or recommended for the Cancer Drugs Fund)"*. Reproducing it fixes the
denominator NICE does not state.

| Denominator | Positive | n | Share |
|---|---|---|---|
| all recommendations | 1156 | 1531 | **75.51%** |
| excluding terminated non-submissions | 1156 | 1357 | **85.19%** |
| excluding non-submissions and only-in-research (NICE's own denominator) | 1156 | 1327 | **87.11%** |

The third row is the one to compare with NICE's published 87.0%. **If it drifts, the mapping broke.**

## Checks

| Check | Result |
|---|---|
| recommendations = 1531 | PASS — 1531 |
| appraisals = 1181 | PASS — 1181 |
| appraisal numbers gapless 1-1181 | PASS — 1-1181, gapless=True |
| terminated non-submissions = 174 | PASS — 174 |
| only-in-research = 30 | PASS — 30 |
| positive recommendations = 1156 | PASS — 1156 |
| positive share, all 1531 = 75.51% | PASS — 75.51% |
| positive share, excl 174 non-submissions = 85.19% | PASS — 85.19% |
| positive share, NICE denominator 1327 = 87.11% (matches NICE's published 87%) | PASS — 87.11% |
| is_cancer = 662 | PASS — 662 |

## Known trap, recorded not fixed

`technology_type_raw` carries a case variant of its own — *Medical device* (46) and
*Medical Device* (1) are the same category. It ships verbatim because Schema v1
specifies no normalised sibling for it; anyone stratifying on it should fold case
first. Flagged here rather than silently corrected.

---

Derived from NICE published data. NICE does not endorse this work. See `LICENSING.md`.
