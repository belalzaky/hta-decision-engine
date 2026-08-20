"""Command-line entry point.

One command rebuilds the whole table from the cached raw file, offline:

    python -m hta.cli build

It reads only from ``data/raw/``, writes CSV and parquet to ``data/processed/``
and the reconciliation to ``results/``, and **fails** if the counts or the 87%
check drift from what Lap 0 measured. Nothing here touches the network.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from hta import crawl as crawl_mod
from hta import excel, inventory, reconcile
from hta.spine import build_spine

DEFAULT_RAW = Path("data/raw/ta-recommendations_2026-08-19.xlsx")
DEFAULT_CANCER = Path("data/raw/ta-cancer-recommendations_2026-08-19.xlsx")
DEFAULT_PROCESSED = Path("data/processed")
DEFAULT_RESULTS = Path("results")
STEM = "nice_ta_recommendations_spine"
DEFAULT_GUIDANCE_CACHE = Path("data/raw/guidance")
MANIFEST_NAME = "manifest.jsonl"


def _targets_from_spine(spine_path: Path) -> list[tuple[str, str]]:
    """One (appraisal_id, url) per appraisal, from the Lap 1 spine.

    The spine is the enumeration source — guardrail 7b. NICE's published
    listing omits 260 live appraisals and omits them non-randomly.
    """
    spine = pd.read_parquet(spine_path)
    pairs = (
        spine[["appraisal_id", "appraisal_url"]]
        .drop_duplicates()
        .assign(_n=lambda d: d["appraisal_id"].str.slice(2).astype(int))
        .sort_values("_n")
    )
    return list(zip(pairs["appraisal_id"], pairs["appraisal_url"]))


def _build(args) -> int:
    raw_path, cancer_path = Path(args.raw), Path(args.cancer)
    if not raw_path.exists():
        print(
            f"error: {raw_path} not found.\n"
            "The raw NICE cache is not redistributed (see LICENSING.md); download the\n"
            "'Technology appraisal recommendations (Excel)' file from NICE and save it\n"
            "under data/raw/ with its retrieval date in the name.",
            file=sys.stderr,
        )
        return 2

    source = excel.describe(raw_path)
    excel.verify_sha256(
        source,
        excel.PINNED_RECOMMENDATIONS_SHA256,
        allow_new_vintage=args.allow_new_vintage,
    )
    raw = excel.read_sheet(raw_path)

    sources = {
        "recommendations": {
            "file": source.name,
            "sha256": source.sha256,
            "retrieved_at": source.retrieved_at,
        }
    }

    cancer = None
    if cancer_path.exists():
        cancer_src = excel.describe(cancer_path)
        excel.verify_sha256(
            cancer_src,
            excel.PINNED_CANCER_SHA256,
            allow_new_vintage=args.allow_new_vintage,
        )
        cancer = excel.read_sheet(cancer_path)
        sources["cancer"] = {
            "file": cancer_src.name,
            "sha256": cancer_src.sha256,
            "retrieved_at": cancer_src.retrieved_at,
        }
    else:
        print(
            f"warning: {cancer_path} not found — is_cancer will be False on every row",
            file=sys.stderr,
        )

    spine = build_spine(raw, source=source, cancer=cancer)

    processed = Path(args.outdir)
    processed.mkdir(parents=True, exist_ok=True)
    csv_path = processed / f"{STEM}.csv"
    parquet_path = processed / f"{STEM}.parquet"
    spine.to_csv(csv_path, index=False)
    spine.to_parquet(parquet_path, index=False)

    report = reconcile.reconcile(spine, sources=sources)
    checks = reconcile.verify(report)
    written = reconcile.write_reports(report, checks, Path(args.results))

    for path in [csv_path, parquet_path, *written]:
        print(f"wrote {path}", file=sys.stderr)

    counts = report["counts"]
    print(
        f"{counts['recommendations']} recommendations across {counts['appraisals']} appraisals",
        file=sys.stderr,
    )
    for name, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name} -> {detail}", file=sys.stderr)

    if not args.no_verify:
        reconcile.raise_on_drift(checks)
    return 0


def _crawl_overviews(args) -> int:
    spine_path = Path(args.spine)
    if not spine_path.exists():
        print(f"error: {spine_path} not found — run `hta build` first.", file=sys.stderr)
        return 2

    targets = _targets_from_spine(spine_path)
    root = Path(args.cache)
    print(f"{len(targets)} appraisals enumerated from the spine", file=sys.stderr)

    summary = crawl_mod.crawl(
        targets,
        root,
        root / MANIFEST_NAME,
        delay=args.delay,
        limit=args.limit,
        log=lambda m: print(m, file=sys.stderr),
    )
    print(
        f"requested {summary['requested']}, ok {summary['ok']}, "
        f"failed {summary['failed']}, already cached {summary['skipped']}",
        file=sys.stderr,
    )
    return 0


def _crawl_chapters(args) -> int:
    root = Path(args.cache)
    overview_manifest = root / MANIFEST_NAME
    if not overview_manifest.exists():
        print(f"error: {overview_manifest} not found — run `crawl-overviews` first.",
              file=sys.stderr)
        return 2

    slugs = (
        tuple(s.strip() for s in args.slugs.split(",") if s.strip())
        if args.slugs else inventory.SUBSTANTIVE_SLUGS
    )
    targets = inventory.chapter_targets(
        _targets_from_spine(Path(args.spine)),
        crawl_mod.read_manifest(overview_manifest),
        slugs=slugs,
    )
    print(f"{len(targets)} chapters to consider, from cached overviews only "
          f"(slugs: {', '.join(slugs)})", file=sys.stderr)

    chapter_root = root / "chapters"
    summary = crawl_mod.crawl(
        targets,
        chapter_root,
        chapter_root / MANIFEST_NAME,
        delay=args.delay,
        limit=args.limit,
        log=lambda m: print(m, file=sys.stderr),
    )
    print(
        f"requested {summary['requested']}, ok {summary['ok']}, "
        f"failed {summary['failed']}, already cached {summary['skipped']}",
        file=sys.stderr,
    )
    return 0


def _inventory(args) -> int:
    root = Path(args.cache)
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.exists():
        print(f"error: {manifest_path} not found — run `crawl-overviews` first.",
              file=sys.stderr)
        return 2

    targets = _targets_from_spine(Path(args.spine))
    listing = Path(args.listing)
    spine = pd.read_parquet(args.spine)
    terminated = set(spine.loc[spine["terminated_flag"], "appraisal_id"])
    report = inventory.build_report(
        targets, crawl_mod.read_manifest(manifest_path), root,
        listing_path=listing if listing.exists() else None,
        terminated_ids=terminated,
    )
    written = inventory.write_reports(report, Path(args.results))
    for path in written:
        print(f"wrote {path}", file=sys.stderr)
    print(inventory.headline(report), file=sys.stderr)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="hta",
        description="Build the NICE technology appraisal recommendation spine, offline.",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="rebuild the spine from the cached NICE spreadsheet")
    b.add_argument("--raw", default=str(DEFAULT_RAW), help="cached recommendations .xlsx")
    b.add_argument("--cancer", default=str(DEFAULT_CANCER), help="cached cancer companion .xlsx")
    b.add_argument("--outdir", default=str(DEFAULT_PROCESSED), help="where CSV/parquet go")
    b.add_argument("--results", default=str(DEFAULT_RESULTS), help="where the reconciliation goes")
    b.add_argument(
        "--allow-new-vintage",
        action="store_true",
        help="accept a raw file whose sha256 is not the pinned one",
    )
    b.add_argument(
        "--no-verify",
        action="store_true",
        help="write the outputs even if the reconciliation fails (diagnostics only)",
    )
    b.set_defaults(func=_build)

    c = sub.add_parser(
        "crawl-overviews",
        help="Lap 2a: cache /guidance/taXXXX for every appraisal in the spine",
    )
    c.add_argument("--spine", default=str(DEFAULT_PROCESSED / f"{STEM}.parquet"))
    c.add_argument("--cache", default=str(DEFAULT_GUIDANCE_CACHE))
    c.add_argument("--delay", type=float, default=crawl_mod.DELAY_SECONDS,
                   help="seconds between requests (default 2.0 — twice robots.txt)")
    c.add_argument("--limit", type=int, default=None,
                   help="stop after N requests (for a smoke test, not for the real run)")
    c.set_defaults(func=_crawl_overviews)

    ch = sub.add_parser(
        "crawl-chapters",
        help="Lap 2b: cache the substantive chapters linked from the cached overviews",
    )
    ch.add_argument("--spine", default=str(DEFAULT_PROCESSED / f"{STEM}.parquet"))
    ch.add_argument("--cache", default=str(DEFAULT_GUIDANCE_CACHE))
    ch.add_argument("--delay", type=float, default=crawl_mod.DELAY_SECONDS)
    ch.add_argument("--limit", type=int, default=None)
    ch.add_argument("--slugs", default=None,
                    help="comma-separated chapter slugs (default: the substantive set)")
    ch.set_defaults(func=_crawl_chapters)

    i = sub.add_parser(
        "inventory",
        help="Lap 2a: read the cache (never the network) and write the report",
    )
    i.add_argument("--spine", default=str(DEFAULT_PROCESSED / f"{STEM}.parquet"))
    i.add_argument("--cache", default=str(DEFAULT_GUIDANCE_CACHE))
    i.add_argument("--results", default=str(DEFAULT_RESULTS))
    i.add_argument("--listing",
                   default="data/raw/ta-published-listing_2026-08-19.json",
                   help="Lap 0's cached published listing, for the cross-check")
    i.set_defaults(func=_inventory)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
