"""Reading the NICE spreadsheets, and pinning the identity of what was read.

Two things this module exists to defend against:

1. **The phantom range.** openpyxl reports the recommendations workbook as
   16,370 columns x 1,643 rows. The real extent is 9 x 1531. Anything that
   trusts ``max_col`` or ``max_row`` reads mostly emptiness, so every read
   drops all-null rows and columns before returning.
2. **A silently refreshed file.** The spreadsheet trails the NICE website and is
   re-issued without a version marker, so a rebuild against a newer download is
   a *different dataset* wearing the same filename. Every build records the
   sha256 and, by default, refuses to run against an unpinned one.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

#: sha256 of the recommendations workbook profiled in Lap 0 (retrieved 2026-08-19).
PINNED_RECOMMENDATIONS_SHA256 = (
    "04fa1864d0f2e49b3c767e77b6fad1f6f710023f54109cd749913dedac9f377a"
)
#: sha256 of the cancer companion workbook, same retrieval.
PINNED_CANCER_SHA256 = (
    "593564f478e46625467bc6922ff9676d97afedeae70c67a515e9956dce66b7c9"
)

#: The nine real columns, verbatim and in file order.
EXPECTED_COLUMNS = [
    "Rec no.",
    "TA ID",
    "Year of Publication",
    "STA/MTA process",
    "Technology",
    "Technology type",
    "Indication",
    "Categorisation (for specific recommendation)",
    "Comment",
]

_DATE_IN_NAME = re.compile(r"_(\d{4}-\d{2}-\d{2})\.xlsx$")


@dataclass(frozen=True)
class SourceFile:
    """A cached NICE workbook, with the provenance that goes on every row."""

    path: Path
    sha256: str
    retrieved_at: str

    @property
    def name(self) -> str:
        return self.path.name


def sha256_of(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def retrieval_date_from_name(path: str | Path) -> str:
    """Read the retrieval date out of ``ta-recommendations_2026-08-19.xlsx``.

    The cache filename is the only record of when the file was fetched — the
    workbook itself carries no vintage. A file without one is a file whose
    provenance we cannot state, so this raises rather than guessing today.
    """
    m = _DATE_IN_NAME.search(Path(path).name)
    if not m:
        raise ValueError(
            f"cannot read a retrieval date from {Path(path).name!r}; "
            "cached NICE files must be named <slug>_YYYY-MM-DD.xlsx"
        )
    return m.group(1)


def describe(path: str | Path) -> SourceFile:
    path = Path(path)
    return SourceFile(
        path=path,
        sha256=sha256_of(path),
        retrieved_at=retrieval_date_from_name(path),
    )


def read_sheet(path: str | Path) -> pd.DataFrame:
    """Read a NICE recommendations workbook into a tidy frame.

    Drops the phantom all-null rows and columns, then asserts the nine real
    columns are present and in order. Both workbooks (main and the cancer
    companion) share this layout.
    """
    df = pd.read_excel(path, sheet_name=0)
    df = df.dropna(how="all").dropna(axis=1, how="all").reset_index(drop=True)

    if list(df.columns) != EXPECTED_COLUMNS:
        raise ValueError(
            "unexpected sheet layout after dropping empty rows/columns.\n"
            f"  expected: {EXPECTED_COLUMNS}\n"
            f"  found:    {list(df.columns)}"
        )
    return df


def verify_sha256(source: SourceFile, expected: str, *, allow_new_vintage: bool = False) -> None:
    """Fail loudly when the cached file is not the one the counts were measured on."""
    if source.sha256 == expected:
        return
    if allow_new_vintage:
        return
    raise ValueError(
        f"{source.name} is not the pinned vintage.\n"
        f"  expected sha256 {expected}\n"
        f"  found    sha256 {source.sha256}\n"
        "NICE re-issues this file without a version marker, so a different digest "
        "means a different dataset. Re-run with --allow-new-vintage once you have "
        "re-checked the reconciliation, and update the pin."
    )
