"""Lap 2a — the polite crawler for NICE guidance overview pages.

The crawl rules are not tuning parameters. NICE is a public body publishing at
its own expense, and this project fetches ~1,181 pages from it:

- **1 request per 2 seconds, sequential, no concurrency.** robots.txt asks for
  `Crawl-delay: 1`; this is double it. A crawl-delay is a serial interval, not a
  budget to spend in parallel.
- **robots.txt is re-read at the start of any run that will fetch**, and the run
  aborts if it has tightened since Lap 0 measured it on 19 Aug 2026.
- **A real identifying User-Agent**, naming the project and a contact route.
- **Resume-safe.** Killed at request 700, a restart continues at 701. What is on
  disk is never re-fetched.
- **An empty 200 is a failure, not a page.** The run stops on the first one,
  rather than caching 1,181 shells and discovering it in Lap 3.

Nothing here parses anything into the dataset. It caches bytes and records what
happened. Inventory is `hta.inventory`; extraction is Lap 3.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

USER_AGENT = (
    "hta-decision-engine/0.2 (+https://github.com/belalzaky/hta-decision-engine)"
)
ROBOTS_URL = "https://www.nice.org.uk/robots.txt"

#: What Lap 0 read on 19 Aug 2026. A tightened robots.txt aborts the run.
LAP0_CRAWL_DELAY = 1.0
LAP0_DISALLOWED = (
    "/cks-is-only-available-in-the-uk",
    "/cks-end-user-licence-agreement",
)

#: Double the requested crawl-delay.
DELAY_SECONDS = 2.0
TIMEOUT_SECONDS = 30

#: A real overview page is ~10 KB even when superseded down to a stub.
MIN_BODY_BYTES = 500

#: Stop rather than hammer a site that has started refusing us.
MAX_CONSECUTIVE_FAILURES = 10


class CrawlAbort(RuntimeError):
    """The run stopped deliberately. The message says why."""


@dataclass
class Fetched:
    """One cached page, or one recorded failure. Written to the manifest.

    `key` addresses the thing fetched: an appraisal ID for an overview page
    (`TA081`), or an appraisal ID and chapter slug for a chapter
    (`TA081/1-Recommendations`). Lap 2a manifests written before the chapter
    crawl existed carry `appraisal_id` instead; `read_manifest` accepts both so
    an existing cache is not invalidated by the rename.
    """

    key: str
    url_requested: str
    url_final: str
    redirected: bool
    http_status: int | None
    path: str | None
    sha256: str | None
    bytes: int | None
    retrieved_at: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.http_status == 200

    @property
    def appraisal_id(self) -> str:
        """The appraisal this page belongs to, chapter or not."""
        return self.key.split("/", 1)[0]


# --------------------------------------------------------------------------
# robots.txt
# --------------------------------------------------------------------------

def parse_robots(text: str) -> dict:
    """Minimal parse of the `User-agent: *` group — the only one that binds us."""
    delay, disallowed, allowed, in_star = None, [], [], False
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            in_star = value == "*"
        elif in_star and key == "crawl-delay":
            delay = float(value)
        elif in_star and key == "disallow" and value:
            disallowed.append(value)
        elif in_star and key == "allow":
            allowed.append(value)
    return {"crawl_delay": delay, "disallow": disallowed, "allow": allowed}


def check_robots(text: str, *, path_prefix: str = "/guidance/") -> dict:
    """Abort if robots.txt has tightened since Lap 0, or now blocks /guidance/."""
    rules = parse_robots(text)

    blocking = [d for d in rules["disallow"] if path_prefix.startswith(d) or d == "/"]
    if blocking:
        raise CrawlAbort(
            f"robots.txt now disallows {path_prefix} via {blocking!r}. "
            "Lap 0 recorded /guidance/ as explicitly allowed on 19 Aug 2026. Stop."
        )

    new_rules = set(rules["disallow"]) - set(LAP0_DISALLOWED)
    if new_rules:
        raise CrawlAbort(
            f"robots.txt has new Disallow rules since Lap 0: {sorted(new_rules)!r}. "
            "None of them touch /guidance/, but the file has changed — re-read it "
            "by hand and update LAP0_DISALLOWED deliberately before crawling."
        )

    delay = rules["crawl_delay"]
    if delay is not None and delay > LAP0_CRAWL_DELAY:
        raise CrawlAbort(
            f"robots.txt has tightened Crawl-delay to {delay}s (Lap 0 saw "
            f"{LAP0_CRAWL_DELAY}s). Raise DELAY_SECONDS to at least {2 * delay}s "
            "deliberately before crawling."
        )
    return rules


def fetch_robots(opener=None) -> str:
    body, _, _, _ = _get(ROBOTS_URL, opener=opener)
    return body.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------------

def _get(url: str, opener=None) -> tuple[bytes, int, str, dict]:
    """One GET. Returns (body, status, final_url, headers)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    open_it = opener or urllib.request.urlopen
    with open_it(request, timeout=TIMEOUT_SECONDS) as response:
        return (
            response.read(),
            response.status,
            response.geturl(),
            dict(response.headers),
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cache_path(root: Path, url: str) -> Path:
    """`/guidance/ta81` -> `<root>/ta81.html`. De-padded, as the spine builds it."""
    slug = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    if not slug:
        raise ValueError(f"cannot derive a cache filename from {url!r}")
    return root / f"{slug}.html"


def path_for(root: Path, key: str, url: str) -> Path:
    """Where one fetch lands.

    An overview goes at `<root>/ta81.html`; a chapter goes one level down, at
    `<root>/ta81/1-Recommendations.html`, so the cache mirrors the URL and a
    directory listing reads like the site.
    """
    if "/" not in key:
        return cache_path(root, url)
    parts = [p for p in urlsplit(url).path.split("/") if p]
    # /guidance/ta81/chapter/1-Recommendations -> directory ta81, matching the
    # de-padded overview filename rather than the padded spreadsheet ID.
    directory = parts[1] if len(parts) > 1 else key.split("/", 1)[0].lower()
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", key.split("/", 1)[1])
    return root / directory / f"{safe}.html"


def fetch_one(key: str, url: str, root: Path, opener=None) -> Fetched:
    """Fetch one overview page and write it to the cache, unmodified.

    Raises `CrawlAbort` on an empty or implausibly short 200 — that is the
    failure mode worth stopping the whole run for, because it is silent.
    """
    path = path_for(root, key, url)
    try:
        body, status, final_url, _ = _get(url, opener=opener)
    except urllib.error.HTTPError as e:
        return Fetched(key, url, e.url or url, (e.url or url) != url,
                       e.code, None, None, None, _now(), f"HTTP {e.code} {e.reason}")
    except Exception as e:  # network-level: DNS, timeout, reset
        return Fetched(key, url, url, False, None, None, None, None,
                       _now(), f"{type(e).__name__}: {e}")

    if len(body) < MIN_BODY_BYTES:
        raise CrawlAbort(
            f"{url} returned HTTP {status} with a {len(body)}-byte body "
            f"(minimum {MIN_BODY_BYTES}). An empty 200 is a failure, not a page — "
            "stopping rather than caching shells. Nothing was written."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return Fetched(
        key=key,
        url_requested=url,
        url_final=final_url,
        redirected=final_url != url,
        http_status=status,
        path=str(path),
        sha256=hashlib.sha256(body).hexdigest(),
        bytes=len(body),
        retrieved_at=_now(),
    )


# --------------------------------------------------------------------------
# manifest
# --------------------------------------------------------------------------

def read_manifest(path: Path) -> dict[str, Fetched]:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        # Manifests written before chapters existed key on `appraisal_id`.
        row.setdefault("key", row.pop("appraisal_id", None))
        row.pop("appraisal_id", None)
        out[row["key"]] = Fetched(**row)
    return out


def append_manifest(path: Path, record: Fetched) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def outstanding(targets: list[tuple[str, str]], manifest: dict[str, Fetched]) -> list:
    """What still needs fetching: never on disk, or on disk but failed."""
    todo = []
    for key, url in targets:
        seen = manifest.get(key)
        if seen and seen.ok and seen.path and Path(seen.path).exists():
            continue
        todo.append((key, url))
    return todo


# --------------------------------------------------------------------------
# the run
# --------------------------------------------------------------------------

def crawl(
    targets: list[tuple[str, str]],
    root: Path,
    manifest_path: Path,
    *,
    delay: float = DELAY_SECONDS,
    limit: int | None = None,
    opener=None,
    sleep=time.sleep,
    log=print,
) -> dict:
    """Fetch every outstanding target, sequentially, politely, resumably."""
    manifest = read_manifest(manifest_path)
    todo = outstanding(targets, manifest)

    if not todo:
        log(f"cache complete: {len(targets)} targets, 0 network requests")
        return {"requested": 0, "ok": 0, "failed": 0, "skipped": len(targets),
                "robots_checked": False}

    # Only now — a full-cache run must make zero network requests, robots.txt
    # included, and there is nothing to be polite about if we fetch nothing.
    log(f"re-reading {ROBOTS_URL}")
    check_robots(fetch_robots(opener=opener))
    log("robots.txt unchanged since Lap 0")

    already_cached = len(targets) - len(todo)
    if limit is not None:
        todo = todo[:limit]

    log(f"{len(todo)} to fetch, {already_cached} already cached, "
        f"{delay}s apart — about {len(todo) * delay / 60:.0f} minutes")

    ok = failed = 0
    consecutive = 0
    for i, (key, url) in enumerate(todo, start=1):
        if i > 1:
            sleep(delay)
        record = fetch_one(key, url, root, opener=opener)
        append_manifest(manifest_path, record)

        if record.ok:
            ok += 1
            consecutive = 0
        else:
            failed += 1
            consecutive += 1
            log(f"  FAIL {key} {record.error}")
            if consecutive >= MAX_CONSECUTIVE_FAILURES:
                raise CrawlAbort(
                    f"{consecutive} consecutive failures ending at {key}. "
                    "Stopping rather than hammering a site that is refusing us. "
                    "The manifest records everything fetched so far; re-running "
                    "resumes."
                )
        if i % 50 == 0 or i == len(todo):
            log(f"  {i}/{len(todo)} ({ok} ok, {failed} failed)")

    return {"requested": len(todo), "ok": ok, "failed": failed,
            "skipped": already_cached,
            "deferred_by_limit": len(targets) - already_cached - len(todo),
            "robots_checked": True}
