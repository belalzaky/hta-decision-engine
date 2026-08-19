"""The real external validity check — runs against the cached NICE file.

Skipped in CI, where `data/raw/` is absent by design (LICENSING.md §7). This is
the test that proves the *actual* NICE spreadsheet still produces 1531 / 1181
and reproduces NICE's published 87%; the surrogate elsewhere proves the mapping
logic, but only this one is checked against reality.
"""
import json
from pathlib import Path

import pytest

from hta import excel, reconcile
from hta.spine import build_spine

# Resolved here rather than imported from conftest: `tests` is not an importable
# package (no __init__.py, and CI runs bare `pytest`, which does not put the repo
# root on sys.path), so a cross-test import works locally and breaks in CI.
REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
RAW_RECOMMENDATIONS = REPO_ROOT / "data" / "raw" / "ta-recommendations_2026-08-19.xlsx"
RAW_CANCER = REPO_ROOT / "data" / "raw" / "ta-cancer-recommendations_2026-08-19.xlsx"

pytestmark = pytest.mark.skipif(
    not RAW_RECOMMENDATIONS.exists(),
    reason="raw NICE cache absent (never redistributed — see LICENSING.md)",
)


def _build():
    source = excel.describe(RAW_RECOMMENDATIONS)
    raw = excel.read_sheet(RAW_RECOMMENDATIONS)
    cancer = excel.read_sheet(RAW_CANCER) if RAW_CANCER.exists() else None
    return build_spine(raw, source=source, cancer=cancer), source, raw, cancer


def test_the_cached_file_is_the_pinned_vintage():
    source = excel.describe(RAW_RECOMMENDATIONS)
    assert source.sha256 == excel.PINNED_RECOMMENDATIONS_SHA256
    assert source.retrieved_at == "2026-08-19"
    if RAW_CANCER.exists():
        assert excel.sha256_of(RAW_CANCER) == excel.PINNED_CANCER_SHA256


def test_real_file_reconciles_and_reproduces_the_87_percent():
    spine, source, _, cancer = _build()
    report = reconcile.reconcile(
        spine, sources={"recommendations": {"file": source.name}, "cancer": {"file": "cancer"}}
    )
    checks = reconcile.verify(report)
    assert [(n, d) for n, ok, d in checks if not ok] == []

    s = report["positive_shares"]
    assert (s["all"]["numerator"], s["all"]["denominator"], s["all"]["pct"]) == (1156, 1531, 75.51)
    assert s["excl_non_submission"]["pct"] == 85.19
    assert s["nice_denominator"]["pct"] == 87.11
    assert report["counts"]["is_cancer"] == 662


def test_cancer_companion_is_an_exact_subset_on_ta_id_and_rec_no():
    _, _, raw, cancer = _build()
    main_keys = set(zip(raw["TA ID"], raw["Rec no."].astype(int)))
    cancer_keys = set(zip(cancer["TA ID"], cancer["Rec no."].astype(int)))
    assert len(cancer) == len(cancer_keys) == 662
    assert cancer_keys <= main_keys


def test_the_surrogate_still_matches_the_real_marginals():
    """If NICE reissues the file, the fixture must be regenerated, not drift."""
    _, _, raw, cancer = _build()
    marginals = json.loads((FIXTURES / "nice_marginals.json").read_text(encoding="utf-8"))

    assert marginals["recommendations"] == len(raw)
    assert marginals["appraisals"] == raw["TA ID"].nunique()
    assert marginals["cancer_recommendations"] == len(cancer)
    assert marginals["categorisation"] == (
        raw["Categorisation (for specific recommendation)"].value_counts().to_dict()
    )
    assert marginals["sta_mta_process"] == raw["STA/MTA process"].value_counts().to_dict()
    assert marginals["technology_type"] == raw["Technology type"].value_counts().to_dict()
    per = raw.groupby("TA ID").size().value_counts().sort_index()
    assert marginals["recommendations_per_appraisal"] == {str(k): int(v) for k, v in per.items()}


def test_real_urls_and_ids():
    spine, *_ = _build()
    ta81 = spine[spine["appraisal_id"] == "TA081"]
    assert len(ta81) == 16                       # the widest appraisal in the file
    assert ta81["appraisal_url"].unique().tolist() == [
        "https://www.nice.org.uk/guidance/ta81"
    ]
    assert ta81["recommendation_id"].tolist()[-1] == "TA081-16"
    assert spine["year_published_raw"].min() == "1999/00"
    assert spine["year_published_raw"].max() == "2026/27"


def test_technology_type_case_variant_is_preserved_not_silently_folded():
    """`Medical device` (46) and `Medical Device` (1) are one category with two
    spellings. Schema v1 specifies no normalised sibling, so it ships verbatim
    and the trap is documented rather than hidden."""
    spine, *_ = _build()
    counts = spine["technology_type_raw"].value_counts()
    assert counts["Medical device"] == 46
    assert counts["Medical Device"] == 1
