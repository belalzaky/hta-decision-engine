"""Counts, denominators, and the 87% external validity check.

The 87% figure is NICE's, not ours. It is the only number in this project that
can be checked against an authority outside the pipeline, so it is the check
that tells us the outcome normalisation is right rather than merely consistent.
"""
import pytest

from hta import reconcile
from hta.spine import build_spine


@pytest.fixture(scope="module")
def report(surrogate_raw, surrogate_cancer, surrogate_source):
    spine = build_spine(surrogate_raw, source=surrogate_source, cancer=surrogate_cancer)
    return reconcile.reconcile(spine, sources={"recommendations": {}, "cancer": {}})


def test_counts_reconcile_to_1531_recommendations_over_1181_appraisals(report):
    c = report["counts"]
    assert c["recommendations"] == 1531
    assert c["appraisals"] == 1181
    assert c["recommendations_lost_by_counting_appraisals"] == 350


def test_appraisal_numbers_are_gapless_1_to_1181(report):
    """A complete census, not a sample."""
    c = report["counts"]
    assert (c["appraisal_number_min"], c["appraisal_number_max"]) == (1, 1181)
    assert c["appraisal_numbers_gapless"] is True


def test_outcome_counts_match_the_published_marginals(report, marginals):
    o = report["outcome_counts"]
    assert sum(o.values()) == 1531
    assert o["terminated_non_submission"] == 174
    assert o["only_in_research"] == 22 + 8       # two case variants folded
    assert o["recommended"] == 651 + 2
    assert o["not_recommended"] == 137 + 34
    assert o["imf_recommended"] + o["imf_optimised"] == 3
    assert report["raw_category_counts"] == marginals["categorisation"]


def test_the_three_denominators(report):
    s = report["positive_shares"]
    assert s["all"]["denominator"] == 1531
    assert s["excl_non_submission"]["denominator"] == 1531 - 174 == 1357
    assert s["nice_denominator"]["denominator"] == 1531 - 174 - 30 == 1327


def test_the_87_percent_check(report):
    """75.51% / 85.19% / 87.11%, and the third matches NICE's published 87%."""
    s = report["positive_shares"]

    assert s["all"]["numerator"] == 1156
    assert (s["all"]["numerator"], s["all"]["denominator"]) == (1156, 1531)
    assert s["all"]["pct"] == 75.51

    assert (s["excl_non_submission"]["numerator"],
            s["excl_non_submission"]["denominator"]) == (1156, 1357)
    assert s["excl_non_submission"]["pct"] == 85.19

    assert (s["nice_denominator"]["numerator"],
            s["nice_denominator"]["denominator"]) == (1156, 1327)
    assert s["nice_denominator"]["pct"] == 87.11

    assert round(s["nice_denominator"]["pct"]) == reconcile.NICE_PUBLISHED_POSITIVE_PCT


def test_positives_and_negatives_exhaust_the_nice_denominator(report):
    """1156 positive + 171 not-recommended = 1327. Nothing falls through."""
    o = report["outcome_counts"]
    positive = sum(o[k] for k in reconcile.POSITIVE_OUTCOMES)
    assert positive + o["not_recommended"] == 1327


def test_all_checks_pass_on_the_surrogate(report):
    checks = reconcile.verify(report)
    failed = [(n, d) for n, ok, d in checks if not ok]
    assert failed == []
    reconcile.raise_on_drift(checks)


def test_a_broken_outcome_mapping_moves_the_87_percent(surrogate_raw, surrogate_source):
    """The point of the check: mis-map one category and 87.11% no longer holds.

    Here only-in-research is wrongly treated as positive — the single most
    plausible mapping error, and exactly the one NICE's own wording invites.
    """
    from hta import normalise

    spine = build_spine(surrogate_raw, source=surrogate_source)
    spine = spine.copy()
    spine.loc[spine["outcome"] == "only_in_research", "outcome"] = "recommended"

    shares = reconcile.positive_shares(spine)
    assert shares["nice_denominator"].pct != 87.11

    report = reconcile.reconcile(spine)
    with pytest.raises(reconcile.ReconciliationError, match="87"):
        reconcile.raise_on_drift(reconcile.verify(report))
    assert normalise.POSITIVE_OUTCOMES  # mapping itself untouched


def test_markdown_report_states_the_numbers(report):
    md = reconcile.to_markdown(report, reconcile.verify(report))
    for expected in ("1531", "1181", "**87.11%**", "**75.51%**", "**85.19%**", "350"):
        assert expected in md
