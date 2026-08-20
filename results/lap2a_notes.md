# Lap 2a — what did not work, and what the pages cost to read

Three notes, in the house style: the mistakes are the reusable part.

## 1 · My first supersession detector was wrong in two directions at once

A single regex for *"has been replaced / withdrawn / no longer current"* looked like it worked —
258 hits against 260 chapterless pages, close enough to feel finished. It was wrong twice:

- **Four false positives.** TA61, TA86, TA139 and TA566 are *live* appraisals that keep all their
  chapters and carry an update note — *"Recommendation 1.5 has been replaced"*, *"this is no longer
  available"*. Partially updated, not superseded. Worse, the superseding-link extractor then picked
  up the page's own nav link and reported **TA61 as superseded by TA61**.
- **Thirty-one false negatives in substance.** Withdrawal is a *different status* and NICE words it
  differently: *"NICE has withdrawn this guidance"*, *"we withdrew this guidance"*, *"has therefore
  been made obsolete"*. There is no superseding guidance to point at because the product left the
  market or lost its licence. A detector that looks only for *replaced by* silently files these as
  ordinary supersessions and loses an interesting class — a company pulling a product after
  approval is a different event from NICE replacing its own advice.

**Fixed by structure, not by more regex.** The reliable signal is **the absence of a chapter list**:
a superseded or withdrawn appraisal is served as a stub. The sentence then says *which* of the two
it is. Self-referential links are excluded explicitly.

## 2 · The metadata-shape table was useless until the reference number was masked

The first version masked dates but not `Reference number: TA1121`, so it reported 1,181 distinct
"shapes" — one per page — and answered nothing. Masked properly, there are **four**, which is what
makes "the route is not on this page" a measurement rather than an impression.

## 3 · No parser dependency was added, deliberately

`bs4` or `selectolax` was the obvious reach. The page-header block is byte-similar across 2000,
2016 and 2026 pages, and Lap 2a's questions are counting questions, so regex over a stable template
answers them without adding weight to the image. **This is not a general endorsement**: if Lap 3
extracts committee reasoning from chapter bodies, that is real parsing and a parser earns its
place. Recorded so the decision is revisited then rather than inherited by default.

## 4 · What the crawl actually cost

1,181 pages, 1,178 fetched in this run, **zero failures, zero redirects, zero retries**. Measured
from the manifest timestamps: **3,447 seconds — 57.5 minutes — for 1,178 requests, or 2.93 s each**,
against a 39-minute estimate. The estimate counted the 2-second delay and not NICE's own response
time, which adds about **0.93 s per request**.

**The delay is a floor, not the period.** Carrying the measured rate rather than the arithmetic one:
Lap 2b's 4,717 chapter requests are **2.6 hours on paper and about 3.8 hours in practice**. Same
mistake, same direction, now corrected once instead of twice.

---

# Lap 2b — notes

## 5 · The search API was checked before crawling, and it was empty

Full write-up: `results/lap2b-search-api-check.md`. Three requests, five minutes, negative result:
NICE's search API has **eight facets and none is the appraisal route**, and every route-adjacent
document field (`approachType`, `publicationType`, `technologyType`, `prioritisationProgramme`) is
**null on all 927 published appraisals**. Worth the five minutes anyway — a route facet would have
made a chunk of Lap 3 free, and the check is now on the record instead of being an open assumption.

It did settle one thing: `ngt` lists **Highly specialised technologies guidance as a separate
programme (37 items)**, so `hst` is out of scope by construction rather than merely missing.

## 6 · Three transient failures, and why they are worth writing down

1,635 chapters, **3 network-level failures** — two `IncompleteRead`, one read timeout. No HTTP
error, no rate-limiting, no pattern (TA390, TA413, TA651, spread across the run). All three were
`Committee-discussion` chapters, which are the largest pages in the set, so a dropped connection on
a long body is the likely cause.

**Re-running recovered all three and re-fetched nothing else.** That is the whole point of the
resume design: the cost of a dropped connection is three requests, not 1,635. The failures stay in
the manifest and in the report rather than being cleaned up — a "clean run" claim that quietly
omits three retries is the kind of thing this project exists not to do.

## 7 · Two measurement corrections, both mine

- **`--limit` reported deferred targets as "already cached".** A smoke test of 2 against 1,635
  targets printed *"1,633 already cached"*, which was false — they were untried. Now counted
  separately as `deferred_by_limit`.
- **Elapsed time spanned idle gaps.** Measuring first-to-last manifest timestamp would have folded
  the pause between the smoke test, the main run and the retry into the crawl rate. The report now
  sums only contiguous stretches and says so. In this run it made no difference — no gap exceeded
  60 s — but it would have on any run left overnight, and a rate that flatters itself is not a rate.

## 8 · What the chapter crawl cost

**1,635 chapters, 64.7 MB, 87 minutes, 3.17 s per request** — against 2.93 s for overview pages.
Chapters are bigger (mean 39,574 bytes against ~15,000), so the extra 0.24 s is transfer time.
Carrying the measured rate forward beats the arithmetic one: the narrow scope was estimated at
1.33 hours at 2.93 s and came in at 1.44 hours.
