"""The built table: shape, keys, and the verbatim-beside-normalised rule."""
import pandas as pd
import pytest

from hta.spine import COLUMNS, build_spine


@pytest.fixture(scope="module")
def spine(surrogate_raw, surrogate_cancer, surrogate_source):
    return build_spine(surrogate_raw, source=surrogate_source, cancer=surrogate_cancer)


def test_one_row_per_recommendation_not_per_appraisal(spine, surrogate_raw):
    assert len(spine) == len(surrogate_raw) == 1531
    assert spine["appraisal_id"].nunique() == 1181
    assert len(spine) - spine["appraisal_id"].nunique() == 350


def test_columns_are_exactly_schema_v1_in_order(spine):
    assert list(spine.columns) == COLUMNS


def test_route_and_date_published_are_absent(spine):
    """Deferred to Lap 3. Inventing them is worse than lacking them."""
    assert "route" not in spine.columns
    assert "date_published" not in spine.columns


def test_keys_are_unique_and_stable(spine):
    assert spine["recommendation_id"].is_unique
    assert spine["recommendation_seq"].is_unique
    assert sorted(spine["recommendation_seq"]) == list(range(1, 1532))
    assert spine["recommendation_id"].str.match(r"^TA\d{3,4}-\d{2}$").all()


def test_a_rebuild_is_byte_identical(surrogate_raw, surrogate_cancer, surrogate_source, spine):
    again = build_spine(surrogate_raw, source=surrogate_source, cancer=surrogate_cancer)
    pd.testing.assert_frame_equal(spine, again)


def test_verbatim_columns_are_untouched(spine, surrogate_raw):
    """A normalised field never replaces the verbatim one — a licence condition,
    not only data hygiene: the NICE OCL forbids amending published wording."""
    joined = spine.set_index("recommendation_seq").sort_index()
    original = surrogate_raw.set_index("Rec no.").sort_index()
    for raw_col, spine_col in [
        ("Technology", "technology_raw"),
        ("Technology type", "technology_type_raw"),
        ("Indication", "condition_raw"),
        ("STA/MTA process", "sta_mta_process_raw"),
        ("Categorisation (for specific recommendation)", "recommendation_category_raw"),
        ("Comment", "nice_comments_raw"),
        ("Year of Publication", "year_published_raw"),
    ]:
        assert (joined[spine_col] == original[raw_col]).all(), spine_col


def test_every_normalised_field_sits_beside_its_source(spine):
    for raw_col, derived in [
        ("sta_mta_process_raw", ["process_type", "review_type"]),
        ("recommendation_category_raw", ["outcome", "terminated_flag"]),
    ]:
        assert raw_col in spine.columns
        for d in derived:
            assert d in spine.columns


def test_year_stays_a_fiscal_year_string(spine):
    """`1999/00` is a fiscal year, not a date. Do not coerce it into one."""
    from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype

    assert spine["year_published_raw"].str.match(r"^\d{4}/\d{2}$").all()
    assert not is_datetime64_any_dtype(spine["year_published_raw"])
    assert not is_numeric_dtype(spine["year_published_raw"])


def test_appraisal_url_is_depadded(spine):
    row = spine[spine["appraisal_id"] == "TA081"].iloc[0]
    assert row["appraisal_url"] == "https://www.nice.org.uk/guidance/ta81"
    assert not spine["appraisal_url"].str.contains("/ta0").any()


def test_flags_are_boolean_and_never_null(spine):
    for col in ("terminated_flag", "is_cancer"):
        assert spine[col].dtype == bool
        assert not spine[col].isna().any()


def test_terminated_flag_agrees_with_the_outcome(spine):
    assert (
        spine["terminated_flag"] == (spine["outcome"] == "terminated_non_submission")
    ).all()
    assert spine["terminated_flag"].sum() == 174


def test_is_cancer_is_the_companion_file_subset(spine, surrogate_cancer):
    assert spine["is_cancer"].sum() == len(surrogate_cancer) == 662
    flagged = set(spine.loc[spine["is_cancer"], "recommendation_seq"])
    assert flagged == set(surrogate_cancer["Rec no."].astype(int))


def test_is_cancer_defaults_to_false_without_the_companion(surrogate_raw, surrogate_source):
    built = build_spine(surrogate_raw, source=surrogate_source, cancer=None)
    assert built["is_cancer"].dtype == bool
    assert not built["is_cancer"].any()


def test_provenance_is_on_every_row(spine, surrogate_source):
    assert (spine["source_file"] == surrogate_source.name).all()
    assert (spine["source_sha256"] == surrogate_source.sha256).all()
    assert (spine["retrieved_at"] == surrogate_source.retrieved_at).all()


def test_a_new_nice_category_breaks_the_build(surrogate_raw, surrogate_source):
    poisoned = surrogate_raw.copy()
    poisoned.loc[0, "Categorisation (for specific recommendation)"] = "Recommended (new fund)"
    with pytest.raises(ValueError, match="Recommended \\(new fund\\)"):
        build_spine(poisoned, source=surrogate_source)
