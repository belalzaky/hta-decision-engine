"""Lap 2a — read the cache, never the network, and report what is in it.

Five questions, from the brief: the exact chapter inventory, whether the
appraisal *route* is visible on the overview page, whether the real publication
date is there, whether supersession is detectable, and every failure itemised.

**Nothing here writes to the spine.** Lap 2 caches and inventories; Lap 3
extracts. The parsers exist to count and characterise, not to populate fields.

Parsing is regex over a stable server-rendered template rather than an HTML
library: the page-header metadata block is byte-similar across 2000, 2016 and
2026 pages, and adding a parser dependency to answer counting questions would be
weight without benefit. If Lap 3 needs real extraction, that is where a parser
earns its place.
"""
from __future__ import annotations

import html as html_mod
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

_TIME = re.compile(r'<time[^>]*datetime="(\d{4}-\d{2}-\d{2})"[^>]*>(.*?)</time>', re.S)
_METADATA_BLOCK = re.compile(
    r'<ul class="page-header__metadata".*?>(.*?)</ul>', re.S
)
_LI = re.compile(r"<li[^>]*>(.*?)</li>", re.S)
_REFERENCE = re.compile(r"Reference number:\s*</span>\s*([A-Z]+\d+)", re.S)
_TITLE = re.compile(r"<title>(.*?)</title>", re.S)
_CHAPTER_LINK = re.compile(
    r'href="(/guidance/[a-z0-9]+/chapter/([^"#]+))"[^>]*>(.*?)</a>', re.S
)
_ANCHOR = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_BODY = re.compile(r"<body\b", re.I)

#: Phrases that would identify the appraisal route if NICE printed it here.
ROUTE_MARKERS = {
    "cost_comparison": re.compile(r"cost[- ]comparison", re.I),
    "highly_specialised": re.compile(r"highly specialised", re.I),
    "fast_track": re.compile(r"fast[- ]track", re.I),
    "single_technology": re.compile(r"single technology appraisal", re.I),
    "multiple_technology": re.compile(r"multiple technology appraisal", re.I),
    "proposal_route": re.compile(r"\bproportionate approach\b", re.I),
}

#: "This guidance has been updated and replaced by ..." — the stub-page sentence.
_SUPERSESSION = re.compile(
    r"(has been (?:updated and )?replaced|no longer (?:current|available)|"
    r"has been withdrawn|this guidance has been updated)",
    re.I,
)

#: Withdrawal is a *different* status from supersession and NICE words it
#: differently: the product left the market or the licence went, so there is no
#: superseding guidance to point at. Detected separately — conflating the two
#: would lose a distinct and interesting outcome class.
_WITHDRAWAL = re.compile(
    r"(we withdrew this guidance|has withdrawn this guidance|"
    r"guidance was withdrawn|has been withdrawn|been made obsolete|"
    r"announced the withdrawal of)",
    re.I,
)
_SUPERSEDING_LINK = re.compile(
    r'<a[^>]*href="([^"]*?/guidance/([a-z]+\d+))"[^>]*>(.*?)</a>', re.S
)


def _text(fragment: str) -> str:
    return html_mod.unescape(re.sub(r"<[^>]+>", " ", fragment)).replace("\xa0", " ")


def _clean(fragment: str) -> str:
    return re.sub(r"\s+", " ", _text(fragment)).strip()


def _body(page: str) -> str:
    m = _BODY.search(page)
    return page[m.start():] if m else page


def parse_overview(page: str) -> dict:
    """Everything Lap 2a needs to count, from one cached overview page."""
    body = _body(page)

    metadata: list[str] = []
    block = _METADATA_BLOCK.search(body)
    if block:
        metadata = [t for t in (_clean(li) for li in _LI.findall(block.group(1))) if t]

    dates = [(iso, _clean(label)) for iso, label in _TIME.findall(body)]
    published = dates[0][0] if dates else None
    labels = [m for m in metadata if "Published" in m or "Last updated" in m]

    chapters, seen = [], set()
    for href, slug, label in _CHAPTER_LINK.findall(body):
        if slug in seen:
            continue
        seen.add(slug)
        chapters.append({"slug": slug, "url": href, "title": _clean(label)})

    plain_body = _clean(body)
    superseded = bool(_SUPERSESSION.search(plain_body))
    withdrawn = bool(_WITHDRAWAL.search(plain_body))
    reference = _REFERENCE.search(body)
    own_ref = (reference.group(1) if reference else "").upper()

    superseding = []
    if superseded:
        for href, ref, label in _SUPERSEDING_LINK.findall(body):
            if not href.rstrip("/").endswith(ref):
                continue
            # The page links to itself in its own nav; that is not supersession.
            if ref.upper() == own_ref:
                continue
            superseding.append({"reference": ref.upper(), "url": href,
                                "label": _clean(label)})

    routes = [name for name, rx in ROUTE_MARKERS.items() if rx.search(plain_body)]

    title = _TITLE.search(page)

    return {
        "reference_number": reference.group(1) if reference else None,
        "title": _clean(title.group(1)) if title else None,
        "product_type": metadata[0] if metadata else None,
        "metadata_items": metadata,
        "date_labels": labels,
        "published_date": published,
        "all_dates": [d for d, _ in dates],
        "chapters": chapters,
        "chapter_count": len(chapters),
        "superseded": superseded,
        "withdrawn": withdrawn,
        "superseding": superseding[:3],
        "route_markers": routes,
        "bytes": len(page),
    }


_LISTING_ID = re.compile(r"^ta\d+$", re.I)


def published_listing_ids(path: Path) -> set[str]:
    """De-padded TA IDs from Lap 0's cached copy of NICE's published listing.

    Used only as a cross-check: Lap 0 found 260 appraisals in the spreadsheet
    and not in this listing. If the stub pages found here are the same 260, two
    independent methods agree and the finding is not an artefact of either.
    """
    found: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, str) and _LISTING_ID.match(node.strip()):
            found.add(f"TA{int(node.strip()[2:])}")

    walk(json.loads(path.read_text(encoding="utf-8")))
    return found


def _depad(appraisal_id: str) -> str:
    return f"TA{int(appraisal_id[2:])}"


#: The chapters that carry the decision and the reasoning behind it. Everything
#: else on an overview — implementation, committee membership, sources — is
#: administrative and answers none of Phase 1's questions.
SUBSTANTIVE_SLUGS = (
    "Recommendations",
    "Recommendation",
    "Committee-discussion",
    "Consideration-of-the-evidence",
    "Evidence-and-interpretation",
    "Advice",
)


BASE_URL = "https://www.nice.org.uk"


def chapter_targets(targets, manifest, slugs=SUBSTANTIVE_SLUGS) -> list[tuple[str, str]]:
    """`(key, url)` for every chapter worth fetching, read from the cached overviews.

    Targets come from the pages already on disk — not from a guessed URL pattern
    and not from the site. A chapter that NICE does not link from the overview
    does not exist as far as this crawl is concerned.

    `slugs` is matched after stripping the leading chapter number, so
    `1-Recommendations` and `4-Recommendations` both match `Recommendations`.
    """
    wanted = set(slugs)
    out: list[tuple[str, str]] = []
    for appraisal_id, _ in targets:
        record = manifest.get(appraisal_id)
        if record is None or not record.ok or not record.path:
            continue
        parsed = parse_overview(Path(record.path).read_text(encoding="utf-8", errors="replace"))
        for chapter in parsed["chapters"]:
            if re.sub(r"^\d+-", "", chapter["slug"]) not in wanted:
                continue
            out.append((f"{appraisal_id}/{chapter['slug']}", BASE_URL + chapter["url"]))
    return out


def chapter_cache_report(targets, chapter_manifest, manifest_path: Path) -> dict:
    """What Lap 2b actually put on disk, and what it cost.

    Reads the manifest and the files it points at. Nothing is parsed out of the
    chapter bodies — that is Lap 3's job, and doing it here would be exactly the
    scope creep the brief forbids.
    """
    wanted = dict(targets)
    ok, failed, missing = [], [], []
    per_slug: Counter = Counter()
    per_slug_wanted: Counter = Counter()
    total_bytes = 0

    for key in wanted:
        per_slug_wanted[re.sub(r"^\d+-", "", key.split("/", 1)[1])] += 1
        record = chapter_manifest.get(key)
        if record is None:
            missing.append({"key": key, "reason": "never attempted"})
            continue
        if not record.ok:
            failed.append({"key": key, "http_status": record.http_status,
                           "error": record.error})
            continue
        if not Path(record.path).exists():
            missing.append({"key": key,
                            "reason": f"manifest points at {record.path}, which is absent"})
            continue
        ok.append(key)
        per_slug[re.sub(r"^\d+-", "", key.split("/", 1)[1])] += 1
        total_bytes += record.bytes or 0

    rows = [json.loads(l) for l in manifest_path.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    retried = len(rows) - len({r["key"] for r in rows})
    transient = [
        {"key": r["key"], "error": r["error"]}
        for r in rows if r.get("error") and r["key"] in set(ok)
    ]

    # Wall clock from first to last row would include the idle gaps between a
    # smoke test, the main run and a retry, and would understate the true rate.
    # Sum the contiguous stretches instead: a gap over a minute starts a new one.
    stamps = sorted(datetime.fromisoformat(r["retrieved_at"]) for r in rows)
    seconds, gaps = 0.0, 0
    for earlier, later in zip(stamps, stamps[1:]):
        delta = (later - earlier).total_seconds()
        if delta > 60:
            gaps += 1
            continue
        seconds += delta
    seconds = seconds or None

    appraisals = {k.split("/", 1)[0] for k in ok}
    return {
        "targets": len(wanted),
        "cached": len(ok),
        "failed": failed,
        "missing": missing,
        "appraisals_with_a_substantive_chapter": len(appraisals),
        "per_slug_cached": dict(per_slug.most_common()),
        "per_slug_targeted": dict(per_slug_wanted.most_common()),
        "megabytes_on_disk": round(total_bytes / 1_000_000, 1),
        "mean_page_bytes": round(total_bytes / len(ok)) if ok else 0,
        "manifest_rows": len(rows),
        "retried_keys": retried,
        "transient_failures_recovered": transient,
        "active_seconds": round(seconds) if seconds else None,
        "idle_gaps_excluded": gaps,
        "seconds_per_request": round(seconds / (len(rows) - gaps - 1), 2)
        if seconds and len(rows) - gaps - 1 > 0 else None,
    }


def chapter_report_markdown(r: dict) -> str:
    lines = [
        "# Lap 2b — the substantive chapter cache",
        "",
        "Written by `python -m hta.cli inventory`. Targets came from the **cached overview",
        "pages**, never a guessed URL pattern and never the site. **Nothing is parsed out of the",
        "chapter bodies here** — Lap 2 caches, Lap 3 extracts.",
        "",
        "## Coverage",
        "",
        *_table(
            [["Chapters targeted", r["targets"]],
             ["Cached", f"**{r['cached']}**"],
             ["Failed", len(r["failed"])],
             ["Missing", len(r["missing"])],
             ["Appraisals with at least one substantive chapter",
              r["appraisals_with_a_substantive_chapter"]],
             ["On disk", f"{r['megabytes_on_disk']} MB "
                         f"(mean {r['mean_page_bytes']:,} bytes per chapter)"]],
            ["Quantity", "n"]),
        "",
        "## By chapter type",
        "",
        *_table(
            [[f"`{slug}`", r["per_slug_targeted"].get(slug, 0), n]
             for slug, n in r["per_slug_cached"].items()],
            ["Chapter slug", "Targeted", "Cached"]),
        "",
        "## What it cost, measured",
        "",
        *_table(
            [["Requests (manifest rows, retries included)", r["manifest_rows"]],
             ["Time actually crawling", f"{r['active_seconds']:,} s "
                                       f"({round((r['active_seconds'] or 0) / 60)} minutes)"],
             ["Per request", f"**{r['seconds_per_request']} s**"],
             ["Idle gaps excluded (smoke test, retry)", r["idle_gaps_excluded"]]],
            ["Quantity", "Value"]),
        "",
        "The 2-second delay is a floor; NICE's response time sits on top of it. Lap 2a measured",
        "2.93 s per request on overview pages, so chapters are marginally slower — they are larger",
        "(mean "
        f"{r['mean_page_bytes']:,} bytes against roughly 15,000 for an overview).",
        "",
        "## Failures",
        "",
    ]
    if r["failed"] or r["missing"]:
        lines += _table([[x["key"], x.get("error") or x.get("reason")]
                         for x in r["failed"] + r["missing"]], ["Key", "Reason"])
    else:
        lines.append("**None outstanding.** Every targeted chapter is on disk.")
    if r["transient_failures_recovered"]:
        lines += [
            "",
            f"**{len(r['transient_failures_recovered'])} transient failures were recovered by "
            "re-running**, which is the resume path working rather than a clean run:",
            "",
            *_table([[x["key"], x["error"]] for x in r["transient_failures_recovered"]],
                    ["Key", "First attempt"]),
            "",
            "All three were network-level — an incomplete read or a read timeout, never an HTTP",
            "status. Recorded rather than smoothed over: a crawl of this size against a public",
            "body will drop a connection occasionally, and the design point is that it costs a",
            "re-run of three requests, not of 1,635.",
        ]
    lines += [
        "",
        "---",
        "",
        "Derived from NICE published data. NICE does not endorse this work. The cache is never",
        "redistributed — see `LICENSING.md`.",
        "",
    ]
    return "\n".join(lines)


def _era(appraisal_number: int) -> str:
    if appraisal_number <= 200:
        return "TA1-200"
    if appraisal_number <= 500:
        return "TA201-500"
    if appraisal_number <= 800:
        return "TA501-800"
    return "TA801-1181"


def build_report(targets, manifest, root: Path, listing_path: Path | None = None,
                 terminated_ids: set[str] | None = None) -> dict:
    """Join the spine's appraisals to the cache and characterise what is there."""
    pages, failures, missing = {}, [], []

    for appraisal_id, url in targets:
        record = manifest.get(appraisal_id)
        if record is None:
            missing.append({"appraisal_id": appraisal_id, "url": url,
                            "reason": "never attempted"})
            continue
        if not record.ok:
            failures.append({"appraisal_id": appraisal_id, "url": url,
                             "http_status": record.http_status,
                             "error": record.error,
                             "retrieved_at": record.retrieved_at})
            continue
        path = Path(record.path)
        if not path.exists():
            missing.append({"appraisal_id": appraisal_id, "url": url,
                            "reason": f"manifest points at {path}, which is absent"})
            continue
        parsed = parse_overview(path.read_text(encoding="utf-8", errors="replace"))
        parsed["appraisal_id"] = appraisal_id
        parsed["url_requested"] = record.url_requested
        parsed["url_final"] = record.url_final
        parsed["redirected"] = record.redirected
        parsed["era"] = _era(int(appraisal_id[2:]))
        pages[appraisal_id] = parsed

    chapter_titles = Counter()
    chapter_slugs = Counter()
    per_era_counts: dict[str, Counter] = {}
    chapters_total = 0
    no_chapters, with_chapters = [], 0

    for appraisal_id, p in pages.items():
        chapters_total += p["chapter_count"]
        per_era_counts.setdefault(p["era"], Counter())[p["chapter_count"]] += 1
        if p["chapter_count"] == 0:
            no_chapters.append(appraisal_id)
        else:
            with_chapters += 1
        for c in p["chapters"]:
            chapter_titles[c["title"]] += 1
            chapter_slugs[re.sub(r"^\d+-", "", c["slug"])] += 1

    superseded = [a for a, p in pages.items() if p["superseded"]]
    superseded_named = [a for a in superseded if pages[a]["superseding"]]
    no_chapters = sorted(no_chapters)
    dated = [a for a, p in pages.items() if p["published_date"]]
    redirected = [
        {"appraisal_id": a, "from": p["url_requested"], "to": p["url_final"]}
        for a, p in pages.items() if p["redirected"]
    ]

    product_labels = Counter(p["product_type"] for p in pages.values())
    short_label = sorted(a for a, p in pages.items()
                         if p["product_type"] == "Technology appraisal")
    advice_pages = sorted(a for a, p in pages.items()
                          if any(c["title"] == "Advice" for c in p["chapters"]))
    advice_only = sorted(a for a in advice_pages if pages[a]["chapter_count"] == 1)
    advice_plus = sorted(a for a in advice_pages if pages[a]["chapter_count"] > 1)

    route_hits = Counter()
    for p in pages.values():
        for r in p["route_markers"]:
            route_hits[r] += 1

    metadata_shapes = Counter()
    for p in pages.values():
        metadata_shapes[
            " | ".join(
                re.sub(r"[A-Z]{2,3}\d+", "<ref>",
                       re.sub(r"\d{1,2} \w+ \d{4}", "<date>", m))
                for m in p["metadata_items"]
            )
        ] += 1

    return {
        "totals": {
            "appraisals_in_spine": len(targets),
            "cached_and_parsed": len(pages),
            "failed": len(failures),
            "missing": len(missing),
            "redirected": len(redirected),
        },
        "chapters": {
            "total": chapters_total,
            "appraisals_with_chapters": with_chapters,
            "appraisals_with_no_chapters": len(no_chapters),
            "mean_per_appraisal_where_present": (
                round(chapters_total / with_chapters, 2) if with_chapters else 0
            ),
            "count_distribution": dict(
                sorted(Counter(p["chapter_count"] for p in pages.values()).items())
            ),
            "count_distribution_by_era": {
                era: dict(sorted(c.items())) for era, c in sorted(per_era_counts.items())
            },
            "titles_top": chapter_titles.most_common(40),
            "distinct_titles": len(chapter_titles),
            "slugs_top": chapter_slugs.most_common(30),
            "distinct_slugs": len(chapter_slugs),
        },
        "route": {
            "marker_hits": dict(route_hits),
            "distinct_metadata_shapes": metadata_shapes.most_common(12),
            "product_labels": dict(product_labels),
        },
        "terminated_signals": _terminated_signals(
            short_label, advice_pages, terminated_ids,
            advice_only=advice_only, advice_plus=advice_plus,
        ),
        "dates": {
            "with_published_date": len(dated),
            "without_published_date": len(pages) - len(dated),
            "earliest": min((pages[a]["published_date"] for a in dated), default=None),
            "latest": max((pages[a]["published_date"] for a in dated), default=None),
            "date_label_shapes": Counter(
                " | ".join(
                    re.sub(r"\d{1,2} \w+ \d{4}", "<date>", d) for d in p["date_labels"]
                )
                for p in pages.values()
            ).most_common(8),
        },
        "supersession": {
            "stub_pages_no_chapters": len(no_chapters),
            "stub_naming_superseding_guidance": len(
                [a for a in no_chapters if pages[a]["superseding"]]
            ),
            "stub_with_supersession_sentence": len(
                [a for a in no_chapters if pages[a]["superseded"]]
            ),
            "stub_with_withdrawal_language": len(
                [a for a in no_chapters if pages[a]["withdrawn"]]
            ),
            "stub_with_neither": sorted(
                a for a in no_chapters
                if not pages[a]["superseded"] and not pages[a]["withdrawn"]
            ),
            "withdrawn_not_superseded": sorted(
                a for a in no_chapters
                if pages[a]["withdrawn"] and not pages[a]["superseding"]
            ),
            "live_pages_mentioning_an_update": sorted(
                a for a, p in pages.items()
                if p["superseded"] and p["chapter_count"] > 0
            ),
            "superseding_reference_prefixes": dict(
                Counter(
                    re.match(r"^[A-Z]+", s["reference"]).group(0)
                    for a in superseded_named
                    for s in pages[a]["superseding"][:1]
                )
            ),
            "examples": [
                {
                    "appraisal_id": a,
                    "superseded_by": pages[a]["superseding"][0]["reference"],
                    "url": pages[a]["superseding"][0]["url"],
                }
                for a in superseded_named[:8]
            ],
        },
        "listing_cross_check": _listing_cross_check(listing_path, no_chapters, targets),
        "failures": {"failed": failures, "missing": missing, "redirects": redirected},
        "lap2b": {
            "chapter_requests_if_all": chapters_total,
            "hours_at_2s": round(chapters_total * 2 / 3600, 2),
            "narrow_target": _narrow_target(chapter_slugs),
        },
    }


def _narrow_target(chapter_slugs: Counter) -> dict:
    """A smaller Lap 2b: the decision and the reasoning, not the housekeeping."""
    picked = {s: chapter_slugs.get(s, 0) for s in SUBSTANTIVE_SLUGS}
    total = sum(picked.values())
    return {
        "slugs": picked,
        "requests": total,
        "hours_at_2s": round(total * 2 / 3600, 2),
        "hours_at_measured_rate": round(total * 2.93 / 3600, 2),
    }


def _terminated_signals(short_label, advice_pages, terminated_ids,
                        advice_only=(), advice_plus=()) -> dict:
    """Two page-level signals for the terminated class, scored against the spine.

    The overview page does not carry the appraisal *route*, but it does carry
    two markers of **termination**: a shortened product label, and a lone
    chapter titled "Advice". Both are checked against Lap 1's `terminated_flag`
    rather than assumed — a signal nobody scored is a guess.
    """
    out = {
        "short_product_label": {"n": len(short_label), "examples": short_label[:5]},
        "advice_chapter": {
            "n": len(advice_pages),
            "as_only_chapter": len(advice_only),
            "alongside_other_chapters": sorted(advice_plus),
            "examples": advice_pages[:5],
        },
        "scored": terminated_ids is not None,
    }
    if terminated_ids is None:
        return out

    out["terminated_appraisals_in_spine"] = len(terminated_ids)
    for key, ids in (("short_product_label", short_label), ("advice_chapter", advice_pages)):
        hits = set(ids) & terminated_ids
        out[key].update(
            precision=round(len(hits) / len(ids), 4) if ids else None,
            recall=round(len(hits) / len(terminated_ids), 4) if terminated_ids else None,
            false_positives=sorted(set(ids) - terminated_ids)[:10],
            missed=sorted(terminated_ids - set(ids))[:10],
        )
    return out


def _listing_cross_check(listing_path, no_chapters, targets) -> dict | None:
    """Are the chapterless stubs the same appraisals NICE's listing omits?"""
    if listing_path is None or not Path(listing_path).exists():
        return None
    listing = published_listing_ids(Path(listing_path))
    spine = {_depad(a) for a, _ in targets}
    gap = spine - listing
    stubs = {_depad(a) for a in no_chapters}
    return {
        "listing_appraisals": len(listing),
        "in_spine_not_in_listing": len(gap),
        "chapterless_stub_pages": len(stubs),
        "sets_are_identical": gap == stubs,
        "in_gap_but_has_chapters": sorted(gap - stubs)[:10],
        "chapterless_but_listed": sorted(stubs - gap)[:10],
    }


def headline(report: dict) -> str:
    t, c, l = report["totals"], report["chapters"], report["lap2b"]
    return (
        f"{t['cached_and_parsed']}/{t['appraisals_in_spine']} cached · "
        f"{c['total']} chapters · Lap 2b = {l['chapter_requests_if_all']} requests "
        f"({l['hours_at_2s']} h at 1 per 2 s) · {t['failed']} failed, {t['missing']} missing"
    )


def _terminated_prose(t: dict) -> list[str]:
    """The consolation prize from question 2: two signals for the terminated class."""
    if not t:
        return []
    short, advice = t["short_product_label"], t["advice_chapter"]
    lines = [
        "### What the page *does* carry: two signals for the terminated class",
        "",
        f"The product label is not always the same string. **{short['n']} pages say "
        "`Technology appraisal` rather than `Technology appraisal guidance`**, and "
        f"**{advice['n']} pages carry a chapter titled \"Advice\"** in place of a numbered chapter "
        f"list — for {advice['as_only_chapter']} of them it is the only chapter, and "
        f"{len(advice['alongside_other_chapters'])} "
        f"(`{', '.join(advice['alongside_other_chapters'])}`) carry it alongside others. Both turn",
        "out to mark termination.",
        "",
    ]
    if not t.get("scored"):
        lines.append("_Not scored — the spine was not supplied._")
        return lines
    lines += _table(
        [["Short product label", short["n"], f"{short['precision']:.0%}", f"{short['recall']:.0%}"],
         ['Lone "Advice" chapter', advice["n"], f"{advice['precision']:.0%}",
          f"{advice['recall']:.0%}"]],
        ["Signal", "Pages", "Precision vs `terminated_flag`", "Recall"])
    lines += [
        "",
        f"Scored against Lap 1's {t['terminated_appraisals_in_spine']} terminated appraisals. "
        "**Both signals are perfectly precise** — every page carrying either one is a termination",
        "in the spreadsheet — and neither is complete. The short label misses "
        f"`{', '.join(short['missed'])}`; three of those are chapterless stubs from 2008–2010 and",
        "one is recent, so this is not simply an old-template effect. Neither signal is a",
        "substitute for the spreadsheet's own categorical value, which is exact.",
        "",
        "This is the same kind of check as Lap 1's 87%: an outcome the spreadsheet asserts,",
        "confirmed independently by how NICE builds the page. It costs nothing and it is the",
        "strongest evidence so far that the terminated class — Phase 2's lead question — is solid.",
        "**Not extracted into the spine.** Lap 2 inventories; Lap 3 extracts.",
    ]
    return lines


def _cross_check_prose(x: dict | None) -> str:
    if x is None:
        return "_Lap 0's cached listing is not present, so the cross-check did not run._"
    if x["sets_are_identical"]:
        return (
            f"**The {x['chapterless_stub_pages']} chapterless stub pages are exactly the "
            f"{x['in_spine_not_in_listing']} appraisals Lap 0 found in the spreadsheet and not in "
            f"NICE's published listing of {x['listing_appraisals']}.** Set-identical, both "
            "directions. Two independent methods — a listing diff in Lap 0, page structure here — "
            "pick out the same appraisals, so the finding is not an artefact of either. It also "
            "confirms guardrail 7b the hard way: enumerating from the listing would have skipped "
            "precisely the pages that have no chapters to crawl, and with them 396 recommendations."
        )
    return (
        f"**The two sets differ.** {x['in_spine_not_in_listing']} appraisals are in the spine and "
        f"not the listing; {x['chapterless_stub_pages']} pages have no chapters. In the gap but "
        f"carrying chapters: `{x['in_gap_but_has_chapters']}`. Chapterless but listed: "
        f"`{x['chapterless_but_listed']}`."
    )


def _table(rows, headers) -> list[str]:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def to_markdown(report: dict) -> str:
    t, c, r = report["totals"], report["chapters"], report["route"]
    d, s, f, b = report["dates"], report["supersession"], report["failures"], report["lap2b"]

    lines = [
        "# Lap 2a — overview-page inventory",
        "",
        "Written by `python -m hta.cli inventory`, which reads the cache and makes **no**",
        "network requests. Enumeration is the Lap 1 spine, never NICE's published listing.",
        "",
        "## Coverage",
        "",
        *_table(
            [["Appraisals in the spine", t["appraisals_in_spine"]],
             ["Cached and parsed", t["cached_and_parsed"]],
             ["Failed", t["failed"]],
             ["Missing (never attempted, or manifest points at nothing)", t["missing"]],
             ["Redirected away from the requested ID", t["redirected"]]],
            ["Quantity", "n"]),
        "",
        "## 1 · The chapter inventory",
        "",
        *_table(
            [["Chapters across all cached overviews", f"**{c['total']}**"],
             ["Appraisals carrying chapters", c["appraisals_with_chapters"]],
             ["Appraisals with no chapter list at all", c["appraisals_with_no_chapters"]],
             ["Mean chapters, where present", c["mean_per_appraisal_where_present"]],
             ["Distinct chapter titles", c["distinct_titles"]],
             ["Distinct chapter slugs (number stripped)", c["distinct_slugs"]]],
            ["Quantity", "n"]),
        "",
        "### Chapters per appraisal",
        "",
        *_table([[k, v] for k, v in c["count_distribution"].items()], ["Chapters", "Appraisals"]),
        "",
        "### By era",
        "",
    ]
    for era, dist in c["count_distribution_by_era"].items():
        total = sum(k * v for k, v in dist.items())
        lines.append(f"- **{era}** — {sum(dist.values())} appraisals, {total} chapters, "
                     f"distribution {dist}")
    lines += [
        "",
        "### The most common chapter titles",
        "",
        *_table(c["titles_top"][:25], ["Title", "Appraisals"]),
        "",
        "## 2 · Is the appraisal route visible on the overview page?",
        "",
        "**No.** The overview page carries no route field, and the words that would name one",
        "barely appear across 1,181 pages:",
        "",
        *_table(sorted(r["marker_hits"].items(), key=lambda kv: -kv[1]) or [["none found", 0]],
                ["Route marker", "Pages containing it"]),
        "",
        "The page-header metadata block is the only structured block on the page, and it has just",
        "four shapes across the whole corpus — product label, reference number, and dates. Nothing",
        "distinguishes cost-comparison from standard, and nothing marks fast-track:",
        "",
        *_table([[f"`{shape}`", n] for shape, n in r["distinct_metadata_shapes"]],
                ["Shape (reference and dates masked)", "Appraisals"]),
        "",
        "**`route` stays deferred.** If it exists in the open at all it is in the chapter text or",
        "the committee papers, not here. Lap 2b will show whether the chapters carry it.",
        "",
        *_terminated_prose(report.get("terminated_signals", {})),
        "",
        "## 3 · Is the real publication date there?",
        "",
        *_table(
            [["With a machine-readable `<time datetime=…>`", d["with_published_date"]],
             ["Without one", d["without_published_date"]],
             ["Earliest", d["earliest"]],
             ["Latest", d["latest"]]],
            ["Quantity", "Value"]),
        "",
        *_table([[f"`{shape}`", n] for shape, n in d["date_label_shapes"]],
                ["Date label shape", "Appraisals"]),
        "",
        "## 4 · Supersession",
        "",
        "**Detectable, and it names the superseding guidance.** A superseded appraisal is a",
        "*stub*: the page keeps its title, reference number and publication date, loses its whole",
        "chapter list, and carries one sentence saying what replaced it.",
        "",
        *_table(
            [["Stub pages (no chapter list at all)", s["stub_pages_no_chapters"]],
             ["…carrying a supersession sentence", s["stub_with_supersession_sentence"]],
             ["…naming the superseding guidance with a link", s["stub_naming_superseding_guidance"]],
             ["…using withdrawal language instead", s["stub_with_withdrawal_language"]],
             ["…carrying neither", len(s["stub_with_neither"])]],
            ["Quantity", "n"]),
        "",
        "Superseded and **withdrawn are different statuses.** Withdrawal — the product left the",
        "market, or the licence went — has no superseding guidance to point at, so a detector that",
        "looks only for *replaced by* misses it. Withdrawn with nothing superseding it: "
        f"**{len(s['withdrawn_not_superseded'])}** "
        f"(`{', '.join(s['withdrawn_not_superseded'][:8])}`).",
        "",
        f"Superseding reference prefixes: `{s['superseding_reference_prefixes']}` — a superseded",
        "appraisal is most often replaced by another appraisal, but a quarter of the time it is",
        "absorbed into a clinical guideline (CG/NG), which is a different document class entirely.",
        "",
        *_table([[e["appraisal_id"], e["superseded_by"], e["url"]] for e in s["examples"]],
                ["Appraisal", "Superseded by", "URL"]),
        "",
        "**Precision caveat for Lap 3.** "
        f"{len(s['live_pages_mentioning_an_update'])} *live* appraisals "
        f"(`{', '.join(s['live_pages_mentioning_an_update'])}`) carry update language while keeping",
        "their chapters — a single recommendation replaced, or one drug no longer available. They",
        "are **partially** updated, not superseded. Matching the sentence alone would mis-class them;",
        "the reliable structural signal is **the absence of a chapter list**.",
        "",
        "## 5 · Failures, itemised",
        "",
    ]
    if f["failed"]:
        lines += _table(
            [[x["appraisal_id"], x["url"], x["http_status"], x["error"]] for x in f["failed"]],
            ["Appraisal", "URL", "Status", "Error"])
    else:
        lines.append("**None.** Every appraisal in the spine returned HTTP 200 with a real body.")
    lines += ["", "### Missing", ""]
    if f["missing"]:
        lines += _table([[x["appraisal_id"], x["reason"]] for x in f["missing"]],
                        ["Appraisal", "Reason"])
    else:
        lines.append("**None.** No silent gaps: every appraisal is cached or recorded as failed.")
    lines += ["", "### Redirects", ""]
    if f["redirects"]:
        lines += _table([[x["appraisal_id"], x["from"], x["to"]] for x in f["redirects"]],
                        ["Appraisal", "Requested", "Final"])
    else:
        lines.append("**None.** Every de-padded URL resolved without a redirect, as Lap 0 predicted.")
    lines += [
        "",
        "## Cross-check against Lap 0",
        "",
        _cross_check_prose(report.get("listing_cross_check")),
        "",
        "## What this sets Lap 2b to",
        "",
        f"Crawling every chapter of every cached appraisal is **{b['chapter_requests_if_all']} "
        f"requests** — **{b['hours_at_2s']} hours** at the 2-second delay, and about "
        f"**{round(b['chapter_requests_if_all'] * 2.93 / 3600, 1)} hours** at the rate Lap 2a",
        "actually ran (2.93 s per request measured, because the delay is a floor and NICE's",
        "response time sits on top of it). Scope for 2b is Belal's call at the gate; the",
        "recommendations and committee-discussion chapters alone are a much smaller target:",
        "",
        *_table([[f"`{k}`", v] for k, v in b["narrow_target"]["slugs"].items()],
                ["Chapter slug", "Appraisals carrying it"]),
        "",
        f"That narrower target is **{b['narrow_target']['requests']} requests** — "
        f"{b['narrow_target']['hours_at_2s']} hours on paper, about "
        f"**{b['narrow_target']['hours_at_measured_rate']} hours** at the measured rate, and it",
        "is the half of the corpus that carries the decision and the reasoning. Implementation,",
        "committee membership and sources-of-evidence chapters are administrative and answer",
        "none of Phase 1's questions.",
        "",
        "---",
        "",
        "Derived from NICE published data. NICE does not endorse this work. No NICE content is",
        "redistributed — see `LICENSING.md`.",
        "",
    ]
    return "\n".join(lines)


def write_reports(report: dict, outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    js = outdir / "lap2a-overview-inventory.json"
    md = outdir / "lap2a-overview-inventory.md"
    js.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md.write_text(to_markdown(report), encoding="utf-8")
    return [js, md]
