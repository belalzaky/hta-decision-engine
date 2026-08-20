"""Lap 2a's definition of done, asserted against the real cache.

Skipped in CI, where `data/raw/` is absent by design. These are the checks that
say the crawl actually covered the spine: **no silent gaps**, every cached file
present and matching its recorded sha256, and every page parseable.
"""
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from hta import crawl, inventory

REPO_ROOT = Path(__file__).resolve().parents[1]
SPINE = REPO_ROOT / "data" / "processed" / "nice_ta_recommendations_spine.parquet"
CACHE = REPO_ROOT / "data" / "raw" / "guidance"
MANIFEST = CACHE / "manifest.jsonl"

pytestmark = pytest.mark.skipif(
    not MANIFEST.exists() or not SPINE.exists(),
    reason="Lap 2a cache absent (never redistributed — see LICENSING.md)",
)


@pytest.fixture(scope="module")
def targets():
    spine = pd.read_parquet(SPINE)
    pairs = spine[["appraisal_id", "appraisal_url"]].drop_duplicates()
    return list(zip(pairs["appraisal_id"], pairs["appraisal_url"]))


@pytest.fixture(scope="module")
def manifest():
    return crawl.read_manifest(MANIFEST)


def test_every_appraisal_in_the_spine_is_accounted_for(targets, manifest):
    """No silent gaps: cached, or recorded as failed with a reason."""
    unaccounted = [a for a, _ in targets if a not in manifest]
    assert unaccounted == [], f"{len(unaccounted)} appraisals never attempted"
    assert len(targets) == 1181


def test_no_appraisal_was_recorded_without_a_reason(manifest):
    for appraisal_id, record in manifest.items():
        assert record.ok or record.error, f"{appraisal_id} failed with no reason"


def test_every_cached_file_exists_and_matches_its_recorded_sha(manifest):
    for appraisal_id, record in manifest.items():
        if not record.ok:
            continue
        path = REPO_ROOT / record.path
        assert path.exists(), f"{appraisal_id}: {path} missing"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record.sha256


def test_no_cached_page_is_a_shell(manifest):
    """The rule the crawl enforces at fetch time, re-checked on disk."""
    for record in manifest.values():
        if record.ok:
            assert record.bytes >= crawl.MIN_BODY_BYTES


def test_every_cached_page_parses_and_carries_its_own_reference_number(manifest):
    mismatches = []
    for appraisal_id, record in manifest.items():
        if not record.ok:
            continue
        parsed = inventory.parse_overview(
            (REPO_ROOT / record.path).read_text(encoding="utf-8", errors="replace")
        )
        expected = f"TA{int(appraisal_id[2:])}"
        if parsed["reference_number"] != expected:
            mismatches.append((appraisal_id, parsed["reference_number"]))
    assert mismatches == [], f"{len(mismatches)} pages report a different TA: {mismatches[:5]}"


def test_the_manifest_has_one_row_per_appraisal_and_no_duplicates():
    rows = [json.loads(l) for l in MANIFEST.read_text().splitlines() if l.strip()]
    latest = {r["appraisal_id"] for r in rows}
    assert len(latest) <= 1181
    # a retried appraisal may legitimately appear twice; the reader keeps the last
    assert len(rows) >= len(latest)


def test_rerunning_the_crawl_would_make_no_requests(targets, manifest):
    """`crawl.outstanding` is what makes the run resume-safe and idempotent."""
    assert crawl.outstanding(list(targets), manifest) == []


# --- Lap 2b: the substantive chapter cache --------------------------------

CHAPTERS = CACHE / "chapters"
CHAPTER_MANIFEST = CHAPTERS / "manifest.jsonl"

needs_chapters = pytest.mark.skipif(
    not CHAPTER_MANIFEST.exists(), reason="Lap 2b chapter cache absent"
)


@pytest.fixture(scope="module")
def chapter_targets(targets, manifest):
    return inventory.chapter_targets(targets, manifest)


@pytest.fixture(scope="module")
def chapter_manifest():
    return crawl.read_manifest(CHAPTER_MANIFEST)


@needs_chapters
def test_the_narrow_scope_is_what_was_agreed(chapter_targets):
    """Recommendations and reasoning; not implementation, membership or sources."""
    slugs = {t[0].split("/", 1)[1] for t in chapter_targets}
    stripped = {s.split("-", 1)[1] if s[0].isdigit() else s for s in slugs}
    assert stripped <= set(inventory.SUBSTANTIVE_SLUGS)
    assert "Implementation" not in stripped
    assert not any("committee-members" in s.lower() for s in stripped)
    assert len(chapter_targets) == 1635


@needs_chapters
def test_every_targeted_chapter_is_cached_with_no_silent_gaps(
    chapter_targets, chapter_manifest
):
    unaccounted = [k for k, _ in chapter_targets if k not in chapter_manifest]
    assert unaccounted == []
    failed = [k for k, _ in chapter_targets if not chapter_manifest[k].ok]
    assert failed == [], f"{len(failed)} chapters still failed: {failed[:5]}"


@needs_chapters
def test_every_cached_chapter_matches_its_recorded_sha(chapter_manifest):
    for key, record in chapter_manifest.items():
        if not record.ok:
            continue
        path = REPO_ROOT / record.path
        assert path.exists(), f"{key}: {path} missing"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record.sha256


@needs_chapters
def test_a_chapter_belongs_to_the_appraisal_its_key_names(chapter_manifest):
    """The cache must not silently file TA81's chapter under TA810."""
    wrong = []
    for key, record in chapter_manifest.items():
        if not record.ok:
            continue
        expected = f"TA{int(record.appraisal_id[2:])}"
        parsed = inventory.parse_overview(
            (REPO_ROOT / record.path).read_text(encoding="utf-8", errors="replace")
        )
        if parsed["reference_number"] != expected:
            wrong.append((key, parsed["reference_number"]))
    assert wrong == [], f"{len(wrong)} mis-filed: {wrong[:5]}"


@needs_chapters
def test_rerunning_the_chapter_crawl_would_make_no_requests(
    chapter_targets, chapter_manifest
):
    assert crawl.outstanding(list(chapter_targets), chapter_manifest) == []


@needs_chapters
def test_nothing_from_lap_2_leaked_into_the_spine():
    """Lap 2 caches and inventories. Lap 3 extracts. The schema must not have moved."""
    from hta.spine import COLUMNS

    spine = pd.read_parquet(SPINE)
    assert list(spine.columns) == COLUMNS
    assert "route" not in spine.columns
    assert "date_published" not in spine.columns
    assert not any(c.startswith("chapter") for c in spine.columns)
    assert len(spine) == 1531
