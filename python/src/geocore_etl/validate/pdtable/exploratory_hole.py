"""pdtable CSV validate stage for exploratory-hole-input (Phase 10c, revised 2026-07-17).

Plain dataclasses + hand-written checks -- never raises for bad data, every
failure becomes a ``RejectedRow`` per this repo's data-integrity standard.
Individual rows are independently droppable; the rest of the file still
validates around them.

Two blocks validated here:

- ``**cluster_details`` -> ``ValidatedClusterDetails`` list. Sources
  ``geotech.cluster_location`` rows.
- ``**exploratory_hole_details`` -> ``ValidatedExploratoryHole`` list.
  Sources ``geotech.exploratory_hole`` rows.

``hole_purpose`` is INFORMATIONAL only (see
``mappings.pdtable.exploratory_hole.HOLE_PURPOSE_INFORMATIONAL_ONLY``) and
is not stored on the validated dataclass -- ``asset_or_cluster_name`` is
the real discriminator for FK resolution and is deferred to the load stage.

**2026-07-20 revision (STANDALONE support):** ``asset_or_cluster_name`` is
now OPTIONAL, not required -- a blank value validates as ``None`` and the
load stage leaves ``layout_asset_id``/``asset_location_id``/
``cluster_location_id`` all NULL, producing a genuinely STANDALONE hole
(see ``mappings.pdtable.exploratory_hole.ASSET_OR_CLUSTER_RESOLUTION``).
This corrects a prior misreading of the file's own ``**exploratory_hole_
details`` / ``HEW02``-style destination tag: that value is the block's
``project_code`` destination (see the module's own docstring and
``mappings.pdtable.exploratory_hole``'s module docstring), never a
per-row asset/cluster name -- so a row is never implicitly linked by it,
and a reconnaissance-only campaign with no asset/cluster ties for any hole
is a perfectly valid file.

**2026-07-17 revision (FINAL_QAQC_AUTHORITY):** ``**exploratory_hole_details``
now also carries the progress/final-state columns EHS does --
``hole_status``, ``target_depth``, ``final_depth``, ``termination_reason``,
``start_date``, ``end_date``, ``bumpover_parent_hole``, ``comments`` --
mirroring ``validate.xlsx.ehs``'s equivalent checks (``known_hole_status_codes``
membership, both-or-neither/self-reference for the bumpover pair, optional
non-negative depths, optional yyyymmdd dates). The one rule EHS does NOT
enforce that this stage DOES (see
``mappings.pdtable.exploratory_hole.HOLE_STATUS_MUST_BE_TERMINAL``):
``hole_status`` must be a TERMINAL status -- a non-terminal value here is
rejected outright, since this file is meant to be the campaign's final,
QAQC'd snapshot, never a live progress feed.

**2026-07-20 revision (ACTUAL_POSITION_PRECEDENCE):** two more optional
columns, ``actual_easting``/``actual_northing`` (both-or-neither, mirroring
``validate.xlsx.ehs``'s "As-installed easting/northing" check) and
``seabed_level`` (plain optional float, no cross-field rule). This stage only
enforces shape -- the file-value-wins-else-echo-design-position precedence
is a load-stage decision (see
``mappings.pdtable.exploratory_hole.ACTUAL_POSITION_PRECEDENCE``).
"""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, datetime

from ...mappings.types import RejectedRow
from ...parse.pdtable.exploratory_hole import PdtableExploratoryHoleDocument

_BUMPOVER_LABEL_RE = re.compile(r"^[a-z]$")
# geotech.exploratory_hole.leg_label's DB CHECK was widened (Phase 10c) from
# ^[A-Z]+$ to ^[A-Za-z0-9]+$ to accommodate the real fixture's numeric leg
# labels ('1', '2', ...) used for OSS holes, per the file's own picklist
# prose ("Upper-case letters or numbers"). Validate here matches the DB
# constraint exactly so a rejected row here never reaches an opaque
# IntegrityError at load time.
_LEG_LABEL_RE = re.compile(r"^[A-Za-z0-9]+$")


@dataclass(frozen=True)
class ValidatedClusterDetails:
    """One validated cluster_details row -> geotech.cluster_location upsert input."""

    row_number: int
    cluster_name: str
    survey_phase_code: str
    eastings_m: float
    northings_m: float
    ground_level_m: float | None
    water_level_m: float | None
    comments: str | None


@dataclass(frozen=True)
class ValidatedExploratoryHole:
    """One validated exploratory_hole_details row.

    ``site_investigation_reference`` remains named after the source column,
    even though it carries a reference.survey_phase_code value (keeps
    parity with the "misleadingly named column" gotcha documented in
    ``mappings.pdtable.exploratory_hole.SITE_INVESTIGATION_RESOLUTION``).

    ``parent_hole_name`` carries the raw, unresolved "Bumpover parent hole"
    string (mirrors ``ValidatedEhsHoleRow.parent_hole_name``) -- resolved to
    ``parent_exploratory_hole_id`` by the load stage (see
    ``mappings.pdtable.exploratory_hole.BUMPOVER_PARENT_HOLE_RESOLUTION``).
    """

    row_number: int
    contractor_hole_name: str
    site_investigation_reference: str
    hole_type_code: str
    hole_number: str | None
    leg_label: str | None
    bumpover_label: str | None
    parent_hole_name: str | None
    hole_status_code: str
    target_depth_m: float | None
    final_depth_m: float | None
    termination_reason_code: str | None
    start_date: date | None
    end_date: date | None
    actual_easting_m: float | None
    actual_northing_m: float | None
    seabed_level_m: float | None
    comments: str | None
    asset_or_cluster_name: str | None


@dataclass(frozen=True)
class ValidatedPdtableExploratoryHoleDocument:
    """The fully validated contents of one input_exploratory_holes_{area_code}.csv."""

    source_path: str
    project_code: str
    cluster_details: list[ValidatedClusterDetails]
    exploratory_holes: list[ValidatedExploratoryHole]


def _reject(
    source_file: str,
    group: str,
    row_number: int,
    reason: str,
    field_name: str | None = None,
) -> RejectedRow:
    return RejectedRow(
        source_file=source_file,
        group=group,
        row_number=row_number,
        reason=reason,
        field_name=field_name,
    )


def _clean_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_optional_float(value: object) -> tuple[float | None, bool]:
    if value is None:
        return None, True
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value), True
    text = str(value).strip()
    if not text:
        return None, True
    try:
        return float(text), True
    except ValueError:
        return None, False


def _parse_required_float(value: object) -> tuple[float | None, bool]:
    parsed, ok = _parse_optional_float(value)
    if not ok:
        return None, False
    if parsed is None:
        return None, False
    return parsed, True


def _parse_optional_non_negative_float(value: object) -> tuple[float | None, bool]:
    parsed, ok = _parse_optional_float(value)
    if not ok:
        return None, False
    if parsed is not None and parsed < 0:
        return None, False
    return parsed, True


def _parse_optional_date(value: object) -> tuple[date | None, bool]:
    """Optional yyyymmdd date (mirrors validate.xlsx.ehs's identical helper).

    pdtable's ``read_csv`` never returns a ``datetime.date`` for a plain text
    cell (unlike openpyxl), so unlike EHS's counterpart this only ever needs
    to accept a bare 'yyyymmdd' int/string -- kept as a (value, ok) pair for
    consistency with this module's other ``_parse_optional_*`` helpers.

    A whole-number ``float`` (e.g. ``20250601.0``) is also accepted: pdtable
    infers a float dtype for this column when every populated cell looks
    numeric, so a value like 20250601 round-trips as a float, not an int/str.
    """

    if value is None:
        return None, True
    if isinstance(value, datetime):
        return value.date(), True
    if isinstance(value, date):
        return value, True
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    if not text:
        return None, True
    if re.fullmatch(r"\d{8}", text):
        try:
            return datetime.strptime(text, "%Y%m%d").date(), True
        except ValueError:
            return None, False
    return None, False


def _validate_cluster_details(
    rows: list[dict[str, object]],
    source_file: str,
    *,
    known_survey_phase_codes: Collection[str],
) -> tuple[list[ValidatedClusterDetails], list[RejectedRow]]:
    validated: list[ValidatedClusterDetails] = []
    rejections: list[RejectedRow] = []
    group = "cluster_details"

    for row in rows:
        row_number = int(row.get("_row_number", 0))  # type: ignore[arg-type]

        cluster_name = _clean_str(row.get("cluster_name"))
        if not cluster_name:
            rejections.append(
                _reject(
                    source_file, group, row_number, "required, was blank/missing", "cluster_name"
                )
            )
            continue

        survey_phase_code = _clean_str(row.get("site_investigation_reference"))
        if not survey_phase_code:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    "required, was blank/missing",
                    "site_investigation_reference",
                )
            )
            continue
        if survey_phase_code not in known_survey_phase_codes:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"{survey_phase_code!r} is not a known reference.survey_phase code "
                    f"(known: {sorted(known_survey_phase_codes)})",
                    "site_investigation_reference",
                )
            )
            continue

        eastings_raw = row.get("eastings")
        eastings_m, easting_ok = _parse_required_float(eastings_raw)
        if not easting_ok:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"required and must be numeric, got {eastings_raw!r}",
                    "eastings",
                )
            )
            continue

        northings_raw = row.get("northings")
        northings_m, northing_ok = _parse_required_float(northings_raw)
        if not northing_ok:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"required and must be numeric, got {northings_raw!r}",
                    "northings",
                )
            )
            continue

        ground_level_m, ground_ok = _parse_optional_float(row.get("ground_level"))
        if not ground_ok:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"if present, must be numeric, got {row.get('ground_level')!r}",
                    "ground_level",
                )
            )
            continue

        water_level_m, water_ok = _parse_optional_float(row.get("water_level"))
        if not water_ok:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"if present, must be numeric, got {row.get('water_level')!r}",
                    "water_level",
                )
            )
            continue

        validated.append(
            ValidatedClusterDetails(
                row_number=row_number,
                cluster_name=cluster_name,
                survey_phase_code=survey_phase_code,
                eastings_m=eastings_m,  # type: ignore[arg-type]
                northings_m=northings_m,  # type: ignore[arg-type]
                ground_level_m=ground_level_m,
                water_level_m=water_level_m,
                comments=_clean_str(row.get("comments")),
            )
        )

    return validated, rejections


def _validate_exploratory_hole_details(
    rows: list[dict[str, object]],
    source_file: str,
    *,
    known_hole_type_codes: Collection[str],
    known_hole_status_codes: Collection[str],
    known_terminal_hole_status_codes: Collection[str],
    known_termination_reason_codes: Collection[str],
) -> tuple[list[ValidatedExploratoryHole], list[RejectedRow]]:
    """Validate one **exploratory_hole_details block's rows.

    Notes:
    - ``hole_purpose`` is informational only (see the mappings module) --
      read from the row but never validated or stored.
    - ``site_investigation_reference`` picklist membership check is NOT
      performed here; the load stage does the actual
      ``geotech.site_investigation`` resolve-only lookup and raises
      LoadError for a missing target.
    - ``hole_status`` MUST be a terminal status (see mappings.pdtable.
      exploratory_hole.HOLE_STATUS_MUST_BE_TERMINAL) -- unlike EHS, a blank
      cell is NOT defaulted to 'SCHEDULED', it is rejected as required.
    """

    validated: list[ValidatedExploratoryHole] = []
    rejections: list[RejectedRow] = []
    group = "exploratory_hole_details"

    for row in rows:
        row_number = int(row.get("_row_number", 0))  # type: ignore[arg-type]

        contractor_hole_name = _clean_str(row.get("contractor_hole_name"))
        if not contractor_hole_name:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    "required, was blank/missing",
                    "contractor_hole_name",
                )
            )
            continue

        site_investigation_reference = _clean_str(row.get("site_investigation_reference"))
        if not site_investigation_reference:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    "required, was blank/missing",
                    "site_investigation_reference",
                )
            )
            continue

        hole_type = _clean_str(row.get("hole_type"))
        if not hole_type:
            rejections.append(
                _reject(
                    source_file, group, row_number, "required, was blank/missing", "hole_type"
                )
            )
            continue
        if hole_type not in known_hole_type_codes:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"{hole_type!r} is not a known reference.hole_type code "
                    f"(known: {sorted(known_hole_type_codes)})",
                    "hole_type",
                )
            )
            continue

        # OPTIONAL (2026-07-20): a blank value validates as None -- the load
        # stage leaves all three of layout_asset_id/asset_location_id/
        # cluster_location_id NULL, producing a genuinely STANDALONE hole
        # (see mappings.pdtable.exploratory_hole.ASSET_OR_CLUSTER_RESOLUTION).
        asset_or_cluster_name = _clean_str(row.get("asset_or_cluster_name"))

        hole_number = _clean_str(row.get("hole_number"))
        leg_label = _clean_str(row.get("jacket_leg_label"))
        bumpover_label = _clean_str(row.get("bumpover_label"))

        if leg_label is not None and not _LEG_LABEL_RE.match(leg_label):
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    (
                        f"{leg_label!r} must match ^[A-Za-z0-9]+$ (alphanumerics only) "
                        "if present"
                    ),
                    "jacket_leg_label",
                )
            )
            continue

        if bumpover_label is not None and not _BUMPOVER_LABEL_RE.match(bumpover_label):
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"{bumpover_label!r} must match ^[a-z]$ (single lowercase letter) if present",
                    "bumpover_label",
                )
            )
            continue

        parent_hole_name = _clean_str(row.get("bumpover_parent_hole"))

        # Both-or-neither: a bumpover_label without a parent hole name (or
        # vice versa) is a source-data inconsistency (mirrors validate.xlsx.
        # ehs's identical rule).
        if (bumpover_label is None) != (parent_hole_name is None):
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    "'bumpover_label' and 'bumpover_parent_hole' must be both present "
                    f"or both blank, found bumpover_label={bumpover_label!r}, "
                    f"parent_hole_name={parent_hole_name!r}",
                    "bumpover_label",
                )
            )
            continue

        # Self-reference: a hole cannot bump over itself.
        if parent_hole_name is not None and parent_hole_name == contractor_hole_name:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"'bumpover_parent_hole' cannot name the row's own "
                    f"contractor_hole_name {contractor_hole_name!r}",
                    "bumpover_parent_hole",
                )
            )
            continue

        # hole_status: required, and must be a TERMINAL status -- see
        # mappings.pdtable.exploratory_hole.HOLE_STATUS_MUST_BE_TERMINAL.
        hole_status_code = _clean_str(row.get("hole_status"))
        if not hole_status_code:
            rejections.append(
                _reject(
                    source_file, group, row_number, "required, was blank/missing", "hole_status"
                )
            )
            continue
        if hole_status_code not in known_hole_status_codes:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"{hole_status_code!r} is not a known reference.hole_status code "
                    f"(known: {sorted(known_hole_status_codes)})",
                    "hole_status",
                )
            )
            continue
        if hole_status_code not in known_terminal_hole_status_codes:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"{hole_status_code!r} is not a terminal status (known terminal: "
                    f"{sorted(known_terminal_hole_status_codes)}) -- this file must only "
                    "ever carry the campaign's final, QAQC'd snapshot; a non-terminal "
                    "status means the EHS re-issue cycle for this hole is not yet "
                    "finished (see HOLE_STATUS_MUST_BE_TERMINAL)",
                    "hole_status",
                )
            )
            continue

        target_depth_m, target_depth_ok = _parse_optional_non_negative_float(
            row.get("target_depth")
        )
        if not target_depth_ok:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"optional numeric value must be >= 0 if present, got {row.get('target_depth')!r}",
                    "target_depth",
                )
            )
            continue

        final_depth_m, final_depth_ok = _parse_optional_non_negative_float(row.get("final_depth"))
        if not final_depth_ok:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"optional numeric value must be >= 0 if present, got {row.get('final_depth')!r}",
                    "final_depth",
                )
            )
            continue

        termination_reason_code = _clean_str(row.get("termination_reason"))
        if (
            termination_reason_code is not None
            and termination_reason_code not in known_termination_reason_codes
        ):
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"{termination_reason_code!r} is not a known "
                    "reference.termination_reason code "
                    f"(known: {sorted(known_termination_reason_codes)})",
                    "termination_reason",
                )
            )
            continue

        start_date, start_date_ok = _parse_optional_date(row.get("start_date"))
        if not start_date_ok:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"unparseable date, expected 'yyyymmdd', got {row.get('start_date')!r}",
                    "start_date",
                )
            )
            continue

        end_date, end_date_ok = _parse_optional_date(row.get("end_date"))
        if not end_date_ok:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"unparseable date, expected 'yyyymmdd', got {row.get('end_date')!r}",
                    "end_date",
                )
            )
            continue

        if start_date is not None and end_date is not None and end_date < start_date:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"end_date {end_date} must not be before start_date {start_date}",
                    "end_date",
                )
            )
            continue

        # actual_easting/actual_northing: optional, both-or-neither -- mirrors
        # validate.xlsx.ehs's identical check for its own "As-installed
        # easting/northing" columns, and mappings.pdtable.exploratory_hole.
        # ACTUAL_POSITION_PRECEDENCE's file-value-wins-else-echo rule (the
        # load stage decides the fallback; this stage only enforces shape).
        actual_easting_m, actual_easting_ok = _parse_optional_float(row.get("actual_easting"))
        if not actual_easting_ok:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"optional numeric value, found {row.get('actual_easting')!r}",
                    "actual_easting",
                )
            )
            continue

        actual_northing_m, actual_northing_ok = _parse_optional_float(row.get("actual_northing"))
        if not actual_northing_ok:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"optional numeric value, found {row.get('actual_northing')!r}",
                    "actual_northing",
                )
            )
            continue

        if (actual_easting_m is None) != (actual_northing_m is None):
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    "actual_easting and actual_northing must be both present or "
                    f"both blank, found actual_easting={row.get('actual_easting')!r}, "
                    f"actual_northing={row.get('actual_northing')!r}",
                    "actual_easting",
                )
            )
            continue

        seabed_level_m, seabed_level_ok = _parse_optional_float(row.get("seabed_level"))
        if not seabed_level_ok:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"optional numeric value, found {row.get('seabed_level')!r}",
                    "seabed_level",
                )
            )
            continue

        validated.append(
            ValidatedExploratoryHole(
                row_number=row_number,
                contractor_hole_name=contractor_hole_name,
                site_investigation_reference=site_investigation_reference,
                hole_type_code=hole_type,
                hole_number=hole_number,
                leg_label=leg_label,
                bumpover_label=bumpover_label,
                parent_hole_name=parent_hole_name,
                hole_status_code=hole_status_code,
                target_depth_m=target_depth_m,
                final_depth_m=final_depth_m,
                termination_reason_code=termination_reason_code,
                start_date=start_date,
                end_date=end_date,
                actual_easting_m=actual_easting_m,
                actual_northing_m=actual_northing_m,
                seabed_level_m=seabed_level_m,
                comments=_clean_str(row.get("comments")),
                asset_or_cluster_name=asset_or_cluster_name,
            )
        )

    return validated, rejections


def validate_pdtable_exploratory_hole_document(
    document: PdtableExploratoryHoleDocument,
    *,
    known_survey_phase_codes: Collection[str],
    known_hole_type_codes: Collection[str],
    known_hole_status_codes: Collection[str],
    known_terminal_hole_status_codes: Collection[str],
    known_termination_reason_codes: Collection[str],
) -> tuple[ValidatedPdtableExploratoryHoleDocument, list[RejectedRow]]:
    """Validate a parsed ``PdtableExploratoryHoleDocument`` end to end.

    Args:
        known_terminal_hole_status_codes: the subset of
            known_hole_status_codes for which reference.hole_status.
            is_terminal = true -- every row's hole_status must be a member of
            THIS set, not merely of known_hole_status_codes (see
            mappings.pdtable.exploratory_hole.HOLE_STATUS_MUST_BE_TERMINAL).

    Returns:
        A (validated_document, rejected_rows) pair. There is no whole-file
        rejection -- individual rows are independently droppable.
    """

    source_file = str(document.source_path)
    rejections: list[RejectedRow] = []

    cluster_details, cluster_rejections = _validate_cluster_details(
        document.cluster_details_rows,
        source_file,
        known_survey_phase_codes=known_survey_phase_codes,
    )
    rejections.extend(cluster_rejections)

    exploratory_holes, hole_rejections = _validate_exploratory_hole_details(
        document.exploratory_hole_details_rows,
        source_file,
        known_hole_type_codes=known_hole_type_codes,
        known_hole_status_codes=known_hole_status_codes,
        known_terminal_hole_status_codes=known_terminal_hole_status_codes,
        known_termination_reason_codes=known_termination_reason_codes,
    )
    rejections.extend(hole_rejections)

    return (
        ValidatedPdtableExploratoryHoleDocument(
            source_path=source_file,
            project_code=document.project_code,
            cluster_details=cluster_details,
            exploratory_holes=exploratory_holes,
        ),
        rejections,
    )
