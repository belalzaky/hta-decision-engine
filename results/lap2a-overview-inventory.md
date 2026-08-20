# Lap 2a — overview-page inventory

Written by `python -m hta.cli inventory`, which reads the cache and makes **no**
network requests. Enumeration is the Lap 1 spine, never NICE's published listing.

## Coverage

| Quantity | n |
|---|---|
| Appraisals in the spine | 1181 |
| Cached and parsed | 1181 |
| Failed | 0 |
| Missing (never attempted, or manifest points at nothing) | 0 |
| Redirected away from the requested ID | 0 |

## 1 · The chapter inventory

| Quantity | n |
|---|---|
| Chapters across all cached overviews | **4717** |
| Appraisals carrying chapters | 921 |
| Appraisals with no chapter list at all | 260 |
| Mean chapters, where present | 5.12 |
| Distinct chapter titles | 492 |
| Distinct chapter slugs (number stripped) | 442 |

### Chapters per appraisal

| Chapters | Appraisals |
|---|---|
| 0 | 260 |
| 1 | 147 |
| 2 | 1 |
| 3 | 1 |
| 4 | 76 |
| 5 | 376 |
| 6 | 113 |
| 7 | 76 |
| 8 | 56 |
| 9 | 46 |
| 10 | 14 |
| 11 | 11 |
| 12 | 4 |

### By era

- **TA1-200** — 200 appraisals, 787 chapters, distribution {0: 111, 1: 1, 3: 1, 5: 1, 6: 4, 7: 7, 8: 18, 9: 28, 10: 14, 11: 11, 12: 4}
- **TA201-500** — 300 appraisals, 1409 chapters, distribution {0: 72, 1: 24, 2: 1, 4: 4, 5: 23, 6: 54, 7: 66, 8: 38, 9: 18}
- **TA501-800** — 300 appraisals, 1051 chapters, distribution {0: 60, 1: 43, 4: 15, 5: 146, 6: 34, 7: 2}
- **TA801-1181** — 381 appraisals, 1470 chapters, distribution {0: 17, 1: 79, 4: 57, 5: 206, 6: 21, 7: 1}

### The most common chapter titles

| Title | Appraisals |
|---|---|
| 1 Recommendations | 718 |
| 3 Committee discussion | 473 |
| 4 Implementation | 435 |
| 5 Appraisal committee members and NICE project team | 241 |
| 5 Implementation | 209 |
| 5 Evaluation committee members and NICE project team | 173 |
| 2 The technology | 166 |
| Advice | 149 |
| Update information | 141 |
| 4 Consideration of the evidence | 109 |
| 2 Clinical need and practice | 80 |
| 7 Sources of evidence considered by the Committee | 78 |
| 3 The manufacturer's submission | 75 |
| 4 Evidence and interpretation | 70 |
| 4 Committee discussion | 65 |
| 3 Evidence | 63 |
| 6 Appraisal committee members and NICE project team | 63 |
| 6 Recommendations for further research | 61 |
| 8 Sources of evidence considered by the Committee | 59 |
| 1 Recommendation | 51 |
| 4 Evaluation committee members and NICE project team | 50 |
| 3 Implementation | 44 |
| 6 Appraisal Committee members and NICE project team | 43 |
| 3 The technologies | 40 |
| 7 Appraisal Committee members and NICE project team | 38 |

## 2 · Is the appraisal route visible on the overview page?

**No.** The overview page carries no route field, and the words that would name one
barely appear across 1,181 pages:

| Route marker | Pages containing it |
|---|---|
| multiple_technology | 2 |
| highly_specialised | 2 |

The page-header metadata block is the only structured block on the page, and it has just
four shapes across the whole corpus — product label, reference number, and dates. Nothing
distinguishes cost-comparison from standard, and nothing marks fast-track:

| Shape (reference and dates masked) | Appraisals |
|---|---|
| `Technology appraisal guidance | Reference number: <ref> | Published: <date>` | 938 |
| `Technology appraisal | Reference number: <ref> | Published: <date>` | 168 |
| `Technology appraisal guidance | Reference number: <ref> | Published: <date> | Last updated: <date>` | 73 |
| `Technology appraisal | Reference number: <ref> | Published: <date> | Last updated: <date>` | 2 |

**`route` stays deferred.** If it exists in the open at all it is in the chapter text or
the committee papers, not here. Lap 2b will show whether the chapters carry it.

### What the page *does* carry: two signals for the terminated class

The product label is not always the same string. **170 pages say `Technology appraisal` rather than `Technology appraisal guidance`**, and **149 pages carry a chapter titled "Advice"** in place of a numbered chapter list — for 147 of them it is the only chapter, and 2 (`TA149, TA240`) carry it alongside others. Both turn
out to mark termination.

| Signal | Pages | Precision vs `terminated_flag` | Recall |
|---|---|---|---|
| Short product label | 170 | 100% | 98% |
| Lone "Advice" chapter | 149 | 100% | 86% |

Scored against Lap 1's 174 terminated appraisals. **Both signals are perfectly precise** — every page carrying either one is a termination
in the spreadsheet — and neither is complete. The short label misses `TA1141, TA147, TA150, TA175`; three of those are chapterless stubs from 2008–2010 and
one is recent, so this is not simply an old-template effect. Neither signal is a
substitute for the spreadsheet's own categorical value, which is exact.

This is the same kind of check as Lap 1's 87%: an outcome the spreadsheet asserts,
confirmed independently by how NICE builds the page. It costs nothing and it is the
strongest evidence so far that the terminated class — Phase 2's lead question — is solid.
**Not extracted into the spine.** Lap 2 inventories; Lap 3 extracts.

## 3 · Is the real publication date there?

| Quantity | Value |
|---|---|
| With a machine-readable `<time datetime=…>` | 1181 |
| Without one | 0 |
| Earliest | 2000-03-27 |
| Latest | 2026-07-30 |

| Date label shape | Appraisals |
|---|---|
| `Published: <date>` | 1106 |
| `Published: <date> | Last updated: <date>` | 75 |

## 4 · Supersession

**Detectable, and it names the superseding guidance.** A superseded appraisal is a
*stub*: the page keeps its title, reference number and publication date, loses its whole
chapter list, and carries one sentence saying what replaced it.

| Quantity | n |
|---|---|
| Stub pages (no chapter list at all) | 260 |
| …carrying a supersession sentence | 254 |
| …naming the superseding guidance with a link | 192 |
| …using withdrawal language instead | 31 |
| …carrying neither | 0 |

Superseded and **withdrawn are different statuses.** Withdrawal — the product left the
market, or the licence went — has no superseding guidance to point at, so a detector that
looks only for *replaced by* misses it. Withdrawn with nothing superseding it: **31** (`TA008, TA065, TA084, TA097, TA113, TA144, TA202, TA232`).

Superseding reference prefixes: `{'TA': 149, 'CG': 24, 'NG': 19, 'PH': 1}` — a superseded
appraisal is most often replaced by another appraisal, but a quarter of the time it is
absorbed into a clinical guideline (CG/NG), which is a different document class entirely.

| Appraisal | Superseded by | URL |
|---|---|---|
| TA002 | TA304 | http://www.nice.org.uk/guidance/ta304 |
| TA003 | TA55 | http://www.nice.org.uk/guidance/ta55 |
| TA004 | TA71 | http://www.nice.org.uk/guidance/ta71 |
| TA005 | TA69 | http://www.nice.org.uk/guidance/ta69 |
| TA006 | CG81 | http://www.nice.org.uk/guidance/cg81 |
| TA007 | CG184 | http://www.nice.org.uk/guidance/cg184 |
| TA009 | TA63 | http://www.nice.org.uk/guidance/ta63 |
| TA010 | NG245 | https://www.nice.org.uk/guidance/ng245 |

**Precision caveat for Lap 3.** 4 *live* appraisals (`TA061, TA086, TA139, TA566`) carry update language while keeping
their chapters — a single recommendation replaced, or one drug no longer available. They
are **partially** updated, not superseded. Matching the sentence alone would mis-class them;
the reliable structural signal is **the absence of a chapter list**.

## 5 · Failures, itemised

**None.** Every appraisal in the spine returned HTTP 200 with a real body.

### Missing

**None.** No silent gaps: every appraisal is cached or recorded as failed.

### Redirects

**None.** Every de-padded URL resolved without a redirect, as Lap 0 predicted.

## Cross-check against Lap 0

**The 260 chapterless stub pages are exactly the 260 appraisals Lap 0 found in the spreadsheet and not in NICE's published listing of 925.** Set-identical, both directions. Two independent methods — a listing diff in Lap 0, page structure here — pick out the same appraisals, so the finding is not an artefact of either. It also confirms guardrail 7b the hard way: enumerating from the listing would have skipped precisely the pages that have no chapters to crawl, and with them 396 recommendations.

## What this sets Lap 2b to

Crawling every chapter of every cached appraisal is **4717 requests** — **2.62 hours** at the 2-second delay, and about **3.8 hours** at the rate Lap 2a
actually ran (2.93 s per request measured, because the delay is a floor and NICE's
response time sits on top of it). Scope for 2b is Belal's call at the gate; the
recommendations and committee-discussion chapters alone are a much smaller target:

| Chapter slug | Appraisals carrying it |
|---|---|
| `Recommendations` | 718 |
| `Recommendation` | 51 |
| `Committee-discussion` | 538 |
| `Consideration-of-the-evidence` | 109 |
| `Evidence-and-interpretation` | 70 |
| `Advice` | 149 |

That narrower target is **1635 requests** — 0.91 hours on paper, about **1.33 hours** at the measured rate, and it
is the half of the corpus that carries the decision and the reasoning. Implementation,
committee membership and sources-of-evidence chapters are administrative and answer
none of Phase 1's questions.

---

Derived from NICE published data. NICE does not endorse this work. No NICE content is
redistributed — see `LICENSING.md`.
