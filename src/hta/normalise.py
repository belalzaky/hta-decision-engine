"""Normalisation of NICE's raw categorical columns.

The rule this whole dataset rests on: **a normalised field never replaces the
verbatim one, it sits next to it.** Anyone who disagrees with a mapping can redo
it from the raw column. That is also a licence condition — the NICE UK Open
Content Licence forbids amending the wording of published recommendations, so
the raw text ships untouched and the derivation ships beside it.

Every mapping here is exhaustive over the values measured in Lap 0 and raises on
anything it has not seen. A new NICE category must break the build, not fall
through to a null: silent nulls are how the outcome mapping would drift without
anyone noticing, and the 87% check downstream is only meaningful if nothing can
quietly leave the denominator.
"""
from __future__ import annotations

import re

#: Raw ``Categorisation (for specific recommendation)`` -> canonical outcome.
#: 12 raw values, three of them pure case variants, collapse to 9 outcomes.
OUTCOME_MAP = {
    "Recommended": "recommended",
    "recommended": "recommended",
    "Optimised": "optimised",
    "Recommended (CDF)": "cdf_recommended",
    "Optimised (CDF)": "cdf_optimised",
    "Recommended (IMF)": "imf_recommended",
    "Optimised (IMF)": "imf_optimised",
    "Only in research": "only_in_research",
    "Only in Research": "only_in_research",
    "Not recommended": "not_recommended",
    "Not Recommended": "not_recommended",
    "Terminated Appraisal - non submission": "terminated_non_submission",
}

#: The nine canonical outcomes, in reporting order.
OUTCOMES = [
    "recommended",
    "optimised",
    "cdf_recommended",
    "cdf_optimised",
    "imf_recommended",
    "imf_optimised",
    "only_in_research",
    "not_recommended",
    "terminated_non_submission",
]

#: Outcomes NICE counts as positive in its published "87% of our recommendations
#: have been positive" figure — recommended, optimised, or via a managed access
#: fund. Reproducing that figure exactly is the external validity check on this
#: mapping (see hta.reconcile).
POSITIVE_OUTCOMES = frozenset(
    {
        "recommended",
        "optimised",
        "cdf_recommended",
        "cdf_optimised",
        "imf_recommended",
        "imf_optimised",
    }
)

#: ``STA/MTA process`` is two orthogonal facts in one string: single- vs
#: multiple-technology appraisal, and whether this is an original appraisal or a
#: review of one. It is NOT the appraisal *route* — there is no cost-comparison,
#: HST or fast-track value anywhere in the column, which is why `route` is
#: deferred to Lap 3 rather than invented here.
_PROCESS_RE = re.compile(r"^(STA|MTA)(?:\s*\((review|part-review|rapid review)\))?$")

TERMINATED_OUTCOME = "terminated_non_submission"


def _fail(column: str, values) -> None:
    raise ValueError(
        f"unmapped value(s) in {column!r}: {sorted(values)!r}. "
        "NICE has published a category this mapping has not seen. Add it "
        "deliberately — do not let it become a null."
    )


def map_outcome(raw: str) -> str:
    """Map one raw categorisation to its canonical outcome."""
    try:
        return OUTCOME_MAP[raw]
    except KeyError:
        _fail("Categorisation (for specific recommendation)", {raw})


def split_process(raw: str) -> tuple[str, str]:
    """Split ``STA (rapid review)`` into ``("STA", "rapid review")``.

    An unqualified ``STA``/``MTA`` is an original appraisal.
    """
    m = _PROCESS_RE.match(raw.strip())
    if not m:
        _fail("STA/MTA process", {raw})
    return m.group(1), m.group(2) or "original"


def depad(appraisal_id: str) -> str:
    """``TA081`` -> ``TA81``.

    The padded form is what NICE publishes in the spreadsheet and is kept
    verbatim; the *canonical URL* is unpadded. Lap 0 measured `/guidance/ta081`
    resolving to `/guidance/ta81` via a redirect, so building URLs from the
    padded ID would cost ~1,200 avoidable round-trips in Lap 2.
    """
    m = re.match(r"^TA0*(\d+)$", appraisal_id.strip())
    if not m:
        _fail("TA ID", {appraisal_id})
    return f"TA{int(m.group(1))}"


def appraisal_url(appraisal_id: str) -> str:
    return f"https://www.nice.org.uk/guidance/{depad(appraisal_id).lower()}"


def recommendation_id(appraisal_id: str, seq_within_appraisal: int) -> str:
    """``TA1121`` + 1 -> ``TA1121-01``.

    Built on the *padded* published ID so the key sorts and joins the way NICE's
    own file does. Two digits is enough: the widest appraisal (TA081) carries 16
    recommendations.
    """
    if seq_within_appraisal < 1:
        raise ValueError("recommendation sequence is 1-based")
    return f"{appraisal_id}-{seq_within_appraisal:02d}"
