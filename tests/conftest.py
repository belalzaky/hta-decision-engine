"""Shared fixtures.

The raw NICE spreadsheet is **never redistributed** (LICENSING.md §7), so it is
absent in CI. Tests therefore run against a *structural surrogate*: a 1531-row
frame rebuilt from `tests/fixtures/nice_marginals.json`, which carries only the
marginal counts and the short verbatim categorical values — no NICE free text.

The surrogate reproduces every quantity the 87% check depends on (1531 rows,
1181 gapless appraisals, the exact 12-way categorisation distribution), so the
outcome mapping is genuinely exercised in CI rather than mocked. What it cannot
do is prove the *real* file still looks like this; that is `test_real_file.py`,
which runs locally against `data/raw/` and skips when the cache is absent.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from hta.excel import EXPECTED_COLUMNS, SourceFile

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
RAW_RECOMMENDATIONS = REPO_ROOT / "data" / "raw" / "ta-recommendations_2026-08-19.xlsx"
RAW_CANCER = REPO_ROOT / "data" / "raw" / "ta-cancer-recommendations_2026-08-19.xlsx"

needs_raw_cache = pytest.mark.skipif(
    not RAW_RECOMMENDATIONS.exists(),
    reason="raw NICE cache absent (never redistributed — see LICENSING.md)",
)


@pytest.fixture(scope="session")
def marginals() -> dict:
    return json.loads((FIXTURES / "nice_marginals.json").read_text(encoding="utf-8"))


def _spread(counts: dict[str, int], n: int) -> list[str]:
    """Expand ``{value: count}`` into a length-n list, values interleaved.

    Deterministic and stride-based rather than random, so a failure is always
    reproducible. Interleaving matters: if every terminated row sat at the end,
    a bug that dropped the tail would still pass the count checks.
    """
    pool = [v for value, c in counts.items() for v in [value] * c]
    if len(pool) != n:
        raise ValueError(f"counts sum to {len(pool)}, expected {n}")
    order = sorted(range(n), key=lambda i: (i * 397) % n)
    out = [None] * n
    for slot, value in zip(order, pool):
        out[slot] = value
    return out


@pytest.fixture(scope="session")
def surrogate_raw(marginals) -> pd.DataFrame:
    """A 1531-row stand-in with NICE's real marginals and no NICE text."""
    n = marginals["recommendations"]
    n_appraisals = marginals["appraisals"]

    sizes = [
        int(size)
        for size, count in marginals["recommendations_per_appraisal"].items()
        for _ in range(count)
    ]
    assert len(sizes) == n_appraisals and sum(sizes) == n
    order = sorted(range(n_appraisals), key=lambda i: (i * 397) % n_appraisals)
    by_appraisal = [0] * n_appraisals
    for slot, size in zip(order, sizes):
        by_appraisal[slot] = size

    ta_ids: list[str] = []
    for i, size in enumerate(by_appraisal, start=1):
        ta_ids += [f"TA{i:03d}"] * size

    categories = _spread(marginals["categorisation"], n)
    processes = _spread(marginals["sta_mta_process"], n)
    tech_types = _spread(marginals["technology_type"], n)
    years = [f"{1999 + (i * 27) // n}/{(2000 + (i * 27) // n) % 100:02d}" for i in range(n)]

    return pd.DataFrame(
        {
            "Rec no.": list(range(1, n + 1)),
            "TA ID": ta_ids,
            "Year of Publication": years,
            "STA/MTA process": processes,
            "Technology": [f"Technology {i}" for i in range(1, n + 1)],
            "Technology type": tech_types,
            "Indication": [f"Condition {i}" for i in range(1, n + 1)],
            "Categorisation (for specific recommendation)": categories,
            "Comment": [f"Comment {i}" for i in range(1, n + 1)],
        },
        columns=EXPECTED_COLUMNS,
    )


@pytest.fixture(scope="session")
def surrogate_cancer(marginals, surrogate_raw) -> pd.DataFrame:
    """An exact 662-row subset of the surrogate, as the real companion file is."""
    k = marginals["cancer_recommendations"]
    n = len(surrogate_raw)
    picked = sorted(sorted(range(n), key=lambda i: (i * 811) % n)[:k])
    return surrogate_raw.iloc[picked].reset_index(drop=True)


@pytest.fixture(scope="session")
def surrogate_source(marginals) -> SourceFile:
    return SourceFile(
        path=Path(marginals["source_file"]),
        sha256=marginals["source_sha256"],
        retrieved_at=marginals["retrieved_at"],
    )
