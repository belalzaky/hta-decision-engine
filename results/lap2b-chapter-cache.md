# Lap 2b — the substantive chapter cache

Written by `python -m hta.cli inventory`. Targets came from the **cached overview
pages**, never a guessed URL pattern and never the site. **Nothing is parsed out of the
chapter bodies here** — Lap 2 caches, Lap 3 extracts.

## Coverage

| Quantity | n |
|---|---|
| Chapters targeted | 1635 |
| Cached | **1635** |
| Failed | 0 |
| Missing | 0 |
| Appraisals with at least one substantive chapter | 921 |
| On disk | 64.7 MB (mean 39,574 bytes per chapter) |

## By chapter type

| Chapter slug | Targeted | Cached |
|---|---|---|
| `Recommendations` | 718 | 718 |
| `Committee-discussion` | 538 | 538 |
| `Advice` | 149 | 149 |
| `Consideration-of-the-evidence` | 109 | 109 |
| `Evidence-and-interpretation` | 70 | 70 |
| `Recommendation` | 51 | 51 |

## What it cost, measured

| Quantity | Value |
|---|---|
| Requests (manifest rows, retries included) | 1638 |
| Time actually crawling | 5,194 s (87 minutes) |
| Per request | **3.17 s** |
| Idle gaps excluded (smoke test, retry) | 0 |

The 2-second delay is a floor; NICE's response time sits on top of it. Lap 2a measured
2.93 s per request on overview pages, so chapters are marginally slower — they are larger
(mean 39,574 bytes against roughly 15,000 for an overview).

## Failures

**None outstanding.** Every targeted chapter is on disk.

**3 transient failures were recovered by re-running**, which is the resume path working rather than a clean run:

| Key | First attempt |
|---|---|
| TA390/4-Committee-discussion | IncompleteRead: IncompleteRead(32768 bytes read) |
| TA413/4-Committee-discussion | TimeoutError: The read operation timed out |
| TA651/3-Committee-discussion | IncompleteRead: IncompleteRead(32768 bytes read) |

All three were network-level — an incomplete read or a read timeout, never an HTTP
status. Recorded rather than smoothed over: a crawl of this size against a public
body will drop a connection occasionally, and the design point is that it costs a
re-run of three requests, not of 1,635.

---

Derived from NICE published data. NICE does not endorse this work. The cache is never
redistributed — see `LICENSING.md`.
