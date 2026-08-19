# LICENSING — what this project will and will not redistribute

**Status: PROCEED WITH A NARROWED ARTEFACT — one decision is Belal's, not Claude Code's.**
Resolved in Lap 0, 19 Aug 2026, against the live NICE pages cached in `data/raw/lap0/`.
Nothing here is legal advice; it is a record of what NICE's own published terms say.

## 1 · The governing licence

NICE content is released under the **NICE UK Open Content Licence** (the "OCL"),
<https://www.nice.org.uk/reusing-our-content/nice-uk-open-content-licence>.
NICE's website terms and conditions, clause 18.1, confirm the OCL is the operative grant:

> "Copyright content owned by the National Institute for Health and Care Excellence (NICE) is made
> available for reuse to individuals and commercial/non-commercial organisations on a non-exclusive
> basis in the United Kingdom only under the NICE UK Open Content Licence."

The grant itself:

> "NICE grants you a **UK-only**, royalty-free, perpetual, non-exclusive licence to use the information
> subject to the conditions below."

Technology appraisal guidance is explicitly in scope — NICE's asset register lists "technology
appraisal guidance" under the reusable "Published guidance" category.

## 2 · Can derived structured data be redistributed? — YES, within the UK

The OCL expressly permits it. Under it you **may**:

> "edit, copy, publish, distribute and transmit the information, in part or in full …
> exploit the information commercially and non-commercially — for example, by **combining it with
> other information**, or by including it in your own product or application."

A tidy table of appraisal number, year, process, technology, condition and recommendation category,
derived from NICE's own published spreadsheet, is squarely inside that grant.

## 3 · The four conditions that bind this project

1. **Attribution is mandatory and its wording is prescribed.** Every published artefact must carry an
   attribution statement and disclaimer, linking to both the licence and the source. Required form:

   > © NICE [YEAR] TITLE. Available from www.nice.org.uk/guidance/taXXXX All rights reserved. Subject to
   > Notice of rights. NICE guidance is prepared for the National Health Service in England. All NICE
   > guidance is subject to regular review and may be updated or withdrawn. NICE accepts no responsibility
   > for the use of its content in this product/publication.

   Plus, per the OCL: make clear the information was accurate at the date of issue.
2. **Do not amend the wording or structure of published recommendations.** The OCL forbids amending or
   adapting "the wording or structure of any published individual NICE guidance recommendations". Any
   recommendation text reproduced must be verbatim. **This is why the brief's "verbatim beside
   normalised, never instead of" rule is a licence requirement here, not just good data hygiene.**
3. **No endorsement may be implied.** NICE does not endorse this project; the README must say so.
4. **UK-only.** The licence grant does not extend outside the United Kingdom. See §5.

## 4 · ⚠️ BLOCKER FOR BELAL — the AI clause

The OCL opens with:

> "Requests to use our content for **artificial intelligence (AI) purposes** in the United Kingdom and
> internationally **are not covered by the terms of this licence**."

The syndication API page adds:

> "If you wish to use artificial intelligence on NICE content in any system, platform or service available
> to end users (internally or externally) you must access NICE content through the API. … The use of NICE
> content to **train, fine-tune or weight Generative AI or large language models is not permitted**."

**What this touches:** Phase 3 is NLP (PubMedBERT) over evidence-review critiques, and Phase 2 is a model
over NICE-derived features. Both are plausibly "AI purposes".

**Assessment.** Phase 1 as scoped is *not* affected — it is a structured extract of a published
spreadsheet, no model, no AI. Phases 2 and 3 are affected and the boundary is genuinely unclear:
fine-tuning a transformer on NICE text sits far closer to the prohibition than fitting a logistic
regression on categorical fields does, and the API route (which would license AI use) is closed to
Belal — see §6.

**Recommended action, Belal's call:** email `reuseofcontent@nice.org.uk` — the address the OCL nominates —
stating plainly that this is a non-commercial, open, reproducible research project; that outputs are
derived structured data and published analysis; and asking whether classifying NICE text with an
existing open model falls within the OCL or needs separate permission. **Send this before Phase 3 work
starts, not after.** It costs one email and it is the difference between a publishable project and a
retracted one.

## 5 · ⚠️ SECOND DECISION FOR BELAL — "UK-only" vs a Zenodo DOI

The planned artefact is a **Zenodo DOI dataset**. Zenodo is worldwide, open-access and irrevocable.
The OCL grant is **UK-only**, and NICE's terms are explicit that international use "except for personal
use, study or personal research" requires prior written agreement and may attract a fee.

These are in tension. Publishing NICE-derived data to a world-readable archive under, say, CC-BY is
**not** something the OCL authorises Belal to do — he cannot sub-license more broadly than he was
licensed. Options, best first:

- **(a) Publish the pipeline, not the corpus.** Zenodo-DOI the *code*, the *data dictionary* and the
  *derived analysis*, with a one-command reproduction that downloads NICE's own spreadsheet from NICE.
  A stranger reproduces the dataset in one command; NICE's content is never mirrored. This satisfies
  every success criterion in spec §3 as revised by §10 item 9 (DOI, data dictionary, stranger
  reproduction) **without redistributing NICE content at all.** *This is the recommended route.*
- **(b) Ask NICE.** Same email as §4 — request confirmation that publishing derived structured data to
  an open repository is acceptable and on what attribution.
- **(c) Publish the derived table with the prescribed attribution and a UK-scope notice.** Defensible
  (it is derived data, not NICE's text, and the OCL permits publishing and distributing) but it does
  not sit cleanly with "UK-only" on a global archive.

**Claude Code's recommendation: (a), and send (b) in parallel.** Route (a) makes the licence question
stop being on the critical path, which is exactly what §10 item 10 asked for.

## 6 · The syndication API is closed — do not plan around it

Recorded per the brief and then dropped. The API requires an organisation with Cyber Essentials Plus,
ISO27001 or the NHS DSP Toolkit, and states: *"The NICE API is available for use by companies,
institutions and organisations, not private individuals … NICE cannot consider requests from individual
students."* It also excludes withdrawn and previous versions of guidance — which is precisely the
260-appraisal gap this project needs (see `docs/lap0-findings.md`, Q2). **Not a better route, now or later.**

## 7 · What this project will and will not do — the operative statement

**WILL redistribute:**
- Derived, structured, recommendation-level data: identifiers, dates, process type, normalised outcome
  and route codes, and the short verbatim categorical values (e.g. `Optimised`) needed to make the
  normalisation auditable.
- All code, the data dictionary, tests, and the analysis and write-up.
- Links to every NICE source URL, with the prescribed attribution statement.

**WILL NOT redistribute:**
- Mirrored guidance HTML, chapter text, or committee-papers PDFs. The raw cache stays local; `data/raw/`
  is git-ignored.
- Any amended or paraphrased version of a NICE recommendation. Where recommendation text appears it is
  verbatim, quoted, attributed and linked.
- Company submissions or external assessment reports from the committee-papers bundle. These carry
  **third-party IP that NICE is not authorised to license** — the OCL exempts "third-party rights that
  NICE is not authorised to licence" and, by name, "economic models underpinning guidance development
  work". **This constrains Phase 1.5 and Phase 3 output to derived codes and statistics, never text.**
- Anything marked commercial-in-confidence. NICE lists information exempt under access-to-information
  law, including commercial-in-confidence material, as content that cannot be reused. Redacted ICERs
  must therefore be recorded as `redacted_cic` **status codes** and never reconstructed or inferred.

## 8 · ⚠️ An unresolved contradiction on NICE's own site — recorded, not resolved

The guidance listing page footer carries a notice that flatly contradicts the OCL:

> "All content on this site is NICE copyright unless otherwise stated. You can download material for
> private research, study or in-house use only. **Do not distribute or publish any material from this
> site without first obtaining NICE's permission.**"

This is the pre-OCL legacy notice and it is inconsistent with clause 18.1 of NICE's own terms and with
the OCL grant. It is not possible to tell from the outside which NICE intends to govern. **It does not
change the recommendation in §5 — route (a) is safe under either reading**, which is another reason to
prefer it. Raise it in the same email.

---
*Sources cached with retrieval dates in `data/raw/lap0/`. Retrieved 19 August 2026.*
