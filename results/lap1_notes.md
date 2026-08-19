# Lap 1 — decisions that shaped the build, including the ones not taken

House style: record what did not work, and what was deliberately left alone. Three things.

## 1 · The licence forced the test design, and made it better

`data/raw/` is never redistributed, so CI has no NICE file to test against. The obvious answers
were both bad: mock the data (proves nothing) or commit the spreadsheet (a licence problem made
permanent).

What shipped instead is a **structural surrogate** — a 1531-row frame rebuilt at test time from
`tests/fixtures/nice_marginals.json`, which holds the marginal counts and the short verbatim
categorical values and no NICE free text. It reproduces the real distribution exactly, so the 87%
check genuinely runs in CI. The real file is still tested, in `tests/test_real_file.py`, which
skips when the cache is absent, and one of its cases asserts the fixture still matches the real
marginals — so the surrogate cannot silently drift away from what it stands in for.

The constraint improved the design: there are now three test tiers where there would have been one.

## 2 · `technology_type_raw` has a case variant, and it was NOT normalised

`Medical device` (n=46) and `Medical Device` (n=1) are one category with two spellings — the same
defect the outcome column has in three places, in a column Schema v1 specifies **verbatim only**.

Normalising it would have been one line. It was left alone because the schema was approved without
a normalised sibling for it, and a lap that quietly adds fields is a lap that grows. The trap is
documented instead — in the data dictionary, in `results/reconciliation.md`, and in a test that
asserts both spellings survive. **Anyone stratifying on technology type must fold case first.**

Flagged for Lap 3, where the schema is open again.

## 3 · What was checked and found already correct

Every figure Lap 0 measured reproduced exactly on the first build: 1531 / 1181, gapless TA1–TA1181,
174 non-submissions, 662 cancer recommendations, and 75.51 / 85.19 / 87.11%. Nothing in Lap 0
needed correcting — unusual enough to be worth writing down, since the previous lap corrected two
figures in the layer above it.

The one thing Lap 0 did not record: the `Technology type` case variant. Six raw values, five real
categories. Found in Lap 1, item 2 above.
