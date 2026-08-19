"""Reading the workbook — the phantom range, and pinning the file's identity."""
import pandas as pd
import pytest

from hta import excel


def _write(path, df, *, pad_rows=0, pad_cols=0):
    """Write a sheet with trailing empty rows/columns, as NICE's file has."""
    df = df.copy()
    for c in range(pad_cols):
        df[f"__pad{c}"] = pd.NA
    if pad_rows:
        blank = pd.DataFrame([[pd.NA] * len(df.columns)] * pad_rows, columns=df.columns)
        df = pd.concat([df, blank], ignore_index=True)
    df.to_excel(path, index=False)
    return path


def test_read_sheet_drops_the_phantom_rows_and_columns(tmp_path, surrogate_raw):
    """openpyxl reports NICE's file as 16,370 x 1,643; the real extent is 9 x 1531."""
    path = _write(tmp_path / "ta-recommendations_2026-08-19.xlsx",
                  surrogate_raw.head(20), pad_rows=40, pad_cols=25)
    df = excel.read_sheet(path)
    assert df.shape == (20, 9)
    assert list(df.columns) == excel.EXPECTED_COLUMNS


def test_read_sheet_rejects_an_unexpected_layout(tmp_path, surrogate_raw):
    renamed = surrogate_raw.head(5).rename(columns={"TA ID": "Appraisal"})
    path = _write(tmp_path / "ta-recommendations_2026-08-19.xlsx", renamed)
    with pytest.raises(ValueError, match="unexpected sheet layout"):
        excel.read_sheet(path)


def test_retrieval_date_comes_from_the_filename(tmp_path):
    assert excel.retrieval_date_from_name("ta-recommendations_2026-08-19.xlsx") == "2026-08-19"


def test_a_file_with_no_retrieval_date_is_refused():
    """The workbook carries no vintage of its own, so an undated cache has no provenance."""
    with pytest.raises(ValueError, match="retrieval date"):
        excel.retrieval_date_from_name("ta-recommendations.xlsx")


def test_sha_mismatch_fails_loudly(tmp_path, surrogate_raw):
    path = _write(tmp_path / "ta-recommendations_2026-08-19.xlsx", surrogate_raw.head(3))
    source = excel.describe(path)
    with pytest.raises(ValueError, match="not the pinned vintage"):
        excel.verify_sha256(source, excel.PINNED_RECOMMENDATIONS_SHA256)
    excel.verify_sha256(source, excel.PINNED_RECOMMENDATIONS_SHA256, allow_new_vintage=True)
    excel.verify_sha256(source, source.sha256)
