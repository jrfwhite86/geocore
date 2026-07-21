"""Semantic validation for parsed EHS documents (Increment 3).

Deliberately plain dataclasses + hand-written checks, not Pydantic — this
repo's plan documents (tasks/plan/phase-3b-pipeline-implementation.md Task 8)
anticipated Pydantic for AGS4/CPT-JSON, but that is not yet implemented and
not yet an approved dependency; adding a second new runtime dependency in
the same increment as openpyxl wasn't asked for, and EHS's validation rules
are simple enough that plain dataclasses satisfy "explicit data models,
small focused functions" without it (see incremental-implementation skill's
Rule 0: simplicity first). Revisit if/when Pydantic is actually added for
the AGS/JSON paths and reuse becomes worthwhile.

known_hole_type_codes / known_survey_phase_codes / known_hole_status_codes /
known_termination_reason_codes are deliberately caller-supplied rather than
hardcoded here: they mirror reference.hole_type / reference.survey_phase /
reference.hole_status / reference.termination_reason
(geodb/sql/110__reference_investigation_enums.sql,
geodb/sql/122__reference_hole_status_enums.sql), and hardcoding a second copy
of seeded reference data in Python would create exactly the kind of drift
risk this repo's data-integrity standard warns against. In the full pipeline
these are resolved from the database at run time (a later load-stage-adjacent
increment); unit tests pass static sets instead, keeping this module DB-free
per the "local DB deferred" decision.

**RESOLVED (2026-07-10):** an earlier version of this docstring flagged a
real gap — the reference workbook's own header ('Survey phase code' ==
'GTP') did not match any seeded reference.survey_phase code (GTR/GTD only).
Per user decision, 'GTP' ("Geotechnical preliminary") is now seeded in
geodb/sql/110__reference_investigation_enums.sql, so this is no longer a
rejection case. See test_validate_semantic_xlsx.py's
test_reference_workbook_survey_phase_code_is_recognised (renamed from
..._is_not_yet_seeded) for the now-passing grounding test.

**2026-07-16 progress-tracking revision:** the EHS layout now carries
hole-level progress fields (hole_status_code, target_depth_m/final_depth_m,
termination_reason_code, start_date/end_date, actual_easting_m/
actual_northing_m). This module validates each field's own shape/range and
known-code membership; it deliberately does NOT enforce cross-field
consistency between hole_status_code and termination_reason_code (e.g.
"COMPLETED implies no termination_reason_code") -- see
geodb/sql/124__geotech_exploratory_hole_status.sql's column comment for why
that convention is intentionally NOT a hard CHECK, to avoid forcing strict
ETL ordering. "Position context" (table column J) is read through
unvalidated -- see mappings.xlsx.ehs.POSITION_CONTEXT_CROSS_CHECK_ONLY; its
cross-check happens in the load stage (Task 14a), not here, since it needs
the load stage's own DB-resolved asset/cluster association to compare
against.

**2026-07-16 second revision (bumpover parent hole):** bumpover_label is
validated here against the same '^[a-z]$' pattern as the DB CHECK
(geodb/sql/120__geotech_site_investigation.sql). "Bumpover parent hole" is
read through as an unresolved contractor_hole_name string (parent_hole_name)
-- resolving it to an actual exploratory_hole_id needs a live DB lookup, so
that happens at the load stage (see mappings.xlsx.ehs.
BUMPOVER_PARENT_HOLE_RESOLUTION), NOT here. What this stage DOES enforce,
since both are pure string-level checks needing no DB access:
bumpover_label and parent_hole_name must be present-or-absent together
(both-or-neither), and parent_hole_name must not name the row's own
contractor_hole_name (self-reference) -- an unresolvable-but-different name
is deliberately NOT rejected here; that is the load stage's flag-don't-block
job.
"""

from __future__ import annotations

import math
import re
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from ...mappings.types import RejectedRow
from ...parse.xlsx import EhsDocument

_EPSG_PATTERN = re.compile(r"EPSG:\s*(\d+)", re.IGNORECASE)
_BUMPOVER_LABEL_PATTERN = re.compile(r"^[a-z]$")


@dataclass(frozen=True)
class ValidatedEhsHeader:
    """Header-block values after semantic validation — one per document."""

    si_name: str
    survey_phase_code: str
    contractor: str | None
    coordinate_system_epsg: int
    project_name: str | None
    project_code: str | None


@dataclass(frozen=True)
class ValidatedEhsHoleRow:
    """One validated hole row — safe to hand to the transform stage."""

    row_number: int
    contractor_hole_name: str
    hole_type_code: str
    asset_or_cluster_name: str | None
    planned_easting_m: float
    planned_northing_m: float
    hole_status_code: str
    target_depth_m: float | None
    final_depth_m: float | None
    termination_reason_code: str | None
    start_date: date | None
    end_date: date | None
    actual_easting_m: float | None
    actual_northing_m: float | None
    comments: str | None
    position_context: str | None
    bumpover_label: str | None
    parent_hole_name: str | None


@dataclass(frozen=True)
class ValidatedEhsDocument:
    source_path: Path
    header: ValidatedEhsHeader
    hole_rows: list[ValidatedEhsHoleRow]


def validate_ehs_document(
    document: EhsDocument,
    *,
    known_hole_type_codes: Collection[str],
    known_survey_phase_codes: Collection[str],
    known_hole_status_codes: Collection[str],
    known_termination_reason_codes: Collection[str],
) -> tuple[ValidatedEhsDocument | None, list[RejectedRow]]:
    """Validate a parsed EhsDocument's header and hole rows.

    Returns:
        A (validated_document, rejected_rows) pair. If the header itself is
        invalid, validated_document is None and EVERY hole row is rejected
        too (with a reason referencing the header failure) — per
        geodb/python/docs/ehs-etl-mapping.md's COORDINATE_SYSTEM_RESOLUTION:
        a missing/unparseable coordinate system, or a missing/unrecognised
        si_name/survey_phase_code, makes the whole file unloadable, not just
        one row. Never raises for bad *data* — only a caller-usage error
        (e.g. malformed known_* arguments) would raise, and none of the
        checks here can trigger that.
    """

    header, header_rejections = _validate_header(
        document, known_survey_phase_codes=known_survey_phase_codes
    )

    if header is None:
        whole_file_rejections = list(header_rejections) + [
            RejectedRow(
                source_file=str(document.source_path),
                group="hole_row",
                row_number=int(row["_row_number"]),  # type: ignore[arg-type]
                reason="Rejected: EHS header block failed validation (see header rejection).",
                field_name=None,
            )
            for row in document.hole_rows
        ]
        return None, whole_file_rejections

    valid_rows: list[ValidatedEhsHoleRow] = []
    rejections: list[RejectedRow] = list(header_rejections)
    seen_hole_names: set[str] = set()

    for row in document.hole_rows:
        validated_row, row_rejections = _validate_hole_row(
            row,
            document.source_path,
            known_hole_type_codes=known_hole_type_codes,
            known_hole_status_codes=known_hole_status_codes,
            known_termination_reason_codes=known_termination_reason_codes,
        )
        rejections.extend(row_rejections)
        if validated_row is None:
            continue

        if validated_row.contractor_hole_name in seen_hole_names:
            rejections.append(
                RejectedRow(
                    source_file=str(document.source_path),
                    group="hole_row",
                    row_number=validated_row.row_number,
                    reason=(
                        "Rejected: duplicate contractor_hole_name "
                        f"'{validated_row.contractor_hole_name}' within this file "
                        "(unique per site_investigation)."
                    ),
                    field_name="Exploratory hole name",
                )
            )
            continue

        seen_hole_names.add(validated_row.contractor_hole_name)
        valid_rows.append(validated_row)

    return ValidatedEhsDocument(document.source_path, header, valid_rows), rejections


def _validate_header(
    document: EhsDocument, *, known_survey_phase_codes: Collection[str]
) -> tuple[ValidatedEhsHeader | None, list[RejectedRow]]:
    header = document.header
    rejections: list[RejectedRow] = []

    si_name = _clean_str(header.get("Site investigation name"))
    if not si_name:
        rejections.append(
            _header_rejection(
                document.source_path, "Site investigation name", "required, was blank/missing"
            )
        )

    survey_phase_code = _clean_str(header.get("Survey phase code"))
    if not survey_phase_code:
        rejections.append(
            _header_rejection(
                document.source_path, "Survey phase code", "required, was blank/missing"
            )
        )
    elif survey_phase_code not in known_survey_phase_codes:
        rejections.append(
            _header_rejection(
                document.source_path,
                "Survey phase code",
                f"'{survey_phase_code}' is not a known reference.survey_phase code "
                f"(known: {sorted(known_survey_phase_codes)})",
            )
        )

    contractor = _clean_str(header.get("Contractor"))

    epsg_code = _parse_epsg(header.get("Horizontal CRS (EPSG)"))
    if epsg_code is None:
        rejections.append(
            _header_rejection(
                document.source_path,
                "Horizontal CRS (EPSG)",
                f"missing or unparseable EPSG code, found {header.get('Horizontal CRS (EPSG)')!r}",
            )
        )

    if rejections:
        return None, rejections

    return (
        ValidatedEhsHeader(
            si_name=si_name,  # type: ignore[arg-type]  -- guaranteed non-None: no rejections above
            survey_phase_code=survey_phase_code,  # type: ignore[arg-type]
            contractor=contractor,
            coordinate_system_epsg=epsg_code,  # type: ignore[arg-type]
            project_name=_clean_str(header.get("Project name")),
            project_code=_clean_str(header.get("Project code")),
        ),
        rejections,
    )


def _validate_hole_row(
    row: dict[str, object],
    source_path: Path,
    *,
    known_hole_type_codes: Collection[str],
    known_hole_status_codes: Collection[str],
    known_termination_reason_codes: Collection[str],
) -> tuple[ValidatedEhsHoleRow | None, list[RejectedRow]]:
    row_number = int(row["_row_number"])  # type: ignore[arg-type]
    rejections: list[RejectedRow] = []

    contractor_hole_name = _clean_str(row.get("Exploratory hole name"))
    if not contractor_hole_name:
        rejections.append(
            _row_rejection(
                source_path, row_number, "Exploratory hole name", "required, was blank/missing"
            )
        )

    hole_type_code = _clean_str(row.get("Hole type code"))
    if not hole_type_code:
        rejections.append(
            _row_rejection(
                source_path, row_number, "Hole type code", "required, was blank/missing"
            )
        )
    elif hole_type_code not in known_hole_type_codes:
        rejections.append(
            _row_rejection(
                source_path,
                row_number,
                "Hole type code",
                f"'{hole_type_code}' is not a known reference.hole_type code "
                f"(known: {sorted(known_hole_type_codes)})",
            )
        )

    # Optional: a blank "Cluster / asset name" means a genuinely standalone
    # hole (no cluster/asset association at all) -- see
    # geotech.exploratory_hole's CHECK constraint (2026-07-15 loosened from
    # "exactly one" to "at most one" of layout_asset_id/asset_location_id/
    # cluster_location_id specifically to support this). Not a rejection.
    asset_or_cluster_name = _clean_str(row.get("Cluster / asset name"))

    easting = _parse_finite_float(row.get("Target easting [m]"))
    if easting is None:
        rejections.append(
            _row_rejection(
                source_path,
                row_number,
                "Target easting [m]",
                f"required numeric value, found {row.get('Target easting [m]')!r}",
            )
        )

    northing = _parse_finite_float(row.get("Target northing [m]"))
    if northing is None:
        rejections.append(
            _row_rejection(
                source_path,
                row_number,
                "Target northing [m]",
                f"required numeric value, found {row.get('Target northing [m]')!r}",
            )
        )

    # hole_status_code: blank defaults to SCHEDULED (mirrors the DB column's
    # own NOT NULL DEFAULT 'SCHEDULED'); a non-blank value must be known.
    raw_hole_status = _clean_str(row.get("Hole status"))
    hole_status_code = raw_hole_status or "SCHEDULED"
    if hole_status_code not in known_hole_status_codes:
        rejections.append(
            _row_rejection(
                source_path,
                row_number,
                "Hole status",
                f"'{hole_status_code}' is not a known reference.hole_status code "
                f"(known: {sorted(known_hole_status_codes)})",
            )
        )

    target_depth_m, target_depth_rejection = _validate_optional_non_negative_float(
        row.get("Target depth [m BSF]"), source_path, row_number, "Target depth [m BSF]"
    )
    if target_depth_rejection is not None:
        rejections.append(target_depth_rejection)

    final_depth_m, final_depth_rejection = _validate_optional_non_negative_float(
        row.get("Final depth [m BSF]"), source_path, row_number, "Final depth [m BSF]"
    )
    if final_depth_rejection is not None:
        rejections.append(final_depth_rejection)

    termination_reason_code = _clean_str(row.get("Termination reason"))
    if (
        termination_reason_code is not None
        and termination_reason_code not in known_termination_reason_codes
    ):
        rejections.append(
            _row_rejection(
                source_path,
                row_number,
                "Termination reason",
                f"'{termination_reason_code}' is not a known reference.termination_reason code "
                f"(known: {sorted(known_termination_reason_codes)})",
            )
        )

    start_date, start_date_rejection = _validate_optional_date(
        row.get("Start date [yyyymmdd]"), source_path, row_number, "Start date [yyyymmdd]"
    )
    if start_date_rejection is not None:
        rejections.append(start_date_rejection)

    end_date, end_date_rejection = _validate_optional_date(
        row.get("End date [yyyymmdd]"), source_path, row_number, "End date [yyyymmdd]"
    )
    if end_date_rejection is not None:
        rejections.append(end_date_rejection)

    raw_actual_easting = row.get("As-installed easting [m]")
    raw_actual_northing = row.get("As-installed northing [m]")
    actual_easting = _parse_finite_float(raw_actual_easting)
    actual_northing = _parse_finite_float(raw_actual_northing)

    if (
        actual_easting is None
        and raw_actual_easting is not None
        and not (isinstance(raw_actual_easting, str) and not raw_actual_easting.strip())
    ):
        rejections.append(
            _row_rejection(
                source_path,
                row_number,
                "As-installed easting [m]",
                f"optional numeric value, found {raw_actual_easting!r}",
            )
        )
    if (
        actual_northing is None
        and raw_actual_northing is not None
        and not (isinstance(raw_actual_northing, str) and not raw_actual_northing.strip())
    ):
        rejections.append(
            _row_rejection(
                source_path,
                row_number,
                "As-installed northing [m]",
                f"optional numeric value, found {raw_actual_northing!r}",
            )
        )

    # Both-or-neither, mirroring the DB's
    # (actual_easting_m IS NULL) = (actual_northing_m IS NULL) CHECK.
    if (actual_easting is None) != (actual_northing is None):
        rejections.append(
            _row_rejection(
                source_path,
                row_number,
                "As-installed easting [m]",
                "'As-installed easting [m]' and 'As-installed northing [m]' must be "
                f"both present or both blank, found easting={raw_actual_easting!r}, "
                f"northing={raw_actual_northing!r}",
            )
        )

    comments = _clean_str(row.get("Remarks"))
    position_context = _clean_str(row.get("Position context"))

    bumpover_label = _clean_str(row.get("Bumpover label"))
    if bumpover_label is not None and not _BUMPOVER_LABEL_PATTERN.fullmatch(bumpover_label):
        rejections.append(
            _row_rejection(
                source_path,
                row_number,
                "Bumpover label",
                f"optional single lowercase letter if present (mirrors the DB's "
                f"own '^[a-z]$' CHECK), found {bumpover_label!r}",
            )
        )

    parent_hole_name = _clean_str(row.get("Bumpover parent hole"))

    # Both-or-neither: a bumpover_label without a parent hole name (or vice
    # versa) is a source-data inconsistency, not something the load stage's
    # flag-don't-block resolution should have to paper over.
    if (bumpover_label is None) != (parent_hole_name is None):
        rejections.append(
            _row_rejection(
                source_path,
                row_number,
                "Bumpover label",
                "'Bumpover label' and 'Bumpover parent hole' must be both present "
                f"or both blank, found bumpover_label={bumpover_label!r}, "
                f"parent_hole_name={parent_hole_name!r}",
            )
        )

    # Self-reference: a hole cannot bump over itself. Checked at the string
    # level here since it needs no DB access -- an unresolvable-but-different
    # name is deliberately left to the load stage's flag-don't-block lookup.
    if (
        parent_hole_name is not None
        and contractor_hole_name is not None
        and parent_hole_name == contractor_hole_name
    ):
        rejections.append(
            _row_rejection(
                source_path,
                row_number,
                "Bumpover parent hole",
                f"'Bumpover parent hole' cannot name the row's own "
                f"'Exploratory hole name' ({parent_hole_name!r}) -- a hole cannot "
                "bump over itself",
            )
        )

    if rejections:
        return None, rejections

    return (
        ValidatedEhsHoleRow(
            row_number=row_number,
            contractor_hole_name=contractor_hole_name,  # type: ignore[arg-type]
            hole_type_code=hole_type_code,  # type: ignore[arg-type]
            asset_or_cluster_name=asset_or_cluster_name,
            planned_easting_m=easting,  # type: ignore[arg-type]
            planned_northing_m=northing,  # type: ignore[arg-type]
            hole_status_code=hole_status_code,
            target_depth_m=target_depth_m,
            final_depth_m=final_depth_m,
            termination_reason_code=termination_reason_code,
            start_date=start_date,
            end_date=end_date,
            actual_easting_m=actual_easting,
            actual_northing_m=actual_northing,
            comments=comments,
            position_context=position_context,
            bumpover_label=bumpover_label,
            parent_hole_name=parent_hole_name,
        ),
        rejections,
    )


def _clean_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_epsg(value: object) -> int | None:
    if value is None:
        return None
    match = _EPSG_PATTERN.search(str(value))
    if match is None:
        return None
    return int(match.group(1))


def _parse_finite_float(value: object) -> float | None:
    if isinstance(value, bool):  # bool is an int subclass — reject explicitly
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    return None


def _validate_optional_non_negative_float(
    value: object, source_path: Path, row_number: int, field_name: str
) -> tuple[float | None, RejectedRow | None]:
    """Optional numeric >= 0 (mirrors the DB's own CHECK). Blank -> None,
    not a rejection; a non-blank, non-numeric, or negative value IS a
    rejection (caught here with a friendly message rather than surfacing a
    raw psycopg error at load time)."""

    if value is None or (isinstance(value, str) and not value.strip()):
        return None, None

    parsed = _parse_finite_float(value)
    if parsed is None or parsed < 0:
        return None, _row_rejection(
            source_path,
            row_number,
            field_name,
            f"optional numeric value must be >= 0 if present, found {value!r}",
        )
    return parsed, None


def _validate_optional_date(
    value: object, source_path: Path, row_number: int, field_name: str
) -> tuple[date | None, RejectedRow | None]:
    """Optional date. openpyxl may return a datetime.date/datetime (a
    date-formatted cell) or a bare yyyymmdd int/string (a text-formatted
    cell, per the header's own '[yyyymmdd]' hint) -- both representations
    parse to the same date. Blank -> None, not a rejection; an unparsable
    non-blank value IS a rejection, never silently None'd."""

    if value is None or (isinstance(value, str) and not value.strip()):
        return None, None

    if isinstance(value, datetime):
        return value.date(), None
    if isinstance(value, date):
        return value, None

    text = str(value).strip()
    if re.fullmatch(r"\d{8}", text):
        try:
            return datetime.strptime(text, "%Y%m%d").date(), None
        except ValueError:
            pass

    return None, _row_rejection(
        source_path,
        row_number,
        field_name,
        f"unparseable date, expected a date cell or 'yyyymmdd' text, found {value!r}",
    )


def _header_rejection(source_path: Path, field_name: str, reason: str) -> RejectedRow:
    return RejectedRow(
        source_file=str(source_path),
        group="header",
        row_number=0,
        reason=f"Rejected: {reason}",
        field_name=field_name,
    )


def _row_rejection(
    source_path: Path, row_number: int, field_name: str, reason: str
) -> RejectedRow:
    return RejectedRow(
        source_file=str(source_path),
        group="hole_row",
        row_number=row_number,
        reason=f"Rejected: {reason}",
        field_name=field_name,
    )


