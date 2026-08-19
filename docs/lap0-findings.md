# Lap 0 — reconnaissance findings

**Run:** 19 August 2026 · **Scope:** the five questions in the build brief. No scraper, no scaffold,
no extraction. **Verdict: GO, with four schema changes and one licence decision for Belal.**

Every fetch is cached under `data/raw/lap0/` with its retrieval date. Total network requests: ~30.

---

## Headline — the four things that change the build

1. **The counts in the brief are stale. It is 1181 appraisals / 1531 recommendations, not 1094 / 1443.**
   Confirmed against the file itself, not NICE's prose. The rescope survives; the numbers do not.
2. **`STA/MTA process` is NOT the route field the spec hoped for.** It carries single-vs-multi technology
   and review status. There is **no cost-comparison, no HST, no fast-track value in it.** The `route`
   enum in schema v0 **cannot be populated in Lap 1** and must be deferred to Lap 3.
3. **There is no JavaScript problem.** Plain HTTP with *default* headers returns full recommendation
   text on every era tested. **Playwright is not needed. Lap 2 is a small HTTP job.**
4. **The licence permits redistributing derived data but only UK-wide, and excludes AI use.** That
   collides with the planned worldwide Zenodo DOI and with Phase 3. See `LICENSING.md`; **one decision
   is Belal's.**

---

## Q1 · Profile of the NICE recommendations spreadsheet

**Source:** <https://www.nice.org.uk/what-nice-does/our-guidance/about-technology-appraisal-guidance/technology-appraisal-data-appraisal-recommendations>
(page last updated 14 August 2026) → `https://a.storyblok.com/f/243782/x/04c839059a/ta-recommendations.xlsx`
**Cached:** `data/raw/ta-recommendations_2026-08-19.xlsx` · 470,083 bytes ·
sha256 `04fa1864d0f2e49b3c767e77b6fad1f6f710023f54109cd749913dedac9f377a` · retrieved 2026-08-19.

**Shape.** One sheet, `TA recommendations`. **1531 data rows × 9 real columns.** (openpyxl reports
16,370 columns and 1,643 rows — Excel phantom range; real extent is 9 × 1531 after dropping all-null
rows and columns. A reader must drop empties, not trust `max_col`.) No preamble rows, no merged cells,
header on row 1. Two nulls in the entire file (one `Indication`, one `Comment`).

**Column names, verbatim and in order:**

| # | Column | Notes |
|---|---|---|
| 1 | `Rec no.` | integer, contiguous 1–1531. The natural recommendation key. |
| 2 | `TA ID` | `TA001` … `TA1181`. **Zero-padded to 3 digits.** |
| 3 | `Year of Publication` | **fiscal-year string** `1999/00`–`2026/27`, 28 distinct. Not a date. |
| 4 | `STA/MTA process` | ⚠️ **not the appraisal route** — see below |
| 5 | `Technology` | free text |
| 6 | `Technology type` | 6 values, undocumented by the brief — a free field |
| 7 | `Indication` | free text |
| 8 | `Categorisation (for specific recommendation)` | the outcome; 12 raw values |
| 9 | `Comment` | free text, 24–1780 chars, median 189; 411 contain newlines |

**⚠️ Distinct values of `STA/MTA process` — the single most consequential finding of Lap 0:**

| Value | n |
|---|---|
| STA | 988 |
| MTA | 440 |
| MTA (review) | 45 |
| STA (review) | 35 |
| STA (rapid review) | 16 |
| MTA (part-review) | 7 |

This is **two orthogonal facts in one string**: single-vs-multiple technology appraisal, and whether it
is an original, review, part-review or rapid review. It is **not** the route axis the spec cares about.
`cost_comparison`, `highly specialised technologies` and `fast track` **do not appear at all**.
Spec §10 item 1 asserted this file carries "appraisal process" in the §9 sense. **It does not.**
Corroborating: NICE lists *Highly specialised technologies guidance* as a **separate guidance programme
of 30 items** with its own IDs — HSTs are not in this file by construction, so an `hst` route value would
be empty even in principle.

**Distinct values of the recommendation category (12 raw → 9 canonical):**

| Raw value | n | → normalised |
|---|---|---|
| Recommended | 651 | `recommended` |
| recommended | 2 | `recommended` (case variant) |
| Optimised | 439 | `optimised` |
| Terminated Appraisal - non submission | 174 | `terminated_non_submission` |
| Not recommended | 137 | `not_recommended` |
| Not Recommended | 34 | `not_recommended` (case variant) |
| Recommended (CDF) | 48 | `cdf_recommended` |
| Optimised (CDF) | 13 | `cdf_optimised` |
| Only in research | 22 | `only_in_research` |
| Only in Research | 8 | `only_in_research` (case variant) |
| Optimised (IMF) | 2 | `imf_optimised` |
| Recommended (IMF) | 1 | `imf_recommended` |

Three of the twelve are pure case variants — normalisation is required, and the raw column must be kept
beside it (also a licence requirement, see `LICENSING.md` §3.2). **`IMF` — the Innovative Medicines Fund —
is missing from the brief's `outcome` enum**, which has `cdf` but no `imf`.

**External validity check on the normalisation.** NICE publishes "87% of our recommendations have been
positive (recommended, optimised, or recommended for the Cancer Drugs Fund)". Reproducing it:

| Denominator | Positive share |
|---|---|
| All 1531 | 75.51% |
| Excluding 174 terminated | 85.19% |
| Excluding terminated **and** only-in-research | **87.11%** ✓ |

The mapping reproduces NICE's headline figure exactly, and in doing so **recovers the denominator NICE
does not state** — the 87% excludes both non-submissions and only-in-research. Small, real, publishable.

**Date coverage.** 1999/00 to 2026/27, no gap years. Volume roughly triples across the series (33 in
2000/01 → 104 in 2021/22). The file has **no publication date** — only fiscal year. A real
`Published: 14 January 2026` **is** on each guidance page, so exact dates are a Lap 3 enrichment.

**What `comments` actually contains.** Not commentary — a short standardised rationale or status note.
Recurring patterns: *"Recommendation in line with marketing authorisation"*, *"…in line with clinical
practice"*, *"…following agreement of PAS"*, *"Guidance has been replaced by TAxx"* (121 rows),
*"Moved to static list"* (7). For terminated rows it is a full sentence naming the company's failure to
submit. **Two Phase-1-free signals hide here:** a partial **patient access scheme** flag (the brief
deferred PAS to Phase 1.5 — it is partially free, with recall caveats) and a **supersession** signal.

**Does `TA ID` join cleanly to `nice.org.uk/guidance/taXXXX`? — Yes, after de-padding.** Tested:

| Requested | HTTP | Redirects | Final |
|---|---|---|---|
| `/guidance/ta001` | 200 | 2 | `/guidance/ta1` |
| `/guidance/ta1` | 200 | 0 | `/guidance/ta1` |
| `/guidance/ta081` | 200 | 1 | `/guidance/ta81` |
| `/guidance/ta81` | 200 | 0 | `/guidance/ta81` |
| `/guidance/ta1121` | 200 | 0 | `/guidance/ta1121` |

**The canonical URL is unpadded.** Strip leading zeros: `TA081` → `ta81`. Passing the padded form works
but costs one-to-two redirects per request — ~1,200 avoidable round-trips across Lap 2.

**ID integrity.** All 1181 IDs match `^TA\d+$`; numeric range **1–1181 with zero gaps**. The file is a
**complete census**, not a sample. 1012 appraisals carry one recommendation; the rest split (TA081 has 16).

**Bonus — a free cancer flag.** NICE publishes a companion *cancer appraisal recommendations* file
(`ta-cancer-recommendations.xlsx`, cached). It has **identical columns** and its 662 rows are an **exact
subset** of the main file on `(TA ID, Rec no.)`. It is therefore a **NICE-authored `is_cancer` flag,
free, covering 662/1531 (43%) of recommendations.** This matters more than it looks: spec §7's worked
example of a worthless model is *"oncology drugs with a patient access scheme get approved"*. The
confounder §7 warns about is now a controlled variable rather than a guess.

**Verdict on the ⚠️ in the brief.** The brief said the 1094/1443 figures came from NICE's description,
not the file, and to say so loudly if wrong. **They are wrong.** They are also not what NICE currently
says — the page now states 1181 and 1531, matching the file exactly. The figures were simply stale.
**The rescope's logic is unaffected**: the spine is still a download, ~30% of recommendations are still
lost by counting appraisals, and the ICER fields are still absent.

---

## Q2 · Reconciling 880 vs 1094 vs 1443

**Answer: 1181 appraisals / 1531 recommendations is the dataset. 925 is the currently-published subset.
880 is not reproducible and should be retired. The hypothesis in the brief is CONFIRMED.**

**The 880 figure cannot be re-measured.** §9's method — `nice.org.uk/guidance/published?type=ta` — now
returns **HTTP 403 with NICE's own "Temporary Service Interruption, Error Code: 0x8133"** page. Probing
isolated the cause: the bare path `/guidance/published` returns 200, but **any** query string on it 403s
(`?type=ta`, `?ngt=…`, `?ps=50`, `?pa=2` all fail). This is a NICE-side fault on the filtered listing,
not a block on us — the error is theirs, served with their template. **§9's "results per page: All, one
request" route is currently unavailable.**

**Working route found.** The listing's own `__NEXT_DATA__` exposes the backing search service.
`https://search-api.nice.org.uk/api/search` with
`index=guidance&sp=on&om=[{"gst":["Published"]},{"ngt":["Technology appraisal guidance"]}]&ps=1000`
returns **all 925 in a single request**. Cached: `data/raw/ta-published-listing_2026-08-19.json`.
The naive `ngt=` parameter is silently ignored (returns the unfiltered 3804) — **the `om` array is
required**. A filter that fails open rather than erroring is a trap worth writing down.

**The diff.**

| Set | n |
|---|---|
| Spreadsheet appraisals | 1181 |
| Currently-published listing | 925 |
| Intersection | 921 |
| **In spreadsheet, not in listing** | **260** (= 396 recommendations) |
| **In listing, not in spreadsheet** | **4** — `ta1182`–`ta1185` |

**Characterising the 260-appraisal gap — hypothesis confirmed.** Comment-text enrichment, per appraisal:

| Marker | In gap (n=260) | In kept (n=921) |
|---|---|---|
| "replaced by" | 85 | 1 |
| "withdrawn" | 30 | 8 |
| "no longer" | 12 | 3 |
| "static list" | 2 | 3 |

That is 85/260 = **32.7%** of the gap versus 1/921 = **0.11%** of the kept set — a ~300× enrichment for
"replaced by". 116 of 260 are explained by the spreadsheet's own text; the other
144 carry only a routine rationale. **Five of those 144 were spot-checked live and 5/5 carry an explicit
supersession banner** — e.g. TA10 *"This guidance has been updated and replaced by the NICE guideline on
asthma"*; TA108 and TA109 → NG101; TA1088 → a newer TA. **The gap is superseded and withdrawn guidance,
exactly as hypothesised.** The gap spans every era (20 from 2000/01, 20 from 2017/18, 2 from 2025/26) —
it is not an artefact of age alone.

**⚠️ Critically for Lap 2: the 260 gap pages are still live.** All spot-checks returned HTTP 200 with
full text. They are absent from the *listing*, not from the *site*. **Enumerate Lap 2 from the
spreadsheet, never from the listing** — the listing would silently drop 22% of the corpus, and would
drop it non-randomly (superseded guidance is systematically older and more likely to have been revisited).

**The 4 extras are a freshness lag.** `ta1182`–`ta1185` are published on the site but absent from a
spreadsheet whose page was last updated 14 August 2026. **The spreadsheet trails the website.**
Every published figure needs a spreadsheet-vintage stamp, and any refresh must re-run the diff.

**The honest denominators, for every percentage this project ever publishes:**
- **1531** — all recommendations, the dataset denominator.
- **1357** — excluding 174 non-submissions, for "of appraisals that reached a judgement".
- **1327** — also excluding only-in-research; **this is NICE's own 87% denominator**, use it only when
  comparing to NICE.
- **1181** — appraisals, for appraisal-level questions only.
- **925** — never a denominator. It is "what NICE currently displays", a moving target.

**This is a finding, not just plumbing.** ~26% of recommendations (396/1531) are invisible if you work
from the published listing, and ~23% (350/1531) are invisible if you count appraisals instead of
recommendations. Two different ways to lose a quarter of the data, both the default behaviour.

---

## Q3 · The JavaScript-rendering question — SETTLED, and the spec was wrong

**Answer: plain HTTP with default headers returns the full recommendation text. No browser needed.**

Three appraisals across three eras, `/chapter/1-Recommendations`:

| Appraisal | Era | (a) plain curl, default headers | (b) browser UA + Accept |
|---|---|---|---|
| TA1 (wisdom teeth) | 2000 | **200, rec text present** | 200, identical |
| TA375 (rheumatoid arthritis) | 2016 | **200, rec text present** | 200, identical |
| TA1121 (acoramidis) | 2026 | **200, rec text present** | 200, identical |

Evidence — method (a), no User-Agent set, TA1121, extracted body text:

> "1 Recommendations 1.1 Acoramidis can be used, within its marketing authorisation, as an option to treat
> wild-type or hereditary transthyretin amyloidosis with cardiomyopathy in adults…"

TA1 (2000): *"1.1 The practice of prophylactic removal of pathology-free impacted third molars should be
discontinued in the NHS."* TA375 (2016): full 1.1–1.3 present. Methods (a) and (b) produced
**byte-identical extracted text** (2,525 chars for TA1121) — the browser headers change nothing.

Overview pages (`/guidance/taXXXX`) also render server-side, carrying the title, reference number,
chapter table of contents and a **real publication date** (`Published: 14 January 2026`).

**(c) headless Playwright was not run, deliberately.** Method (a) is the *weakest* of the three and it
succeeds; a stronger method succeeding adds nothing to the build decision, and installing a ~150 MB
browser to confirm a foregone conclusion would be waste dressed as rigour. **Recorded as a decision, not
an omission.** If Lap 2 ever sees empty bodies at volume, Playwright is the fallback and this is where
to start.

**Why §9 saw something different.** Not reproducible today. The site is now a server-rendered Next.js
application (`buildId` present in `__NEXT_DATA__`, build `10.0.4246`); the legacy `?type=ta` listing is
simultaneously 403-ing. The most likely reading is that NICE is mid-platform-migration and §9 caught it
in a different state. §9's conclusion is **superseded**: *the listing is now the broken half and the
individual pages are the reliable half* — precisely inverted.

**⚠️ One caveat, honestly stated.** Three successful fetches do not prove 1,181 sequential fetches will
succeed; rate-limiting or bot mitigation may appear at volume. **Mitigation for Lap 2:** resume-safe by
construction, never re-fetch what is on disk, and assert on each response that the recommendation
container is non-empty — fail loudly on the first empty body rather than caching 1,181 shells.

**Build consequence: Lap 2 is a small HTTP job.** No Playwright, no browser pool, no `pdfplumber`.

---

## Q4 · The licence — resolved, with one decision reserved for Belal

**Full answer in `LICENSING.md`. Summary:**

- **Can derived structured data be redistributed? YES** — the NICE UK Open Content Licence expressly
  permits editing, copying, publishing, distributing and combining the information, commercially or not.
- **Under what attribution?** A prescribed statement plus disclaimer, linking to the licence and the
  source, and an accuracy-at-date-of-issue note. Verbatim quoted text only — the OCL **forbids amending
  the wording or structure of published recommendations**, which independently mandates the brief's
  "verbatim beside normalised" rule.
- **⚠️ Two things stop this being a clean yes:**
  1. **The grant is UK-only.** A worldwide Zenodo DOI is not obviously within it. *Recommended fix:*
     **DOI the pipeline and the analysis, not the corpus** — a one-command rebuild that fetches NICE's own
     file from NICE. This meets every revised §3 success criterion (DOI, data dictionary, stranger
     reproduction) while redistributing no NICE content, and is safe under either reading of §8 below.
  2. **AI use is excluded from the licence entirely**, and training or fine-tuning generative models is
     prohibited outright. **Phase 1 is unaffected. Phases 2–3 are.** Email
     `reuseofcontent@nice.org.uk` before Phase 3 starts.
- **A contradiction on NICE's own site**, recorded: the listing footer still says *"Do not distribute or
  publish any material from this site without first obtaining NICE's permission"*, which is inconsistent
  with clause 18.1 of NICE's own terms. Cannot be resolved from outside. Another reason to prefer the
  pipeline-not-corpus route.
- **Syndication API: closed.** Requires an organisation with Cyber Essentials Plus / ISO27001 / NHS DSP
  Toolkit; *"not private individuals"*; *"cannot consider requests from individual students"*. It also
  excludes withdrawn and superseded guidance — the very 260 appraisals Q2 identified. **Not a better
  route later. Drop it.**

---

## Q5 · The politeness budget, from robots.txt

`https://www.nice.org.uk/robots.txt`, cached, retrieved 2026-08-19 — the complete file:

```
User-agent: *
Crawl-delay: 1
Disallow: /cks-is-only-available-in-the-uk
Disallow: /cks-end-user-licence-agreement
Allow: /
```

- **Crawl-delay: 1 second.** That is the budget, from the file, not a guess.
- **Neither disallowed path touches this project** — both are Clinical Knowledge Summaries. `/guidance/*`
  is explicitly allowed.
- **No sitemap directive**, so no free enumeration route there.

**Lap 2 setting: 1 request per 2 seconds** — double the required delay, on the standing §5 instruction not
to hammer a public body. 1,181 appraisals ≈ **40 minutes** unattended, single-threaded, no concurrency.
Sequential and serial; a crawl-delay is not a token bucket to be spent in parallel.
Set a real, identifying User-Agent with a contact address, as used throughout Lap 0.

---

## Lap 0 — definition of done

- [x] All five questions answered with the evidence that produced the answer.
- [x] Spreadsheet cached under `data/raw/` with retrieval date and sha256 (plus the cancer companion,
      the published-listing JSON, and every HTML page consulted, under `data/raw/lap0/`).
- [x] `LICENSING.md` exists and is unambiguous — including where the ambiguity is NICE's, not ours.
- [x] Go/no-go stated below, with every field that has to change.

## Explicitly NOT done, as instructed

No scraper. Nothing fetched at volume (~30 requests total). Repo not scaffolded — no `src/`, `tests/`,
CI, Dockerfile or `git init`; only `docs/` and `data/raw/` exist, because the deliverables must live
somewhere. No `pdfplumber`. No committee-papers PDF touched. No ICER extracted. Tooling for profiling ran
in a throwaway environment outside the repo.

---

# GO / NO-GO on the Lap 1 schema

## **GO** — Lap 1 can proceed. Four fields change. One decision is Belal's and does not block Lap 1.

### Fields that must change

| # | Field | Change | Why |
|---|---|---|---|
| 1 | `route` | **Remove from Lap 1. Defer to Lap 3.** | Not derivable. `STA/MTA process` carries no cost-comparison / HST / fast-track value. Populating it from Lap 1 data would mean inventing it. |
| 2 | `appraisal_process_raw` | **Rename to `sta_mta_process_raw`**, and add derived `process_type` (`STA`/`MTA`) + `review_type` (`original`/`review`/`part-review`/`rapid review`) | The column is two facts in one string, and the brief's name implies a route it does not carry. Decomposition is clean: STA 988/0/16/35, MTA 440/7/0/45. |
| 3 | `outcome` | **Add `imf_recommended`, `imf_optimised`; split CDF into `cdf_recommended`/`cdf_optimised`; rename `terminated` → `terminated_non_submission`** | IMF exists (3 rows) and is missing from the enum. Non-submission is the only termination flavour present, and naming it precisely keeps it from silently absorbing other withdrawal types later. |
| 4 | `date_published` | **Drop from Lap 1** (keep `year_published_raw` as the fiscal-year string `1999/00`) | The file has no date, only a fiscal year. Real dates are on the guidance pages → Lap 3. Do not fabricate `2026-01-01` from `2026/27`. |

### Fields to add — free, and not in schema v0

| Field | Source |
|---|---|
| `technology_type_raw` | 9th column, 6 values — free, and a natural stratifier |
| `is_cancer` | NICE's own cancer companion file, exact subset — the §7 confounder, controlled |
| `recommendation_seq` | `Rec no.`, contiguous 1–1531 — a stable NICE-native key |

### Fields confirmed exactly as specified

`recommendation_id` (`TA1121-01`), `appraisal_id`, `source_file`, `retrieved_at`, `technology_raw`,
`condition_raw` (from `Indication`), `recommendation_category_raw`, `nice_comments_raw`.
**`terminated_flag` is confirmed and is better than hoped** — §9 expected listing-text parsing; it is a
categorical value in the spreadsheet, exact, zero scraping, **n=174 (11.4% of recommendations)**.

### One correction to `appraisal_url`

Build it from the **de-padded** ID: `TA081` → `https://www.nice.org.uk/guidance/ta81`. Keep the padded
`TA ID` verbatim in its own column. Saves ~1,200 redirects in Lap 2.

### Consequences for the laps ahead

- **Lap 2 shrinks.** No Playwright, no browser automation. ~1,181 fetches at 1 per 2 s ≈ 40 minutes.
  **Enumerate from the spreadsheet, never the listing** — the listing omits 260 live appraisals.
- **Lap 3 gains a job it did not have:** `route` (cost-comparison / HST / fast-track), the real
  publication date, and supersession status all come from guidance HTML.
- **§10 item 14's trap is still live but now deferred.** Route cannot enter a pooled outcome model —
  and since `route` is not in Lap 1 at all, Lap 1 cannot commit that error. Note it forward to Lap 3.
- **Phase 2's lead question is intact and is now stronger.** Termination is exact and categorical
  (n=174), and Q2 shows non-submissions are *under*-represented in the published listing (25 of 174 sit
  in the invisible gap) — so anyone working from the website alone sees a biased picture of withdrawal.
  That is a real, defensible, Phase-1-answerable finding.

### What Belal must decide — does not block Lap 1

1. **Publication artefact shape** (`LICENSING.md` §5): DOI the pipeline and analysis rather than the
   corpus. **Claude Code recommends this** — it satisfies every success criterion and takes the licence
   off the critical path.
2. **Send one email to `reuseofcontent@nice.org.uk`** covering the AI clause, open-repository
   publication, and the site's self-contradictory notice. **Before Phase 3, not after.**
