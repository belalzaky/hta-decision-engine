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

from hta import excel, reconcile
from hta.spine import build_spine

DEFAULT_RAW = Path("data/raw/ta-recommendations_2026-08-19.xlsx")
DEFAULT_CANCER = Path("data/raw/ta-cancer-recommendations_2026-08-19.xlsx")
DEFAULT_PROCESSED = Path("data/processed")
DEFAULT_RESULTS = Path("results")
STEM = "nice_ta_recommendations_spine"


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

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
