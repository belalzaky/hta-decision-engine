"""Reconciliation and the 87% external validity check.

Two jobs.

**Reconcile the counts.** Three appraisal counts were in circulation before Lap 0
(880, 1094, 1181) and two units of analysis (appraisal and recommendation). The
build states its own denominators every time it runs so no published percentage
can quietly rest on the wrong one.

**Check the outcome mapping against NICE.** NICE publishes "87% of our
recommendations have been positive". That figure is reproducible from this
mapping only if the mapping is right, and it pins down a denominator NICE does
not state — the 87% excludes both non-submissions *and* only-in-research. It is
therefore an external check, not a self-consistency check: if the normalisation
drifts, 87.11% moves and the build fails.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from hta.normalise import OUTCOMES, POSITIVE_OUTCOMES, TERMINATED_OUTCOME

#: Everything Lap 0 measured against the 2026-08-19 vintage of NICE's file.
#: These are the numbers the definition of done names; the build fails on drift.
EXPECTED = {
    "recommendations": 1531,
    "appraisals": 1181,
    "appraisal_number_max": 1181,
    "terminated_non_submission": 174,
    "only_in_research": 30,
    "positive": 1156,
    "is_cancer": 662,
    "positive_share_all_pct": 75.51,
    "positive_share_excl_non_submission_pct": 85.19,
    "positive_share_nice_denominator_pct": 87.11,
}

#: NICE's own published headline, the thing 87.11% is checked against.
NICE_PUBLISHED_POSITIVE_PCT = 87.0


@dataclass(frozen=True)
class Share:
    label: str
    numerator: int
    denominator: int

    @property
    def pct(self) -> float:
        return round(100 * self.numerator / self.denominator, 2)

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "pct": self.pct,
        }


def positive_shares(spine: pd.DataFrame) -> dict[str, Share]:
    """The three denominators, and the positive share on each.

    ``925`` — what NICE currently displays on its listing — is deliberately not
    here. It is a moving target, never a denominator.
    """
    outcome = spine["outcome"]
    positive = int(outcome.isin(POSITIVE_OUTCOMES).sum())

    n_all = len(spine)
    n_judged = int((outcome != TERMINATED_OUTCOME).sum())
    n_nice = int((~outcome.isin({TERMINATED_OUTCOME, "only_in_research"})).sum())

    return {
        "all": Share("all recommendations", positive, n_all),
        "excl_non_submission": Share(
            "excluding terminated non-submissions", positive, n_judged
        ),
        "nice_denominator": Share(
            "excluding non-submissions and only-in-research (NICE's own denominator)",
            positive,
            n_nice,
        ),
    }


def appraisal_numbers(spine: pd.DataFrame) -> list[int]:
    return sorted({int(ta[2:]) for ta in spine["appraisal_id"].unique()})


def reconcile(spine: pd.DataFrame, *, sources: dict | None = None) -> dict:
    """Every count the dataset publishes, computed from the built table."""
    numbers = appraisal_numbers(spine)
    shares = positive_shares(spine)
    per_appraisal = spine.groupby("appraisal_id").size()

    return {
        "sources": sources or {},
        "counts": {
            "recommendations": len(spine),
            "appraisals": int(spine["appraisal_id"].nunique()),
            "appraisal_number_min": numbers[0],
            "appraisal_number_max": numbers[-1],
            "appraisal_numbers_gapless": numbers == list(range(numbers[0], numbers[-1] + 1)),
            "appraisals_with_one_recommendation": int((per_appraisal == 1).sum()),
            "appraisals_with_multiple_recommendations": int((per_appraisal > 1).sum()),
            "widest_appraisal_recommendations": int(per_appraisal.max()),
            "recommendations_lost_by_counting_appraisals": len(spine)
            - int(spine["appraisal_id"].nunique()),
            "is_cancer": int(spine["is_cancer"].sum()),
            "terminated": int(spine["terminated_flag"].sum()),
        },
        "outcome_counts": {o: int((spine["outcome"] == o).sum()) for o in OUTCOMES},
        "raw_category_counts": (
            spine["recommendation_category_raw"].value_counts().to_dict()
        ),
        "process_type_counts": spine["process_type"].value_counts().to_dict(),
        "review_type_counts": spine["review_type"].value_counts().to_dict(),
        "technology_type_raw_counts": (
            spine["technology_type_raw"].value_counts().to_dict()
        ),
        "year_published_raw_range": [
            spine["year_published_raw"].min(),
            spine["year_published_raw"].max(),
        ],
        "positive_shares": {k: v.as_dict() for k, v in shares.items()},
        "nice_published_positive_pct": NICE_PUBLISHED_POSITIVE_PCT,
    }


def verify(report: dict) -> list[tuple[str, bool, str]]:
    """Check the report against what Lap 0 measured. Returns (name, ok, detail)."""
    c = report["counts"]
    o = report["outcome_counts"]
    s = report["positive_shares"]
    checks = [
        ("recommendations = 1531", c["recommendations"] == EXPECTED["recommendations"],
         f"{c['recommendations']}"),
        ("appraisals = 1181", c["appraisals"] == EXPECTED["appraisals"], f"{c['appraisals']}"),
        ("appraisal numbers gapless 1-1181",
         c["appraisal_numbers_gapless"]
         and c["appraisal_number_min"] == 1
         and c["appraisal_number_max"] == EXPECTED["appraisal_number_max"],
         f"{c['appraisal_number_min']}-{c['appraisal_number_max']}, "
         f"gapless={c['appraisal_numbers_gapless']}"),
        ("terminated non-submissions = 174",
         o["terminated_non_submission"] == EXPECTED["terminated_non_submission"],
         f"{o['terminated_non_submission']}"),
        ("only-in-research = 30", o["only_in_research"] == EXPECTED["only_in_research"],
         f"{o['only_in_research']}"),
        ("positive recommendations = 1156",
         s["all"]["numerator"] == EXPECTED["positive"], f"{s['all']['numerator']}"),
        ("positive share, all 1531 = 75.51%",
         s["all"]["pct"] == EXPECTED["positive_share_all_pct"], f"{s['all']['pct']}%"),
        ("positive share, excl 174 non-submissions = 85.19%",
         s["excl_non_submission"]["pct"]
         == EXPECTED["positive_share_excl_non_submission_pct"],
         f"{s['excl_non_submission']['pct']}%"),
        ("positive share, NICE denominator 1327 = 87.11% (matches NICE's published 87%)",
         s["nice_denominator"]["pct"]
         == EXPECTED["positive_share_nice_denominator_pct"],
         f"{s['nice_denominator']['pct']}%"),
    ]
    if report["sources"].get("cancer"):
        checks.append(
            ("is_cancer = 662", c["is_cancer"] == EXPECTED["is_cancer"], f"{c['is_cancer']}")
        )
    return checks


class ReconciliationError(RuntimeError):
    """The rebuilt table does not match what Lap 0 measured."""


def raise_on_drift(checks: list[tuple[str, bool, str]]) -> None:
    failed = [(n, d) for n, ok, d in checks if not ok]
    if failed:
        lines = "\n".join(f"  FAIL {n} -> got {d}" for n, d in failed)
        raise ReconciliationError(
            "the rebuilt table does not reconcile against Lap 0's measured counts.\n"
            f"{lines}\n"
            "If the outcome mapping changed, the 87% check is the one that tells you "
            "so — it is an external figure, not one of ours."
        )


def to_markdown(report: dict, checks: list[tuple[str, bool, str]]) -> str:
    c, o, s = report["counts"], report["outcome_counts"], report["positive_shares"]
    src = report["sources"]

    lines = [
        "# Reconciliation — NICE technology appraisal recommendations spine",
        "",
        "Written by `python -m hta.cli build`. Every number here is computed from the",
        "built table, not copied from a document.",
        "",
        "## Source",
        "",
        "| File | sha256 | Retrieved |",
        "|---|---|---|",
    ]
    for key in ("recommendations", "cancer"):
        if src.get(key):
            f = src[key]
            lines.append(f"| `{f['file']}` | `{f['sha256'][:16]}…` | {f['retrieved_at']} |")
    lines += [
        "",
        "NICE re-issues this spreadsheet without a version marker and it trails the",
        "website, so every figure below is stamped to that vintage.",
        "",
        "## Counts",
        "",
        "| Quantity | n |",
        "|---|---|",
        f"| Recommendations (rows) | **{c['recommendations']}** |",
        f"| Appraisals (parent key) | **{c['appraisals']}** |",
        f"| Appraisal numbers | TA{c['appraisal_number_min']}–TA{c['appraisal_number_max']}, "
        f"gapless: {c['appraisal_numbers_gapless']} |",
        f"| Appraisals with one recommendation | {c['appraisals_with_one_recommendation']} |",
        f"| Appraisals with more than one | {c['appraisals_with_multiple_recommendations']} "
        f"(widest: {c['widest_appraisal_recommendations']}) |",
        f"| **Recommendations lost by counting appraisals** | "
        f"**{c['recommendations_lost_by_counting_appraisals']}** |",
        f"| Cancer recommendations (`is_cancer`) | {c['is_cancer']} |",
        f"| Terminated non-submissions | {c['terminated']} |",
        f"| Fiscal years covered | {report['year_published_raw_range'][0]}–"
        f"{report['year_published_raw_range'][1]} |",
        "",
        "## Outcomes",
        "",
        "| Outcome | n |",
        "|---|---|",
    ]
    lines += [f"| `{k}` | {v} |" for k, v in o.items()]
    lines += [
        "",
        "## The 87% check — external validity of the outcome mapping",
        "",
        "NICE publishes: *\"87% of our recommendations have been positive (recommended,",
        "optimised, or recommended for the Cancer Drugs Fund)\"*. Reproducing it fixes the",
        "denominator NICE does not state.",
        "",
        "| Denominator | Positive | n | Share |",
        "|---|---|---|---|",
    ]
    for v in s.values():
        lines.append(
            f"| {v['label']} | {v['numerator']} | {v['denominator']} | **{v['pct']}%** |"
        )
    lines += [
        "",
        f"The third row is the one to compare with NICE's published "
        f"{report['nice_published_positive_pct']}%. **If it drifts, the mapping broke.**",
        "",
        "## Checks",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    lines += [f"| {n} | {'PASS' if ok else 'FAIL'} — {d} |" for n, ok, d in checks]
    lines += [
        "",
        "## Known trap, recorded not fixed",
        "",
        "`technology_type_raw` carries a case variant of its own — *Medical device* (46) and",
        "*Medical Device* (1) are the same category. It ships verbatim because Schema v1",
        "specifies no normalised sibling for it; anyone stratifying on it should fold case",
        "first. Flagged here rather than silently corrected.",
        "",
        "---",
        "",
        "Derived from NICE published data. NICE does not endorse this work. See `LICENSING.md`.",
        "",
    ]
    return "\n".join(lines)


def write_reports(report: dict, checks: list[tuple[str, bool, str]], outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    payload = dict(report)
    payload["checks"] = [{"check": n, "pass": ok, "value": d} for n, ok, d in checks]

    js = outdir / "reconciliation.json"
    md = outdir / "reconciliation.md"
    js.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    md.write_text(to_markdown(report, checks), encoding="utf-8")
    return [js, md]
