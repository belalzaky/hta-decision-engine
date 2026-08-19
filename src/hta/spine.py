"""Build the spine: one row per NICE recommendation.

The unit of analysis is the **recommendation, not the appraisal**. 1531
recommendations sit under 1181 appraisals because multi-technology and
multi-population appraisals split; one row per appraisal silently drops ~350 of
them (~23%). The appraisal is a parent key, nothing more.
"""
from __future__ import annotations

import pandas as pd

from hta import normalise
from hta.excel import SourceFile

#: Column order of the published spine: identity and provenance, then NICE's
#: own words untouched, then everything derived from them.
COLUMNS = [
    # identity
    "recommendation_id",
    "recommendation_seq",
    "appraisal_id",
    "appraisal_url",
    # verbatim from NICE, never overwritten
    "technology_raw",
    "technology_type_raw",
    "condition_raw",
    "sta_mta_process_raw",
    "recommendation_category_raw",
    "nice_comments_raw",
    "year_published_raw",
    # normalised, always beside its source
    "process_type",
    "review_type",
    "outcome",
    "terminated_flag",
    "is_cancer",
    # provenance
    "source_file",
    "retrieved_at",
    "source_sha256",
]

_RENAMES = {
    "Rec no.": "recommendation_seq",
    "TA ID": "appraisal_id",
    "Year of Publication": "year_published_raw",
    "STA/MTA process": "sta_mta_process_raw",
    "Technology": "technology_raw",
    "Technology type": "technology_type_raw",
    "Indication": "condition_raw",
    "Categorisation (for specific recommendation)": "recommendation_category_raw",
    "Comment": "nice_comments_raw",
}


def cancer_keys(cancer_df: pd.DataFrame) -> set[tuple[str, int]]:
    """``(TA ID, Rec no.)`` pairs from NICE's cancer companion file.

    The companion has identical columns to the main file and its rows are an
    exact subset of it, so it functions as a NICE-authored ``is_cancer`` flag —
    free, and it controls the exact confounder the spec warns about (an
    "oncology drugs get approved" model that has learned the base rate).
    """
    return set(zip(cancer_df["TA ID"], cancer_df["Rec no."].astype(int)))


def build_spine(
    raw: pd.DataFrame,
    *,
    source: SourceFile,
    cancer: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Turn the raw sheet into the recommendation-level table."""
    df = raw.rename(columns=_RENAMES).copy()

    missing = set(_RENAMES.values()) - set(df.columns)
    if missing:
        raise ValueError(f"raw frame is missing columns: {sorted(missing)}")

    df["recommendation_seq"] = df["recommendation_seq"].astype(int)
    df["appraisal_id"] = df["appraisal_id"].astype(str).str.strip()

    # Sort by NICE's own contiguous Rec no. so the within-appraisal sequence that
    # forms recommendation_id is stable across rebuilds.
    df = df.sort_values("recommendation_seq", kind="stable").reset_index(drop=True)

    seq_within = df.groupby("appraisal_id").cumcount() + 1
    df["recommendation_id"] = [
        normalise.recommendation_id(ta, i) for ta, i in zip(df["appraisal_id"], seq_within)
    ]
    df["appraisal_url"] = [normalise.appraisal_url(ta) for ta in df["appraisal_id"]]

    _check_exhaustive(df)
    df["outcome"] = [normalise.map_outcome(v) for v in df["recommendation_category_raw"]]
    split = [normalise.split_process(v) for v in df["sta_mta_process_raw"]]
    df["process_type"] = [p for p, _ in split]
    df["review_type"] = [r for _, r in split]
    df["terminated_flag"] = df["outcome"] == normalise.TERMINATED_OUTCOME

    keys = cancer_keys(cancer) if cancer is not None else set()
    df["is_cancer"] = [
        (ta, int(seq)) in keys
        for ta, seq in zip(df["appraisal_id"], df["recommendation_seq"])
    ]

    df["source_file"] = source.name
    df["retrieved_at"] = source.retrieved_at
    df["source_sha256"] = source.sha256

    out = df[COLUMNS]
    _assert_wellformed(out)
    return out


def _check_exhaustive(df: pd.DataFrame) -> None:
    """Report *all* unmapped categories at once, not one per rebuild."""
    unknown_outcome = set(df["recommendation_category_raw"]) - set(normalise.OUTCOME_MAP)
    if unknown_outcome:
        normalise._fail("Categorisation (for specific recommendation)", unknown_outcome)


def _assert_wellformed(df: pd.DataFrame) -> None:
    if df["recommendation_id"].duplicated().any():
        dupes = df.loc[df["recommendation_id"].duplicated(), "recommendation_id"].tolist()
        raise ValueError(f"recommendation_id is not unique: {dupes[:5]}")
    if df["recommendation_seq"].duplicated().any():
        raise ValueError("recommendation_seq is not unique — NICE's Rec no. should be a key")
    for col in ("terminated_flag", "is_cancer"):
        if df[col].isna().any():
            raise ValueError(f"{col} must be boolean and never null")
