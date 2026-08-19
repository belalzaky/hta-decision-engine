"""Inventory parsing, against synthetic pages built to NICE's template shape.

No NICE HTML is committed (LICENSING.md §7), so the fixtures here are written by
hand to the *structure* Lap 0 observed — the `page-header__metadata` block, a
`<time datetime=...>` element, chapter links under `/chapter/`, and the
supersession sentence. The real pages are parsed by `test_real_cache.py`, which
skips when the cache is absent.
"""
import pytest

from hta import inventory

METADATA = """
<ul class="page-header__metadata" aria-label="Product metadata">
  <li>Technology appraisal guidance</li>
  <li><span class="visually-hidden">Reference number: </span>{ref}</li>
  <li>Published:&nbsp;<time class="show" datetime="{iso}">{human}</time></li>
</ul>
"""


def page(ref="TA1121", iso="2026-01-14", human="14 January 2026", chapters=(), extra=""):
    links = "".join(
        f'<a href="/guidance/{ref.lower()}/chapter/{slug}">{title}</a>'
        for slug, title in chapters
    )
    return (
        f"<html><head><title>Overview | Something | Guidance | NICE</title></head>"
        f"<body>{METADATA.format(ref=ref, iso=iso, human=human)}{links}{extra}</body></html>"
    )


def test_reference_number_and_publication_date_are_read():
    p = inventory.parse_overview(page())
    assert p["reference_number"] == "TA1121"
    assert p["published_date"] == "2026-01-14"
    assert p["product_type"] == "Technology appraisal guidance"


def test_chapters_are_listed_with_titles_and_slugs():
    p = inventory.parse_overview(page(chapters=[
        ("1-Recommendations", "1 Recommendations"),
        ("3-Implementation", "3 Implementation"),
    ]))
    assert p["chapter_count"] == 2
    assert [c["title"] for c in p["chapters"]] == ["1 Recommendations", "3 Implementation"]
    assert p["chapters"][0]["slug"] == "1-Recommendations"


def test_a_chapter_linked_twice_is_counted_once():
    """The template links the first chapter again as 'Next page'."""
    repeated = [("1-Recommendations", "1 Recommendations"),
                ("1-Recommendations", "Next page 1 Recommendations")]
    assert inventory.parse_overview(page(chapters=repeated))["chapter_count"] == 1


def test_a_page_with_no_chapters_reports_zero_not_an_error():
    assert inventory.parse_overview(page())["chapter_count"] == 0


def test_supersession_is_detected_and_names_the_superseding_guidance():
    banner = ('<p>This guidance has been updated and replaced by '
              '<a href="http://www.nice.org.uk/guidance/ng101">NICE guideline NG101</a>.</p>')
    p = inventory.parse_overview(page(extra=banner))
    assert p["superseded"] is True
    assert p["superseding"][0]["reference"] == "NG101"
    assert p["superseding"][0]["url"].endswith("/guidance/ng101")


def test_a_live_page_is_not_flagged_as_superseded():
    p = inventory.parse_overview(page(chapters=[("1-Recommendations", "1 Recommendations")]))
    assert p["superseded"] is False and p["superseding"] == []


@pytest.mark.parametrize("phrase,marker", [
    ("This is a cost-comparison appraisal", "cost_comparison"),
    ("highly specialised technology", "highly_specialised"),
    ("a single technology appraisal", "single_technology"),
])
def test_route_markers_are_found_when_present(phrase, marker):
    assert marker in inventory.parse_overview(page(extra=f"<p>{phrase}</p>"))["route_markers"]


def test_no_route_markers_on_a_plain_page():
    assert inventory.parse_overview(page())["route_markers"] == []


def test_entities_and_whitespace_are_normalised():
    p = inventory.parse_overview(page(chapters=[("2-X", "2 Information&nbsp;about\n  X")]))
    assert p["chapters"][0]["title"] == "2 Information about X"


# --- the report ------------------------------------------------------------

class FakeRecord:
    def __init__(self, path=None, ok=True, status=200, error=None, redirected=False):
        self.path, self.http_status, self.error = path, status, error
        self.url_requested = "https://www.nice.org.uk/guidance/ta1"
        self.url_final = self.url_requested
        self.redirected, self.retrieved_at = redirected, "2026-08-20T00:00:00+00:00"
        self._ok = ok

    @property
    def ok(self):
        return self._ok


def test_report_counts_chapters_and_sizes_lap2b(tmp_path):
    (tmp_path / "ta1.html").write_text(page(ref="TA1", chapters=[
        ("1-Recommendations", "1 Recommendations"), ("2-Evidence", "2 Evidence")]))
    (tmp_path / "ta2.html").write_text(page(ref="TA2", chapters=[
        ("1-Recommendations", "1 Recommendations")]))

    manifest = {"TA001": FakeRecord(str(tmp_path / "ta1.html")),
                "TA002": FakeRecord(str(tmp_path / "ta2.html"))}
    targets = [("TA001", "https://www.nice.org.uk/guidance/ta1"),
               ("TA002", "https://www.nice.org.uk/guidance/ta2")]

    report = inventory.build_report(targets, manifest, tmp_path)
    assert report["totals"]["cached_and_parsed"] == 2
    assert report["chapters"]["total"] == 3
    assert report["lap2b"]["chapter_requests_if_all"] == 3
    assert dict(report["chapters"]["titles_top"])["1 Recommendations"] == 2


def test_failures_and_gaps_are_itemised_never_summarised_away(tmp_path):
    manifest = {
        "TA001": FakeRecord(ok=False, status=404, error="HTTP 404 Not Found"),
        "TA002": FakeRecord(str(tmp_path / "gone.html")),      # manifest points at nothing
    }
    targets = [("TA001", "u1"), ("TA002", "u2"), ("TA003", "u3")]  # TA003 never attempted

    report = inventory.build_report(targets, manifest, tmp_path)
    assert report["totals"]["failed"] == 1
    assert report["totals"]["missing"] == 2
    assert report["failures"]["failed"][0]["http_status"] == 404
    reasons = {m["reason"] for m in report["failures"]["missing"]}
    assert "never attempted" in reasons
    assert any("absent" in r for r in reasons)


def test_markdown_report_answers_all_five_questions(tmp_path):
    (tmp_path / "ta1.html").write_text(page(ref="TA1", chapters=[("1-R", "1 Recommendations")]))
    manifest = {"TA001": FakeRecord(str(tmp_path / "ta1.html"))}
    report = inventory.build_report([("TA001", "u")], manifest, tmp_path)
    md = inventory.to_markdown(report)
    for heading in ["chapter inventory", "route", "publication date",
                    "Supersession", "failed"]:
        assert heading.lower() in md.lower()
