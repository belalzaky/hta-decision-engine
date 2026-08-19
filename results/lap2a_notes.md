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
