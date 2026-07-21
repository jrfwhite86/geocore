"""AGS4 version detection: base dictionary version (TRAN_AGS) + the in-house
"AGS 4+ (Revision E)" extension flag (TRAN_REM) — two independent axes.

Grounded directly against real reference artefacts (not invented). The
.xlsx templates moved 2026-07-09 from geodb/sample-data/ags/ directly into
geodb/sample-data/ags/reference-files/ (a new addition to that move is
AGS4-0-4.xlsx, see below):
- geodb/sample-data/ags/bronze/Gardline (2023). HEW02_GTR_CPT-scope.ags
  (TRAN group: TRAN_AGS == "4.1.1", TRAN_REM == "").
- geodb/sample-data/ags/reference-files/AGS4+E.xlsx, Ørsted's in-house
  "AGS 4+ (Revision E)" template (TRAN group: TRAN_AGS == "4.0.4", TRAN_REM ==
  "AGS4+ Rev 00637136_E").
- geodb/sample-data/ags/reference-files/AGS4-1-1.xlsx, the public AGS4.1.1
  template, used as the comparison baseline for heading differences (see
  ags/loca.py, ags/cpt.py for the concrete heading-level findings this
  comparison produced).
- geodb/sample-data/ags/reference-files/AGS4-0-4.xlsx (added 2026-07-09), a
  dedicated public AGS4.0.4 template — NOT a Revision E file (no TRAN_REM
  marker expected). Grounds "4.0.4" as an ordinary, ungated base version in
  its own right, independent of AGS4+E.xlsx (which only ever demonstrated
  "4.0.4" *together with* Revision E, leaving open whether "4.0.4" alone was
  a genuine public base version or an Ørsted-only artefact — this file
  resolves that: "4.0.4" is a real public base version). Not yet diffed
  heading-by-heading against AGS4-1-1.xlsx/AGS4+E.xlsx (tracked as open, see
  REVISION_E_GAP and tasks/todo.md).

CORRECTION (2026-07-09): an earlier version of this module modelled
"AGS 4+ (Revision E)" as a value TRAN_AGS itself could take (a peer of "4.0",
"4.1", "4.1.1"). That was wrong, and disproven directly against the real
AGS4+E.xlsx template above: TRAN_AGS there is "4.0.4" (an ordinary base
version), and the *actual* Revision E marker lives in TRAN_REM. This module
now models both axes independently via AgsFileVersion.

No I/O, no python-ags4 dependency here — this module only interprets
already-parsed TRAN_AGS/TRAN_REM string values (the parse stage, Task 6, is
what reads the raw file).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..types import AgsVersion

# Known literal TRAN_AGS values -> AgsVersion. Deliberately a closed mapping,
# not a permissive parser (e.g. no attempt to regex "4.x" patterns) — an
# unrecognised value is a data-integrity question (per this repo's standard),
# not something to guess at. Includes "4.0.4" (confirmed real, from the
# AGS4+E.xlsx template's own TRAN row) alongside the publicly published
# "4.0"/"4.1"/"4.1.1" series.
KNOWN_TRAN_AGS_VALUES: dict[str, AgsVersion] = {
    "4.0": AgsVersion.V4_0,
    "4.0.4": AgsVersion.V4_0_4,
    "4.1": AgsVersion.V4_1,
    "4.1.1": AgsVersion.V4_1_1,
}

SUPPORTED_AGS_VERSIONS: list[AgsVersion] = [
    AgsVersion.V4_0,
    AgsVersion.V4_0_4,
    AgsVersion.V4_1,
    AgsVersion.V4_1_1,
]

# Matches the confirmed real marker "AGS4+ Rev 00637136_E" (any digit run,
# trailing "_E") — grounded in
# geodb/sample-data/ags/reference-files/AGS4+E.xlsx's own TRAN row rather
# than a guessed pattern. Case-insensitive since AGS text fields are not
# reliably cased consistently across contractor tooling.
REVISION_E_TRAN_REM_PATTERN = re.compile(r"AGS4\+\s*Rev\s*\d+_E", re.IGNORECASE)


class UnrecognisedAgsVersionError(ValueError):
    """Raised when a file's TRAN_AGS value doesn't match any known base version.

    A distinct exception type (not a bare ValueError) so later pipeline
    stages (Task 7 syntactic validation) can catch this specifically and
    turn it into a RejectedRow/quarantine reason with the offending value
    attached, rather than letting an unrecognised version crash the run or
    — worse — silently fall through to a default version's heading rules.
    """


def resolve_ags_version(tran_ags: str) -> AgsVersion:
    """Resolve a file's declared *base* AGS version from its raw TRAN_AGS value.

    Args:
        tran_ags: The TRAN group's TRAN_AGS cell value, as parsed (e.g.
            "4.1.1", or "4.0.4" for an AGS4+ (Revision E) file — Revision E's
            own TRAN_AGS is an ordinary base version, not a special value; see
            is_revision_e_marker() for the actual Revision E flag). Whitespace
            is stripped before matching.

    Returns:
        The matching AgsVersion.

    Raises:
        UnrecognisedAgsVersionError: if tran_ags does not match any entry in
            KNOWN_TRAN_AGS_VALUES. Never silently defaults to the newest known
            version — per this repo's data-integrity standard, an
            unrecognised declared version must not be guessed at, since
            heading availability (and therefore which FieldMapping entries
            apply) depends on it.
    """
    normalized = tran_ags.strip()
    try:
        return KNOWN_TRAN_AGS_VALUES[normalized]
    except KeyError as exc:
        raise UnrecognisedAgsVersionError(
            f"Unrecognised TRAN_AGS value {tran_ags!r}. Supported: "
            f"{sorted(v.value for v in KNOWN_TRAN_AGS_VALUES.values())}."
        ) from exc


def is_revision_e_marker(tran_rem: str) -> bool:
    """Whether a TRAN_REM value marks the file as AGS 4+ (Revision E).

    Independent of resolve_ags_version() — Revision E is layered on top of
    whatever base version TRAN_AGS declares, not a substitute for it (see
    module docstring's correction note). An empty or non-matching tran_rem
    returns False rather than raising, since a blank TRAN_REM is a normal,
    valid AGS4 file (see the reference Gardline fixture, whose TRAN_REM is
    empty) — this is a presence check, not a validation rule.
    """
    return bool(REVISION_E_TRAN_REM_PATTERN.search(tran_rem or ""))


@dataclass(frozen=True)
class AgsFileVersion:
    """A file's full, two-axis declared AGS version: base + Revision E flag.

    Attributes:
        base_version: The AgsVersion resolved from TRAN_AGS.
        is_revision_e: Whether TRAN_REM carries the Revision E marker
            (see is_revision_e_marker()). True means Revision E's additional
            headings (see ags/loca.py's *_REVISION_E_EXTRAS,
            ags/cpt.py's *_REVISION_E_EXTRAS) may be present in this file,
            in addition to base_version's ordinary heading set.
        raw_tran_rem: The unmodified TRAN_REM value, kept for traceability
            (e.g. attaching to a RejectedRow's context) even though only its
            Revision E marker match is currently interpreted.
    """

    base_version: AgsVersion
    is_revision_e: bool
    raw_tran_rem: str = ""


def resolve_ags_file_version(tran_ags: str, tran_rem: str = "") -> AgsFileVersion:
    """Resolve both axes of a file's declared AGS version in one call.

    Args:
        tran_ags: The TRAN group's TRAN_AGS value (see resolve_ags_version()).
        tran_rem: The TRAN group's TRAN_REM value (see is_revision_e_marker()).
            Defaults to "" for the common case of files with no remarks.

    Raises:
        UnrecognisedAgsVersionError: propagated from resolve_ags_version().
    """
    return AgsFileVersion(
        base_version=resolve_ags_version(tran_ags),
        is_revision_e=is_revision_e_marker(tran_rem),
        raw_tran_rem=tran_rem,
    )


# What remains open after the 2026-07-09 investigation (see chat log —
# geodb/sample-data/ags/reference-files/AGS4+E.xlsx and AGS4-1-1.xlsx were
# compared directly, DICT/ABBR sheets diffed group-by-group for
# PROJ/LOCA/SCPG/SCPT): the detection mechanism (this module) and the
# concrete v1-scope heading differences (see ags/loca.py's
# LOCA_FIELD_MAPPINGS_REVISION_E_EXTRAS, ags/cpt.py's
# SCPG_FIELD_MAPPINGS_REVISION_E_EXTRAS / SCPT_RATE_REVISION_E_GAP) are now
# resolved, grounded in the real templates rather than guessed. Still open:
# 1. AGS4+E.xlsx is a *template* (minimum groups for a valid file) — it does
#    not contain example SCPT/SCPG *data* rows, only DICT/ABBR/PROJ/TRAN/
#    TYPE/UNIT structure. A real Revision E data file (not just the template)
#    has not been checked against this mapping.
# 2. Only PROJ/LOCA/SCPG/SCPT (v1 scope) and LOCA_TYPE's ABBR picklist were
#    diffed in detail. Other ABBR picklists (e.g. SCPG_TYPE's cone-type list)
#    and the TYPE/UNIT sheets were not exhaustively compared.
# 3. Whether TRAN_AGS "4.0.4" is itself a stable, reusable signal (e.g. "any
#    Ørsted in-house template uses 4.0.4 as its base") or specific to this one
#    template file is unconfirmed — resolve_ags_version()/is_revision_e_marker()
#    are intentionally independent so this doesn't matter for detection
#    correctness (Revision E is identified via TRAN_REM regardless of which
#    base version TRAN_AGS declares).
# 4. NEW (2026-07-09): geodb/sample-data/ags/reference-files/AGS4-0-4.xlsx, a
#    dedicated public AGS4.0.4 template (not a Revision E file), has not yet
#    been diffed heading-by-heading against AGS4-1-1.xlsx/AGS4+E.xlsx the way
#    those two were compared against each other — it confirms "4.0.4" is a
#    real public base version, but its own heading set relative to 4.1.1 is
#    not yet characterised.
REVISION_E_GAP = (
    "Detection mechanism CONFIRMED (2026-07-09) against the real "
    "geodb/sample-data/ags/reference-files/AGS4+E.xlsx template: TRAN_AGS "
    "declares an ordinary base version ('4.0.4' in the template, itself not "
    "previously a known value — now added to AgsVersion/KNOWN_TRAN_AGS_VALUES, "
    "and independently confirmed as a real public base version by the "
    "dedicated reference-files/AGS4-0-4.xlsx template); the actual Revision E "
    "flag is TRAN_REM matching 'AGS4+ Rev <digits>_E' "
    "(REVISION_E_TRAN_REM_PATTERN). Concrete v1-scope heading differences "
    "for LOCA/SCPG/SCPT are now mapped (see ags/loca.py, ags/cpt.py). "
    "Still open: (1) the template contains no example SCPT/SCPG *data* rows, "
    "only structure — a real Revision E data file hasn't been checked; "
    "(2) not every ABBR picklist / the TYPE/UNIT sheets were exhaustively "
    "diffed, only LOCA_TYPE's; (3) whether '4.0.4' is a stable signal beyond "
    "these templates is unconfirmed (moot for detection correctness, since "
    "Revision E is identified via TRAN_REM independently of base version); "
    "(4) reference-files/AGS4-0-4.xlsx itself has not yet been diffed "
    "heading-by-heading against AGS4-1-1.xlsx/AGS4+E.xlsx."
)

# Separately from Revision E: LOCA_EPSG (used by the real Gardline reference
# fixture) is CONFIRMED ABSENT from both the public AGS4.1.1 dictionary
# template AND the AGS4+E (Revision E) dictionary template (2026-07-09 direct
# comparison) — it is not a version-gated standard/in-house heading at all.
# It is most likely a per-file/contractor DICT-group extension (AGS4 allows
# any file to declare custom headings via its own DICT group), though the
# Gardline fixture itself has no DICT group either (see
# geodb/python/docs/ags-etl-mapping.md's scope table: its 9 groups are ABBR/
# FILE/LOCA/PROJ/SCPG/SCPT/TRAN/TYPE/UNIT — no DICT) — meaning LOCA_EPSG is
# technically undeclared even by that file's own rules. Flagged here as a
# genuine, confirmed data-quality observation, not asserted as a "provisional,
# unverified" claim the way an earlier version of this note put it (that
# earlier phrasing undersold how concrete this finding now is).
LOCA_EPSG_NOT_IN_EITHER_DICTIONARY = (
    "LOCA_EPSG (used by the real Gardline reference fixture) does not appear "
    "in either geodb/sample-data/ags/reference-files/AGS4-1-1.xlsx's or "
    "AGS4+E.xlsx's DICT sheet for the LOCA group — confirmed by direct "
    "comparison, 2026-07-09. It is not a version-gated standard or in-house "
    "heading; most likely a per-file/contractor DICT extension, though the "
    "Gardline fixture itself has no DICT group declaring it either. The "
    "mapping's fallback order (LOCA_EPSG, else LOCA_GREF+LOCA_HDTM/LOCA_DATM, "
    "see ags.loca.COORDINATE_SYSTEM_RESOLUTION) does not depend on which "
    "dictionary a file declares, since it tries LOCA_EPSG first regardless."
)







