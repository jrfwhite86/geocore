"""pdtable CSV validate stage for project-input (Phase 6, Task 3; implemented
in Phase 6b, see tasks/plan/phase-6b-pdtable-cli-completion.md).

Plain dataclasses + hand-written checks, not Pydantic -- same "simplicity
first" choice validate.xlsx.ehs already made (see that module's docstring);
revisit only if this module's rules outgrow it. known_region_codes/
known_sea_area_codes/known_country_codes/known_foundation_type_codes/
known_project_status_codes are deliberately caller-supplied (mirrors
known_hole_type_codes in validate.xlsx.ehs) rather than hardcoded, to avoid a
second, driftable copy of seeded reference.* data in Python. Never raises for
bad data -- every failure becomes a RejectedRow, per this repo's data-
integrity standard.

Whole-file rejection (`validated is None`) only when the development_area
block itself fails (missing area_code, or an unknown region/sea_area/country
code) -- per DEVELOPMENT_AREA_AUTHORITY, every project.area_id in this file
resolves against that one area_code, so a broken development_area makes the
whole file unloadable, not just one row (mirrors validate.xlsx.ehs's header-
failure fan-out). Individual project rows / coordinate_reference_system
blocks / boundary rings are independently droppable -- the rest of the file
still validates around them (see mappings.pdtable.project.BOUNDARY_CLOSURE_
PRE_CHECK / MOJIBAKE_CHECK for the specific rules each field is checked
against).
"""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass, field
from pathlib import Path

from ...mappings.types import RejectedRow, ValidationWarning
from ...parse.pdtable import PdtableProjectDocument

_MOJIBAKE_CHAR = "\ufffd"

# ETRS89/WGS84 UTM north zone EPSG codes -> zone number. Mirrors
# geocore_tracker.services.validation._UTM_ZONE_EPSG (tracker package) --
# used to cross-check a coordinate_reference_system block's numeric EPSG_code
# against its own free-text map_projection field (see
# _check_map_projection_zone below). A prior version of this validator
# accepted map_projection at face value with no cross-check at all (it isn't
# mapped to any reference.coordinate_system column, see
# UNMAPPED_COORDINATE_REFERENCE_SYSTEM_FIELDS in mappings.pdtable.project),
# which let internally-inconsistent CRS blocks (e.g. EPSG:25831 alongside
# "UTM Zone 32N", when 25831 is actually zone 31N) through unnoticed.
_UTM_ZONE_EPSG = {
    **{25800 + z: z for z in range(28, 38)},  # ETRS89 / UTM zone N
    **{32600 + z: z for z in range(1, 61)},  # WGS 84 / UTM zone N
}

_MAP_PROJECTION_ZONE_RE = re.compile(r"zone\s*(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class ValidatedBoundaryVertex:
    """One validated boundary ring vertex (array area or export cable route)."""

    vertex_no: int
    easting_m: float
    northing_m: float


@dataclass(frozen=True)
class ValidatedCoordinateReferenceSystem:
    """Validated coordinate_reference_system block, one per project_code.

    epsg_code_vertical/vertical_unit are Optional -- a project's CRS may
    have no vertical component at all (see
    mappings.pdtable.project.COORDINATE_SYSTEM_RESOLUTION and
    transform.pdtable.project.CoordinateSystemRecord, which this shape feeds).
    """

    epsg_code_horizontal: int
    horizontal_unit: str
    epsg_code_vertical: int | None
    vertical_unit: str | None


@dataclass(frozen=True)
class ValidatedDevelopmentArea:
    """Validated development_area block — exactly one per document."""

    area_code: str
    area_name: str
    region_code: str
    sea_area_code: str
    country_code: str


@dataclass(frozen=True)
class ValidatedProject:
    """One validated project row."""

    row_number: int
    project_code: str
    project_name: str | None
    capacity_mw: float | None
    number_of_turbines: int | None
    foundation_type_code: str
    project_status_code: str


@dataclass(frozen=True)
class ValidatedPdtableProjectDocument:
    """The fully validated contents of one input_project_{area_code}.csv.

    coordinate_reference_systems/array_area_boundaries/
    export_cable_route_boundaries are dicts keyed by project_code, mirroring
    PdtableProjectDocument's own by-project-code shape.

    warnings carries non-fatal ValidationWarning findings (see that class's
    docstring) -- e.g. a coordinate_reference_system block whose map_projection
    text disagrees with its own EPSG_code. Unlike rejections (the second
    element of validate_pdtable_project_document's return tuple), these never
    affect what's in this document -- every affected row/block is still
    present above -- they exist purely so the operator can be warned. Kept on
    this dataclass rather than added as a third tuple element so the existing
    (validated, rejections) call shape stays intact for other callers.
    """

    source_path: Path
    development_area: ValidatedDevelopmentArea
    projects: list[ValidatedProject]
    coordinate_reference_systems: dict[str, ValidatedCoordinateReferenceSystem]
    array_area_boundaries: dict[str, list[ValidatedBoundaryVertex]]
    export_cable_route_boundaries: dict[str, list[ValidatedBoundaryVertex]]
    warnings: list[ValidationWarning] = field(default_factory=list)


def _reject(
    source_path: Path,
    group: str,
    row_number: int,
    reason: str,
    field_name: str | None = None,
) -> RejectedRow:
    return RejectedRow(
        source_file=str(source_path),
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


def _check_mojibake(
    value: str | None, source_path: Path, group: str, row_number: int, field_name: str
) -> RejectedRow | None:
    if value is not None and _MOJIBAKE_CHAR in value:
        return _reject(
            source_path,
            group,
            row_number,
            f"{field_name} contains U+FFFD (the Unicode replacement character) -- "
            "a known upstream mojibake defect, never loaded as-is.",
            field_name,
        )
    return None


def _parse_optional_float(value: object) -> tuple[float | None, bool]:
    """Returns (parsed_value, ok). ok is False only for a non-blank value that
    can't be parsed as a number (blank/None is always ok -- these are optional
    fields).
    """

    if value is None:
        return None, True
    if isinstance(value, int | float):
        return float(value), True
    text = str(value).strip()
    if not text:
        return None, True
    try:
        return float(text), True
    except ValueError:
        return None, False


def _parse_optional_int(value: object) -> tuple[int | None, bool]:
    parsed, ok = _parse_optional_float(value)
    if not ok or parsed is None:
        return None, ok
    return int(parsed), True


def validate_pdtable_project_document(
    document: PdtableProjectDocument,
    *,
    known_region_codes: Collection[str],
    known_sea_area_codes: Collection[str],
    known_country_codes: Collection[str],
    known_foundation_type_codes: Collection[str],
    known_project_status_codes: Collection[str],
) -> tuple[ValidatedPdtableProjectDocument | None, list[RejectedRow]]:
    """Validate a parsed PdtableProjectDocument end to end.

    Returns:
        A (validated_document, rejected_rows) pair. See module docstring for
        the whole-file-vs-per-row rejection split. Non-fatal
        ValidationWarning findings (e.g. a coordinate_reference_system's
        EPSG_code/map_projection mismatch) are attached to
        validated_document.warnings rather than a third tuple element -- see
        ValidatedPdtableProjectDocument's docstring.
    """

    source_path = document.source_path

    development_area, rejections = _validate_development_area(
        document.development_area_rows,
        source_path,
        known_region_codes=known_region_codes,
        known_sea_area_codes=known_sea_area_codes,
        known_country_codes=known_country_codes,
    )

    if development_area is None:
        rejections.extend(
            _reject(
                source_path,
                "project",
                int(row["_row_number"]),  # type: ignore[arg-type]
                "Rejected: this file's development_area block failed validation, "
                "so project.area_id cannot resolve.",
            )
            for row in document.project_rows
        )
        return None, rejections

    valid_projects, project_rejections = _validate_projects(
        document.project_rows,
        source_path,
        area_code=development_area.area_code,
        known_foundation_type_codes=known_foundation_type_codes,
        known_project_status_codes=known_project_status_codes,
    )
    rejections.extend(project_rejections)
    valid_project_codes = {project.project_code for project in valid_projects}

    coordinate_reference_systems: dict[str, ValidatedCoordinateReferenceSystem] = {}
    warnings: list[ValidationWarning] = []
    for project_code, row in document.coordinate_reference_system_by_project.items():
        validated_crs, crs_rejections, crs_warnings = _validate_coordinate_reference_system(
            project_code, row, source_path, valid_project_codes=valid_project_codes
        )
        rejections.extend(crs_rejections)
        warnings.extend(crs_warnings)
        if validated_crs is not None:
            coordinate_reference_systems[project_code] = validated_crs

    array_area_boundaries: dict[str, list[ValidatedBoundaryVertex]] = {}
    for project_code, rows in document.array_area_coordinates_by_project.items():
        vertices, boundary_rejections = _validate_boundary_vertices(
            rows, "array_area_coordinates", source_path
        )
        rejections.extend(boundary_rejections)
        if vertices is not None:
            array_area_boundaries[project_code] = vertices

    export_cable_route_boundaries: dict[str, list[ValidatedBoundaryVertex]] = {}
    for project_code, rows in document.export_cable_route_coordinates_by_project.items():
        vertices, boundary_rejections = _validate_boundary_vertices(
            rows, "export_cable_route_coordinates", source_path
        )
        rejections.extend(boundary_rejections)
        if vertices is not None:
            export_cable_route_boundaries[project_code] = vertices

    return (
        ValidatedPdtableProjectDocument(
            source_path=source_path,
            development_area=development_area,
            projects=valid_projects,
            coordinate_reference_systems=coordinate_reference_systems,
            array_area_boundaries=array_area_boundaries,
            export_cable_route_boundaries=export_cable_route_boundaries,
            warnings=warnings,
        ),
        rejections,
    )


def _validate_development_area(
    rows: list[dict[str, object]],
    source_path: Path,
    *,
    known_region_codes: Collection[str],
    known_sea_area_codes: Collection[str],
    known_country_codes: Collection[str],
) -> tuple[ValidatedDevelopmentArea | None, list[RejectedRow]]:
    group = "development_area"
    rejections: list[RejectedRow] = []

    if not rows:
        return None, [_reject(source_path, group, 0, "development_area block is missing.")]

    row = rows[0]
    row_number = int(row.get("_row_number", 0))  # type: ignore[arg-type]

    area_code = _clean_str(row.get("area_code"))
    if not area_code:
        rejections.append(
            _reject(source_path, group, row_number, "required, was blank/missing", "area_code")
        )

    area_name = _clean_str(row.get("area_name"))
    mojibake_rejection = _check_mojibake(area_name, source_path, group, row_number, "area_name")
    if mojibake_rejection is not None:
        rejections.append(mojibake_rejection)

    region_code = _clean_str(row.get("region_code"))
    if not region_code:
        rejections.append(
            _reject(source_path, group, row_number, "required, was blank/missing", "region_code")
        )
    elif region_code not in known_region_codes:
        rejections.append(
            _reject(
                source_path,
                group,
                row_number,
                f"{region_code!r} is not a known reference.region code "
                f"(known: {sorted(known_region_codes)})",
                "region_code",
            )
        )

    sea_area_code = _clean_str(row.get("sea_area_code"))
    if sea_area_code is not None and sea_area_code not in known_sea_area_codes:
        rejections.append(
            _reject(
                source_path,
                group,
                row_number,
                f"{sea_area_code!r} is not a known reference.sea_area code "
                f"(known: {sorted(known_sea_area_codes)})",
                "sea_area_code",
            )
        )

    country_code = _clean_str(row.get("country_code"))
    if not country_code:
        rejections.append(
            _reject(source_path, group, row_number, "required, was blank/missing", "country_code")
        )
    elif country_code not in known_country_codes:
        rejections.append(
            _reject(
                source_path,
                group,
                row_number,
                f"{country_code!r} is not a known reference.country code "
                f"(known: {sorted(known_country_codes)})",
                "country_code",
            )
        )

    if rejections:
        return None, rejections

    return (
        ValidatedDevelopmentArea(
            area_code=area_code,  # type: ignore[arg-type]
            area_name=area_name or "",
            region_code=region_code,  # type: ignore[arg-type]
            sea_area_code=sea_area_code or "",
            country_code=country_code,  # type: ignore[arg-type]
        ),
        rejections,
    )


def _validate_projects(
    rows: list[dict[str, object]],
    source_path: Path,
    *,
    area_code: str,
    known_foundation_type_codes: Collection[str],
    known_project_status_codes: Collection[str],
) -> tuple[list[ValidatedProject], list[RejectedRow]]:
    group = "project"
    rejections: list[RejectedRow] = []
    candidates: list[ValidatedProject] = []

    for row in rows:
        candidate, row_rejections = _validate_project_row(
            row,
            source_path,
            area_code=area_code,
            known_foundation_type_codes=known_foundation_type_codes,
            known_project_status_codes=known_project_status_codes,
        )
        rejections.extend(row_rejections)
        if candidate is not None:
            candidates.append(candidate)

    valid_projects: list[ValidatedProject] = []
    seen_project_codes: set[str] = set()
    for candidate in candidates:
        if candidate.project_code in seen_project_codes:
            rejections.append(
                _reject(
                    source_path,
                    group,
                    candidate.row_number,
                    f"duplicate project_code {candidate.project_code!r} within this file "
                    "(unique per project.project).",
                    "project_code",
                )
            )
            continue
        seen_project_codes.add(candidate.project_code)
        valid_projects.append(candidate)

    return valid_projects, rejections


def _validate_project_row(
    row: dict[str, object],
    source_path: Path,
    *,
    area_code: str,
    known_foundation_type_codes: Collection[str],
    known_project_status_codes: Collection[str],
) -> tuple[ValidatedProject | None, list[RejectedRow]]:
    group = "project"
    row_number = int(row.get("_row_number", 0))  # type: ignore[arg-type]
    rejections: list[RejectedRow] = []

    project_code = _clean_str(row.get("project_code"))
    if not project_code:
        rejections.append(
            _reject(source_path, group, row_number, "required, was blank/missing", "project_code")
        )
    elif not project_code.startswith(area_code):
        rejections.append(
            _reject(
                source_path,
                group,
                row_number,
                f"project_code {project_code!r} does not start with this file's own "
                f"area_code {area_code!r}.",
                "project_code",
            )
        )

    project_name = _clean_str(row.get("project_name"))
    mojibake_rejection = _check_mojibake(
        project_name, source_path, group, row_number, "project_name"
    )
    if mojibake_rejection is not None:
        rejections.append(mojibake_rejection)

    capacity_mw, capacity_ok = _parse_optional_float(row.get("capacity"))
    if not capacity_ok:
        rejections.append(
            _reject(
                source_path,
                group,
                row_number,
                f"non-numeric capacity, found {row.get('capacity')!r}",
                "capacity",
            )
        )

    number_of_turbines, turbines_ok = _parse_optional_int(row.get("number_of_turbines"))
    if not turbines_ok:
        rejections.append(
            _reject(
                source_path,
                group,
                row_number,
                f"non-numeric number_of_turbines, found {row.get('number_of_turbines')!r}",
                "number_of_turbines",
            )
        )

    foundation_type_code = _clean_str(row.get("foundation_type"))
    if (
        foundation_type_code is not None
        and foundation_type_code not in known_foundation_type_codes
    ):
        rejections.append(
            _reject(
                source_path,
                group,
                row_number,
                f"{foundation_type_code!r} is not a known reference.foundation_type code "
                f"(known: {sorted(known_foundation_type_codes)})",
                "foundation_type",
            )
        )

    project_status_code = _clean_str(row.get("status"))
    if project_status_code is not None and project_status_code not in known_project_status_codes:
        rejections.append(
            _reject(
                source_path,
                group,
                row_number,
                f"{project_status_code!r} is not a known reference.project_status code "
                f"(known: {sorted(known_project_status_codes)})",
                "status",
            )
        )

    if rejections:
        return None, rejections

    return (
        ValidatedProject(
            row_number=row_number,
            project_code=project_code,  # type: ignore[arg-type]
            project_name=project_name,
            capacity_mw=capacity_mw,
            number_of_turbines=number_of_turbines,
            foundation_type_code=foundation_type_code,  # type: ignore[arg-type]
            project_status_code=project_status_code,  # type: ignore[arg-type]
        ),
        rejections,
    )


def _check_map_projection_zone(
    epsg_code: int | None,
    map_projection: object,
    source_path: Path,
    group: str,
    row_number: int,
) -> ValidationWarning | None:
    """Cross-checks a CRS block's numeric EPSG_code against its own free-text
    map_projection field (e.g. "UTM Zone 32N"), when both are UTM and the
    EPSG_code is one this module recognises (see _UTM_ZONE_EPSG). Warning
    only -- map_projection isn't mapped to any reference.coordinate_system
    column (see UNMAPPED_COORDINATE_REFERENCE_SYSTEM_FIELDS in
    mappings.pdtable.project), so a mismatch can't be "corrected" here, but it
    must not pass unnoticed either: it means the file's own CRS declaration
    is internally inconsistent.
    """

    if epsg_code is None:
        return None
    zone = _UTM_ZONE_EPSG.get(epsg_code)
    if zone is None:
        return None
    text = _clean_str(map_projection)
    if not text:
        return None
    match = _MAP_PROJECTION_ZONE_RE.search(text)
    if match is None or int(match.group(1)) == zone:
        return None
    return ValidationWarning(
        source_file=str(source_path),
        group=group,
        row_number=row_number,
        reason=(
            f"map_projection={text!r} says zone {match.group(1)} but "
            f"EPSG_code={epsg_code} is UTM zone {zone}"
        ),
        field_name="map_projection",
    )


def _validate_coordinate_reference_system(
    project_code: str,
    row: dict[str, object],
    source_path: Path,
    *,
    valid_project_codes: Collection[str],
) -> tuple[ValidatedCoordinateReferenceSystem | None, list[RejectedRow], list[ValidationWarning]]:
    group = "coordinate_reference_system"
    row_number = int(row.get("_row_number", 0))  # type: ignore[arg-type]
    rejections: list[RejectedRow] = []

    if project_code not in valid_project_codes:
        return (
            None,
            [
                _reject(
                    source_path,
                    group,
                    row_number,
                    f"destination project_code {project_code!r} does not match any valid "
                    "project_code in this file's own project block.",
                    "project_code",
                )
            ],
            [],
        )

    epsg_code_horizontal, horizontal_ok = _parse_optional_int(row.get("EPSG_code"))
    if not horizontal_ok or epsg_code_horizontal is None:
        rejections.append(
            _reject(
                source_path,
                group,
                row_number,
                f"required numeric EPSG_code, found {row.get('EPSG_code')!r}",
                "EPSG_code",
            )
        )

    horizontal_unit = _clean_str(row.get("horizontal_unit"))
    if not horizontal_unit:
        rejections.append(
            _reject(
                source_path, group, row_number, "required, was blank/missing", "horizontal_unit"
            )
        )

    epsg_code_vertical, vertical_ok = _parse_optional_int(row.get("EPSG_code_vertical"))
    if not vertical_ok:
        rejections.append(
            _reject(
                source_path,
                group,
                row_number,
                f"non-numeric EPSG_code_vertical, found {row.get('EPSG_code_vertical')!r}",
                "EPSG_code_vertical",
            )
        )

    vertical_unit = _clean_str(row.get("vertical_unit"))

    if (epsg_code_vertical is None) != (vertical_unit is None):
        rejections.append(
            _reject(
                source_path,
                group,
                row_number,
                "EPSG_code_vertical and vertical_unit must both be present or both be absent.",
                "EPSG_code_vertical",
            )
        )

    if rejections:
        return None, rejections, []

    warnings: list[ValidationWarning] = []
    zone_warning = _check_map_projection_zone(
        epsg_code_horizontal, row.get("map_projection"), source_path, group, row_number
    )
    if zone_warning is not None:
        warnings.append(zone_warning)

    return (
        ValidatedCoordinateReferenceSystem(
            epsg_code_horizontal=epsg_code_horizontal,  # type: ignore[arg-type]
            horizontal_unit=horizontal_unit,  # type: ignore[arg-type]
            epsg_code_vertical=epsg_code_vertical,
            vertical_unit=vertical_unit,
        ),
        rejections,
        warnings,
    )


def _validate_boundary_vertices(
    rows: list[dict[str, object]],
    group: str,
    source_path: Path,
) -> tuple[list[ValidatedBoundaryVertex] | None, list[RejectedRow]]:
    """Reproduces location.validate_boundary_closure()'s three checks as a
    semantic-validation failure (see mappings.pdtable.project.
    BOUNDARY_CLOSURE_PRE_CHECK): at least 4 vertices, contiguous 'index' from
    0, and a closed ring (first vertex == last vertex).
    """

    row_number = int(rows[0].get("_row_number", 0)) if rows else 0  # type: ignore[arg-type]

    if len(rows) < 4:
        return None, [
            _reject(
                source_path,
                group,
                row_number,
                f"a boundary ring must have at least 4 vertices, found {len(rows)}.",
            )
        ]

    for expected_index, row in enumerate(rows):
        if int(row.get("index", -1)) != expected_index:  # type: ignore[arg-type]
            return None, [
                _reject(
                    source_path,
                    group,
                    int(row.get("_row_number", 0)),  # type: ignore[arg-type]
                    "boundary ring vertices must have a contiguous index starting from 0 "
                    f"(expected {expected_index}, found {row.get('index')!r}).",
                    "index",
                )
            ]

    first, last = rows[0], rows[-1]
    if (float(first["eastings"]), float(first["northings"])) != (  # type: ignore[arg-type]
        float(last["eastings"]),  # type: ignore[arg-type]
        float(last["northings"]),  # type: ignore[arg-type]
    ):
        return None, [
            _reject(
                source_path,
                group,
                row_number,
                "boundary ring is not closed: first vertex's (eastings, northings) must equal "
                "the last vertex's.",
            )
        ]

    vertices = [
        ValidatedBoundaryVertex(
            vertex_no=int(row["index"]) + 1,  # type: ignore[arg-type]
            easting_m=float(row["eastings"]),  # type: ignore[arg-type]
            northing_m=float(row["northings"]),  # type: ignore[arg-type]
        )
        for row in rows
    ]
    return vertices, []


