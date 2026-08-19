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

_SUPERSESSION = re.compile(
    r"(has been (?:updated and )?replaced|no longer (?:current|available)|"
    r"has been withdrawn|this guidance has been updated)",
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

    superseded = bool(_SUPERSESSION.search(_clean(body)))
    superseding = []
    if superseded:
        for href, ref, label in _SUPERSEDING_LINK.findall(body):
            if not href.rstrip("/").endswith(ref):
                continue
            superseding.append({"reference": ref.upper(), "url": href,
                                "label": _clean(label)})

    plain = _clean(body)
    routes = [name for name, rx in ROUTE_MARKERS.items() if rx.search(plain)]

    title = _TITLE.search(page)
    reference = _REFERENCE.search(body)

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
        "superseding": superseding[:3],
        "route_markers": routes,
        "bytes": len(page),
    }


def _era(appraisal_number: int) -> str:
    if appraisal_number <= 200:
        return "TA1-200"
    if appraisal_number <= 500:
        return "TA201-500"
    if appraisal_number <= 800:
        return "TA501-800"
    return "TA801-1181"


def build_report(targets, manifest, root: Path) -> dict:
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
    dated = [a for a, p in pages.items() if p["published_date"]]
    redirected = [
        {"appraisal_id": a, "from": p["url_requested"], "to": p["url_final"]}
        for a, p in pages.items() if p["redirected"]
    ]

    route_hits = Counter()
    for p in pages.values():
        for r in p["route_markers"]:
            route_hits[r] += 1

    metadata_shapes = Counter()
    for p in pages.values():
        metadata_shapes[
            " | ".join(
                re.sub(r"\d{1,2} \w+ \d{4}", "<date>", m) for m in p["metadata_items"]
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
        },
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
            "detected": len(superseded),
            "naming_the_superseding_guidance": len(superseded_named),
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
            "no_chapters_and_superseded": len(
                [a for a in no_chapters if pages[a]["superseded"]]
            ),
        },
        "failures": {"failed": failures, "missing": missing, "redirects": redirected},
        "lap2b": {
            "chapter_requests_if_all": chapters_total,
            "hours_at_2s": round(chapters_total * 2 / 3600, 2),
        },
    }


def headline(report: dict) -> str:
    t, c, l = report["totals"], report["chapters"], report["lap2b"]
    return (
        f"{t['cached_and_parsed']}/{t['appraisals_in_spine']} cached · "
        f"{c['total']} chapters · Lap 2b = {l['chapter_requests_if_all']} requests "
        f"({l['hours_at_2s']} h at 1 per 2 s) · {t['failed']} failed, {t['missing']} missing"
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
        *_table(sorted(r["marker_hits"].items(), key=lambda kv: -kv[1]) or [["none found", 0]],
                ["Route marker", "Pages containing it"]),
        "",
        "### Distinct shapes of the page-header metadata block",
        "",
        *_table([[f"`{shape}`", n] for shape, n in r["distinct_metadata_shapes"]],
                ["Shape (dates masked)", "Appraisals"]),
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
        *_table(
            [["Overviews carrying a supersession sentence", s["detected"]],
             ["…that name the superseding guidance with a link", s["naming_the_superseding_guidance"]],
             ["…that also have no chapter list", s["no_chapters_and_superseded"]]],
            ["Quantity", "n"]),
        "",
        f"Superseding reference prefixes: `{s['superseding_reference_prefixes']}`",
        "",
        *_table([[e["appraisal_id"], e["superseded_by"], e["url"]] for e in s["examples"]],
                ["Appraisal", "Superseded by", "URL"]),
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
        "## What this sets Lap 2b to",
        "",
        f"Crawling every chapter of every cached appraisal is **{b['chapter_requests_if_all']} "
        f"requests** — about **{b['hours_at_2s']} hours** at 1 per 2 seconds, sequential.",
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
