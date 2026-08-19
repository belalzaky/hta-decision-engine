"""End-to-end: one command rebuilds the whole table, offline."""
import json

import pandas as pd
import pytest

from hta import cli, reconcile
from hta.spine import COLUMNS


def _cache(tmp_path, raw, cancer=None):
    raw_path = tmp_path / "ta-recommendations_2026-08-19.xlsx"
    raw.to_excel(raw_path, index=False)
    if cancer is None:
        return raw_path, tmp_path / "absent_2026-08-19.xlsx"
    cancer_path = tmp_path / "ta-cancer-recommendations_2026-08-19.xlsx"
    cancer.to_excel(cancer_path, index=False)
    return raw_path, cancer_path


def _run(tmp_path, raw_path, cancer_path, *extra):
    return cli.main([
        "build",
        "--raw", str(raw_path),
        "--cancer", str(cancer_path),
        "--outdir", str(tmp_path / "processed"),
        "--results", str(tmp_path / "results"),
        "--allow-new-vintage",   # the surrogate is not the pinned NICE file
        *extra,
    ])


def test_build_writes_csv_parquet_and_the_reconciliation(
    tmp_path, surrogate_raw, surrogate_cancer
):
    raw_path, cancer_path = _cache(tmp_path, surrogate_raw, surrogate_cancer)
    assert _run(tmp_path, raw_path, cancer_path) == 0

    csv = tmp_path / "processed" / "nice_ta_recommendations_spine.csv"
    parquet = tmp_path / "processed" / "nice_ta_recommendations_spine.parquet"
    assert csv.exists() and parquet.exists()

    from_csv = pd.read_csv(csv)
    from_parquet = pd.read_parquet(parquet)
    assert list(from_csv.columns) == COLUMNS
    assert len(from_csv) == len(from_parquet) == 1531
    assert from_csv["appraisal_id"].nunique() == 1181

    report = json.loads((tmp_path / "results" / "reconciliation.json").read_text())
    assert report["counts"]["recommendations"] == 1531
    assert report["positive_shares"]["nice_denominator"]["pct"] == 87.11
    assert all(c["pass"] for c in report["checks"])
    assert "87.11%" in (tmp_path / "results" / "reconciliation.md").read_text()


def test_csv_and_parquet_carry_the_same_table(tmp_path, surrogate_raw, surrogate_cancer):
    raw_path, cancer_path = _cache(tmp_path, surrogate_raw, surrogate_cancer)
    _run(tmp_path, raw_path, cancer_path)
    csv = pd.read_csv(tmp_path / "processed" / "nice_ta_recommendations_spine.csv")
    parquet = pd.read_parquet(tmp_path / "processed" / "nice_ta_recommendations_spine.parquet")
    assert csv["recommendation_id"].tolist() == parquet["recommendation_id"].tolist()
    assert csv["outcome"].tolist() == parquet["outcome"].tolist()
    # parquet keeps the booleans as booleans; CSV cannot
    assert parquet["is_cancer"].dtype == bool
    assert int(parquet["is_cancer"].sum()) == 662


def test_build_runs_without_the_cancer_companion(tmp_path, surrogate_raw, capsys):
    raw_path, cancer_path = _cache(tmp_path, surrogate_raw)
    assert _run(tmp_path, raw_path, cancer_path) == 0
    assert "is_cancer will be False" in capsys.readouterr().err


def test_build_fails_when_the_reconciliation_drifts(tmp_path, surrogate_raw, surrogate_cancer):
    """A rebuild that no longer matches Lap 0 must fail, not quietly publish."""
    short = surrogate_raw.iloc[:-1]
    raw_path, cancer_path = _cache(tmp_path, short, surrogate_cancer)
    with pytest.raises(reconcile.ReconciliationError):
        _run(tmp_path, raw_path, cancer_path)


def test_no_verify_writes_anyway_for_diagnosis(tmp_path, surrogate_raw, surrogate_cancer):
    short = surrogate_raw.iloc[:-1]
    raw_path, cancer_path = _cache(tmp_path, short, surrogate_cancer)
    assert _run(tmp_path, raw_path, cancer_path, "--no-verify") == 0
    report = json.loads((tmp_path / "results" / "reconciliation.json").read_text())
    assert not all(c["pass"] for c in report["checks"])


def test_missing_raw_file_explains_itself(tmp_path, capsys):
    code = cli.main(["build", "--raw", str(tmp_path / "nope_2026-08-19.xlsx"),
                     "--cancer", str(tmp_path / "nope2_2026-08-19.xlsx"),
                     "--outdir", str(tmp_path / "p"), "--results", str(tmp_path / "r")])
    assert code == 2
    assert "LICENSING.md" in capsys.readouterr().err


def test_an_unpinned_raw_file_is_refused_by_default(tmp_path, surrogate_raw):
    """NICE re-issues this file without a version marker; a new digest is a new dataset."""
    raw_path, cancer_path = _cache(tmp_path, surrogate_raw)
    with pytest.raises(ValueError, match="not the pinned vintage"):
        cli.main(["build", "--raw", str(raw_path), "--cancer", str(cancer_path),
                  "--outdir", str(tmp_path / "p"), "--results", str(tmp_path / "r")])
