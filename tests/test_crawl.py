"""The crawl rules, tested without touching the network.

Every test here drives `crawl` through a fake opener. The rules are the point of
the module — politeness, resume-safety, and failing loudly — so they are what is
asserted, not the happy path alone.
"""
import io
import json
import urllib.error
from pathlib import Path

import pytest

from hta import crawl

ROBOTS_LAP0 = """User-agent: *
Crawl-delay: 1
Disallow: /cks-is-only-available-in-the-uk
Disallow: /cks-end-user-licence-agreement
Allow: /
"""

PAGE = b"<html><body>" + b"x" * 2000 + b"</body></html>"


class FakeResponse(io.BytesIO):
    def __init__(self, body, status=200, url="https://www.nice.org.uk/guidance/ta1"):
        super().__init__(body)
        self.status = status
        self._url = url
        self.headers = {}

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def make_opener(pages: dict, robots: str = ROBOTS_LAP0, calls: list | None = None):
    def opener(request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else request
        if calls is not None:
            calls.append(url)
        if url == crawl.ROBOTS_URL:
            return FakeResponse(robots.encode(), url=url)
        if url not in pages:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        body, status, final = pages[url]
        if status != 200:
            raise urllib.error.HTTPError(final, status, "Gone", {}, None)
        return FakeResponse(body, status, final)

    return opener


def targets(n):
    return [(f"TA{i:03d}", f"https://www.nice.org.uk/guidance/ta{i}") for i in range(1, n + 1)]


def pages_for(n, body=PAGE):
    return {
        f"https://www.nice.org.uk/guidance/ta{i}": (body, 200,
                                                    f"https://www.nice.org.uk/guidance/ta{i}")
        for i in range(1, n + 1)
    }


# --- robots.txt ------------------------------------------------------------

def test_lap0_robots_still_passes():
    rules = crawl.check_robots(ROBOTS_LAP0)
    assert rules["crawl_delay"] == 1.0


def test_the_delay_is_double_what_robots_asks():
    assert crawl.DELAY_SECONDS == 2 * crawl.LAP0_CRAWL_DELAY


def test_a_tightened_crawl_delay_aborts_the_run():
    with pytest.raises(crawl.CrawlAbort, match="tightened Crawl-delay"):
        crawl.check_robots(ROBOTS_LAP0.replace("Crawl-delay: 1", "Crawl-delay: 10"))


def test_disallowing_guidance_aborts_the_run():
    with pytest.raises(crawl.CrawlAbort, match="disallows /guidance/"):
        crawl.check_robots(ROBOTS_LAP0 + "Disallow: /guidance/\n")


def test_a_blanket_disallow_aborts_the_run():
    with pytest.raises(crawl.CrawlAbort, match="disallows"):
        crawl.check_robots("User-agent: *\nDisallow: /\n")


def test_any_new_rule_stops_us_even_if_it_looks_harmless():
    with pytest.raises(crawl.CrawlAbort, match="new Disallow rules"):
        crawl.check_robots(ROBOTS_LAP0 + "Disallow: /something-else\n")


def test_rules_for_other_agents_are_ignored():
    text = ROBOTS_LAP0 + "\nUser-agent: GPTBot\nDisallow: /\nCrawl-delay: 60\n"
    assert crawl.check_robots(text)["crawl_delay"] == 1.0


# --- identity and cache layout --------------------------------------------

def test_user_agent_identifies_the_project_and_a_contact_route():
    assert "hta-decision-engine" in crawl.USER_AGENT
    assert "+https://github.com/" in crawl.USER_AGENT


def test_cache_path_is_the_depadded_slug(tmp_path):
    assert crawl.cache_path(tmp_path, "https://www.nice.org.uk/guidance/ta81").name == "ta81.html"


# --- the rules that matter -------------------------------------------------

def test_an_empty_200_stops_the_run_and_writes_nothing(tmp_path):
    opener = make_opener({"https://www.nice.org.uk/guidance/ta1": (b"", 200,
                                                                  "https://www.nice.org.uk/guidance/ta1")})
    with pytest.raises(crawl.CrawlAbort, match="empty 200 is a failure"):
        crawl.crawl(targets(1), tmp_path, tmp_path / "m.jsonl",
                    opener=opener, sleep=lambda s: None, log=lambda m: None)
    assert not (tmp_path / "ta1.html").exists()


def test_a_short_body_counts_as_empty(tmp_path):
    opener = make_opener({"https://www.nice.org.uk/guidance/ta1": (b"<html></html>", 200,
                                                                  "https://www.nice.org.uk/guidance/ta1")})
    with pytest.raises(crawl.CrawlAbort, match="13-byte body"):
        crawl.crawl(targets(1), tmp_path, tmp_path / "m.jsonl",
                    opener=opener, sleep=lambda s: None, log=lambda m: None)


def test_requests_are_sequential_and_spaced(tmp_path):
    slept = []
    summary = crawl.crawl(targets(4), tmp_path, tmp_path / "m.jsonl",
                          opener=make_opener(pages_for(4)),
                          sleep=slept.append, log=lambda m: None)
    assert summary["ok"] == 4
    # one gap between each pair of requests, none before the first
    assert slept == [crawl.DELAY_SECONDS] * 3


def test_the_run_is_resume_safe_and_never_refetches(tmp_path):
    calls = []
    crawl.crawl(targets(3), tmp_path, tmp_path / "m.jsonl",
                opener=make_opener(pages_for(3), calls=calls),
                sleep=lambda s: None, log=lambda m: None, limit=2)
    assert len([c for c in calls if "robots" not in c]) == 2

    calls.clear()
    summary = crawl.crawl(targets(3), tmp_path, tmp_path / "m.jsonl",
                          opener=make_opener(pages_for(3), calls=calls),
                          sleep=lambda s: None, log=lambda m: None)
    assert summary["requested"] == 1 and summary["skipped"] == 2
    assert [c for c in calls if "guidance" in c] == ["https://www.nice.org.uk/guidance/ta3"]


def test_a_full_cache_makes_zero_network_requests_including_robots(tmp_path):
    calls = []
    crawl.crawl(targets(2), tmp_path, tmp_path / "m.jsonl",
                opener=make_opener(pages_for(2), calls=calls),
                sleep=lambda s: None, log=lambda m: None)
    calls.clear()

    def explode(*a, **k):
        raise AssertionError("a full cache must not open a connection")

    summary = crawl.crawl(targets(2), tmp_path, tmp_path / "m.jsonl",
                          opener=explode, sleep=lambda s: None, log=lambda m: None)
    assert summary == {"requested": 0, "ok": 0, "failed": 0, "skipped": 2,
                       "robots_checked": False}


def test_a_limited_run_does_not_call_the_rest_cached(tmp_path):
    """`--limit` defers targets; reporting them as cached would be a lie."""
    summary = crawl.crawl(targets(5), tmp_path, tmp_path / "m.jsonl", limit=2,
                          opener=make_opener(pages_for(5)),
                          sleep=lambda s: None, log=lambda m: None)
    assert summary["requested"] == 2
    assert summary["skipped"] == 0
    assert summary["deferred_by_limit"] == 3


def test_a_deleted_cache_file_is_refetched_even_though_the_manifest_has_it(tmp_path):
    crawl.crawl(targets(1), tmp_path, tmp_path / "m.jsonl",
                opener=make_opener(pages_for(1)), sleep=lambda s: None, log=lambda m: None)
    (tmp_path / "ta1.html").unlink()
    summary = crawl.crawl(targets(1), tmp_path, tmp_path / "m.jsonl",
                          opener=make_opener(pages_for(1)),
                          sleep=lambda s: None, log=lambda m: None)
    assert summary["requested"] == 1


def test_failures_are_recorded_and_the_run_continues(tmp_path):
    pages = pages_for(3)
    del pages["https://www.nice.org.uk/guidance/ta2"]       # 404
    summary = crawl.crawl(targets(3), tmp_path, tmp_path / "m.jsonl",
                          opener=make_opener(pages), sleep=lambda s: None, log=lambda m: None)
    assert (summary["ok"], summary["failed"]) == (2, 1)

    manifest = crawl.read_manifest(tmp_path / "m.jsonl")
    assert manifest["TA002"].http_status == 404
    assert "404" in manifest["TA002"].error
    assert manifest["TA002"].path is None                    # no shell cached


def test_a_recorded_failure_is_retried_on_the_next_run(tmp_path):
    pages = pages_for(2)
    del pages["https://www.nice.org.uk/guidance/ta2"]
    crawl.crawl(targets(2), tmp_path, tmp_path / "m.jsonl",
                opener=make_opener(pages), sleep=lambda s: None, log=lambda m: None)
    summary = crawl.crawl(targets(2), tmp_path, tmp_path / "m.jsonl",
                          opener=make_opener(pages_for(2)),
                          sleep=lambda s: None, log=lambda m: None)
    assert summary["requested"] == 1 and summary["ok"] == 1


def test_a_wall_of_failures_stops_the_run(tmp_path):
    """Do not keep hammering a site that has started refusing us."""
    with pytest.raises(crawl.CrawlAbort, match="consecutive failures"):
        crawl.crawl(targets(30), tmp_path, tmp_path / "m.jsonl",
                    opener=make_opener({}), sleep=lambda s: None, log=lambda m: None)
    manifest = crawl.read_manifest(tmp_path / "m.jsonl")
    assert len(manifest) == crawl.MAX_CONSECUTIVE_FAILURES


def test_a_redirect_is_recorded_not_silently_followed(tmp_path):
    pages = {"https://www.nice.org.uk/guidance/ta1":
             (PAGE, 200, "https://www.nice.org.uk/guidance/ta999")}
    crawl.crawl(targets(1), tmp_path, tmp_path / "m.jsonl",
                opener=make_opener(pages), sleep=lambda s: None, log=lambda m: None)
    record = crawl.read_manifest(tmp_path / "m.jsonl")["TA001"]
    assert record.redirected is True
    assert record.url_final.endswith("/ta999")


def test_the_manifest_records_everything_the_dod_asks_for(tmp_path):
    crawl.crawl(targets(1), tmp_path, tmp_path / "m.jsonl",
                opener=make_opener(pages_for(1)), sleep=lambda s: None, log=lambda m: None)
    row = json.loads((tmp_path / "m.jsonl").read_text().splitlines()[0])
    assert set(row) >= {"key", "path", "retrieved_at", "sha256", "http_status"}
    assert row["sha256"] == __import__("hashlib").sha256(PAGE).hexdigest()
    assert Path(row["path"]).read_bytes() == PAGE      # cached raw and unmodified


def test_a_legacy_manifest_keyed_on_appraisal_id_still_reads(tmp_path):
    """Lap 2a's manifest predates chapters. Renaming the key must not orphan it."""
    legacy = {"appraisal_id": "TA081", "url_requested": "u", "url_final": "u",
              "redirected": False, "http_status": 200, "path": "p", "sha256": "s",
              "bytes": 10, "retrieved_at": "2026-08-19T00:00:00+00:00", "error": None}
    (tmp_path / "m.jsonl").write_text(json.dumps(legacy) + "\n")
    record = crawl.read_manifest(tmp_path / "m.jsonl")["TA081"]
    assert record.key == "TA081" and record.appraisal_id == "TA081"


def test_a_chapter_key_addresses_a_chapter_and_knows_its_appraisal(tmp_path):
    url = "https://www.nice.org.uk/guidance/ta81/chapter/1-Recommendations"
    opener = make_opener({url: (PAGE, 200, url)})
    crawl.crawl([("TA081/1-Recommendations", url)], tmp_path, tmp_path / "m.jsonl",
                opener=opener, sleep=lambda s: None, log=lambda m: None)
    record = crawl.read_manifest(tmp_path / "m.jsonl")["TA081/1-Recommendations"]
    assert record.appraisal_id == "TA081"
    assert Path(record.path) == tmp_path / "ta81" / "1-Recommendations.html"
    assert Path(record.path).read_bytes() == PAGE


def test_chapters_of_the_same_appraisal_do_not_collide(tmp_path):
    base = "https://www.nice.org.uk/guidance/ta81/chapter/"
    urls = {base + s: (PAGE, 200, base + s) for s in ("1-Recommendations", "3-Committee-discussion")}
    targets = [(f"TA081/{s}", base + s) for s in ("1-Recommendations", "3-Committee-discussion")]
    crawl.crawl(targets, tmp_path, tmp_path / "m.jsonl", opener=make_opener(urls),
                sleep=lambda s: None, log=lambda m: None)
    assert sorted(p.name for p in (tmp_path / "ta81").iterdir()) == [
        "1-Recommendations.html", "3-Committee-discussion.html"]
