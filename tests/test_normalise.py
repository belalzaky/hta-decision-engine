"""Unit tests for the mappings — every raw value NICE actually publishes."""
import json
from pathlib import Path

import pytest

from hta import normalise

MARGINALS = json.loads(
    (Path(__file__).parent / "fixtures" / "nice_marginals.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Recommended", "recommended"),
        ("recommended", "recommended"),  # case variant
        ("Optimised", "optimised"),
        ("Recommended (CDF)", "cdf_recommended"),
        ("Optimised (CDF)", "cdf_optimised"),
        ("Recommended (IMF)", "imf_recommended"),
        ("Optimised (IMF)", "imf_optimised"),
        ("Only in research", "only_in_research"),
        ("Only in Research", "only_in_research"),  # case variant
        ("Not recommended", "not_recommended"),
        ("Not Recommended", "not_recommended"),  # case variant
        ("Terminated Appraisal - non submission", "terminated_non_submission"),
    ],
)
def test_every_published_category_maps(raw, expected):
    assert normalise.map_outcome(raw) == expected


def test_mapping_covers_exactly_the_published_categories():
    """No stale keys, no missing ones — checked against the measured marginals."""
    assert set(normalise.OUTCOME_MAP) == set(MARGINALS["categorisation"])
    assert set(normalise.OUTCOME_MAP.values()) == set(normalise.OUTCOMES)
    assert len(normalise.OUTCOME_MAP) == 12 and len(normalise.OUTCOMES) == 9


def test_unknown_category_raises_rather_than_nulling():
    with pytest.raises(ValueError, match="unmapped"):
        normalise.map_outcome("Recommended (some new fund)")


def test_cdf_and_imf_count_as_positive_but_only_in_research_does_not():
    assert "cdf_recommended" in normalise.POSITIVE_OUTCOMES
    assert "imf_optimised" in normalise.POSITIVE_OUTCOMES
    assert "only_in_research" not in normalise.POSITIVE_OUTCOMES
    assert "terminated_non_submission" not in normalise.POSITIVE_OUTCOMES
    assert len(normalise.POSITIVE_OUTCOMES) == 6


@pytest.mark.parametrize(
    "raw,process,review",
    [
        ("STA", "STA", "original"),
        ("MTA", "MTA", "original"),
        ("MTA (review)", "MTA", "review"),
        ("STA (review)", "STA", "review"),
        ("STA (rapid review)", "STA", "rapid review"),
        ("MTA (part-review)", "MTA", "part-review"),
    ],
)
def test_process_column_splits_into_its_two_facts(raw, process, review):
    assert normalise.split_process(raw) == (process, review)


def test_process_split_covers_every_published_value():
    assert set(MARGINALS["sta_mta_process"]) == {
        "STA", "MTA", "MTA (review)", "STA (review)", "STA (rapid review)", "MTA (part-review)"
    }
    for value in MARGINALS["sta_mta_process"]:
        normalise.split_process(value)


def test_process_column_carries_no_route_value():
    """`route` is deferred to Lap 3 precisely because it is not in this column."""
    for value in MARGINALS["sta_mta_process"]:
        lowered = value.lower()
        assert "cost" not in lowered
        assert "highly specialised" not in lowered
        assert "fast track" not in lowered


def test_unknown_process_raises():
    with pytest.raises(ValueError, match="unmapped"):
        normalise.split_process("HST")


@pytest.mark.parametrize(
    "padded,url",
    [
        ("TA001", "https://www.nice.org.uk/guidance/ta1"),
        ("TA081", "https://www.nice.org.uk/guidance/ta81"),
        ("TA1121", "https://www.nice.org.uk/guidance/ta1121"),
    ],
)
def test_url_is_built_from_the_depadded_id(padded, url):
    """Lap 0 measured /guidance/ta081 redirecting to /guidance/ta81."""
    assert normalise.appraisal_url(padded) == url


def test_recommendation_id_keeps_the_padded_published_id():
    assert normalise.recommendation_id("TA1121", 1) == "TA1121-01"
    assert normalise.recommendation_id("TA081", 16) == "TA081-16"


def test_recommendation_sequence_is_one_based():
    with pytest.raises(ValueError):
        normalise.recommendation_id("TA001", 0)
