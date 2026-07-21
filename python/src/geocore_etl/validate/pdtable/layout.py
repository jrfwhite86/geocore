"""pdtable CSV validate stage for layout-input (Phase 10b rewrite).

Plain dataclasses + hand-written checks, not Pydantic (same "simplicity
first" choice validate.pdtable.project already made). Never raises for bad
data -- every failure becomes a RejectedRow, per this repo's data-integrity
standard. Individual rows are independently droppable -- the rest of the
file still validates around them.

Two blocks validated here, across every project the file covers (see
mappings.pdtable.layout.MULTI_PROJECT_DESTINATION_CONVENTION):

- Each ``**layout_details`` block (one per project_code) ->
  ``ValidatedLayoutCatalogueEntry`` list. Sources ``project.layout``
  catalogue rows. Every entry carries its owning ``project_code`` (passed in
  from the block's destination), so downstream stages still know which
  project each catalogue row belongs to after block boundaries are
  flattened.
- Each ``**layout_configuration`` block (one per (project_code,
  layout_code) pair) -> ``ValidatedAssetDetails`` list. Every entry carries
  its owning ``project_code`` and ``layout_code`` (passed in from the
  block's destination, NOT read from a per-row column -- neither column
  exists post-Phase-10b), so the load stage still knows which project and
  layout each asset row belongs to after block-boundaries are flattened.

Cluster-purpose asset_type values (REC/IAC/ECR/OTHER) are REJECTED with an
explicit cross-file message -- input_layout.csv now carries physical assets
only (ANS/WTG/OSS/OCS/RCS/JLEG/MET); cluster locations belong to
input_exploratory_hole.csv's cluster_details block (a different pipeline).
See mappings.pdtable.layout.ASSET_TYPE_SCOPE.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, datetime

from ...mappings.types import RejectedRow
from ...parse.pdtable import PdtableLayoutDocument

# Physical assets loaded by this pipeline -- location.asset_location is
# populated exclusively from these types (see geodb/sql/080__location_asset_location.sql).
ASSET_TYPE_CODES_FOR_ASSET_PURPOSE = frozenset(
    {"ANS", "WTG", "OSS", "OCS", "RCS", "JLEG", "MET"}
)

# foundation_type's file picklist uses 'NA' for "Not applicable" -- resolves
# to NULL rather than being validated against known_foundation_type_codes
# (see mappings.pdtable.layout.FOUNDATION_TYPE_MAPPING).
FOUNDATION_TYPE_NOT_APPLICABLE_CODE = "NA"


@dataclass(frozen=True)
class ValidatedLayoutCatalogueEntry:
    """One validated layout_details row -> project.layout upsert input.

    ``project_code`` is the owning **layout_details block's own destination
    tag, copied verbatim onto every validated row from that block (never
    read from a per-row column) -- see mappings.pdtable.layout.
    MULTI_PROJECT_DESTINATION_CONVENTION.
    """

    row_number: int
    project_code: str
    layout_code: str
    layout_name: str | None
    layout_status_code: str
    effective_date: date | None
    description: str | None


@dataclass(frozen=True)
class ValidatedAssetDetails:
    """One validated layout_configuration row.

    ``project_code``/``layout_code`` are the block's own destination tags,
    not per-row columns -- passed in to ``_validate_layout_configuration``
    and copied verbatim onto every validated row so the load stage still
    knows which project and layout to attach the position to after block
    boundaries are flattened. See mappings.pdtable.layout.
    MULTI_PROJECT_DESTINATION_CONVENTION.
    """

    row_number: int
    project_code: str
    layout_code: str
    asset_name: str
    asset_type_code: str
    eastings_m: float
    northings_m: float
    seabed_level_m: float | None
    water_level: float | None
    foundation_type_code: str | None
    leg_label: str | None
    parent_asset_name: str | None
    rdspp_code: str | None


@dataclass(frozen=True)
class ValidatedPdtableLayoutDocument:
    """The fully validated contents of one input_layout_{area_code}.csv.

    May cover multiple projects -- layout_catalogue/asset_details are flat
    lists spanning every project in the file, each row carrying its own
    ``project_code`` (see ValidatedLayoutCatalogueEntry/ValidatedAssetDetails).
    """

    source_path: str
    layout_catalogue: list[ValidatedLayoutCatalogueEntry]
    asset_details: list[ValidatedAssetDetails]


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
    """Returns (parsed_value, ok). ok is False only for a non-blank value that
    can't be parsed as a number (blank/None is always ok -- these are
    optional fields).
    """

    if value is None:
        return None, True
    if isinstance(value, (int, float)):
        return float(value), True
    text = str(value).strip()
    if not text:
        return None, True
    try:
        return float(text), True
    except ValueError:
        return None, False


def _parse_optional_yyyymmdd(value: object) -> tuple[date | None, bool]:
    """Parse an optional yyyymmdd value (int like 20260710, or its string
    form). Returns (parsed_value, ok). ok is False only for a non-blank value
    that can't be interpreted as a valid yyyymmdd date.
    """

    if value is None:
        return None, True
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        text = str(int(value))
    else:
        text = str(value).strip()
    if not text:
        return None, True
    if len(text) != 8 or not text.isdigit():
        return None, False
    try:
        return datetime.strptime(text, "%Y%m%d").date(), True
    except ValueError:
        return None, False


def _catalogue_group_name(project_code: str) -> str:
    """Origin-block label for RejectedRow.group -- disambiguates by
    project_code now that a file may cover multiple projects (see
    mappings.pdtable.layout.MULTI_PROJECT_DESTINATION_CONVENTION)."""

    return f"layout_details[{project_code}]"


def _configuration_group_name(project_code: str, layout_code: str) -> str:
    """Origin-block label for RejectedRow.group. Kept close to the old
    ``asset_details`` group-name convention while disambiguating the origin
    block by its (project_code, layout_code) pair."""

    return f"layout_configuration[{project_code}:{layout_code}]"


def _validate_layout_catalogue(
    rows: list[dict[str, object]],
    source_file: str,
    project_code: str,
    *,
    known_layout_status_codes: Collection[str],
) -> tuple[list[ValidatedLayoutCatalogueEntry], list[RejectedRow]]:
    """Validate one **layout_details block's rows.

    ``project_code`` is the block's own destination tag, copied verbatim
    onto every validated row (never read from a per-row column).

    Checks:
    - layout_code: required (natural key for project.layout upsert)
    - layout_status_code: required, must be in ``known_layout_status_codes``
      (per mappings.pdtable.layout.LAYOUT_STATUS_AUTHORITY, written only on
      first INSERT of the row)
    - effective_date: optional, yyyymmdd shape if present
    - layout_name / description: optional free text
    """

    validated: list[ValidatedLayoutCatalogueEntry] = []
    rejections: list[RejectedRow] = []
    group = _catalogue_group_name(project_code)

    for row in rows:
        row_number = int(row.get("_row_number", 0))  # type: ignore[arg-type]

        layout_code = _clean_str(row.get("layout_code"))
        if not layout_code:
            rejections.append(
                _reject(
                    source_file, group, row_number, "required, was blank/missing", "layout_code"
                )
            )
            continue

        layout_status_code = _clean_str(row.get("layout_status_code"))
        if not layout_status_code:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    "required, was blank/missing",
                    "layout_status_code",
                )
            )
            continue
        if layout_status_code not in known_layout_status_codes:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"{layout_status_code!r} is not a known reference.layout_status code "
                    f"(known: {sorted(known_layout_status_codes)})",
                    "layout_status_code",
                )
            )
            continue

        effective_date_raw = row.get("effective_date")
        effective_date, effective_ok = _parse_optional_yyyymmdd(effective_date_raw)
        if not effective_ok:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"if present, must be a yyyymmdd date, got {effective_date_raw!r}",
                    "effective_date",
                )
            )
            continue

        validated.append(
            ValidatedLayoutCatalogueEntry(
                row_number=row_number,
                project_code=project_code,
                layout_code=layout_code,
                layout_name=_clean_str(row.get("layout_name")),
                layout_status_code=layout_status_code,
                effective_date=effective_date,
                description=_clean_str(row.get("description")),
            )
        )

    return validated, rejections


def _validate_layout_configuration(
    rows: list[dict[str, object]],
    source_file: str,
    project_code: str,
    layout_code: str,
    *,
    known_asset_type_codes: Collection[str],
    known_foundation_type_codes: Collection[str],
) -> tuple[list[ValidatedAssetDetails], list[RejectedRow]]:
    """Validate one ``**layout_configuration`` block's rows.

    ``project_code``/``layout_code`` are the block's own destination tags,
    copied verbatim onto every validated row (never read from a per-row
    column -- there isn't one).

    Cluster-purpose asset_type values (REC/IAC/ECR/OTHER, or any value not in
    ASSET_TYPE_CODES_FOR_ASSET_PURPOSE) are REJECTED with an explicit
    cross-file message rather than silently reclassified -- see
    mappings.pdtable.layout.ASSET_TYPE_SCOPE.
    """

    validated: list[ValidatedAssetDetails] = []
    rejections: list[RejectedRow] = []
    group = _configuration_group_name(project_code, layout_code)

    for row in rows:
        row_number = int(row.get("_row_number", 0))  # type: ignore[arg-type]

        asset_name = _clean_str(row.get("asset_name"))
        if not asset_name:
            rejections.append(
                _reject(source_file, group, row_number, "required, was blank/missing", "asset_name")
            )
            continue

        asset_type = _clean_str(row.get("asset_type"))
        if not asset_type:
            rejections.append(
                _reject(source_file, group, row_number, "required, was blank/missing", "asset_type")
            )
            continue
        if asset_type not in known_asset_type_codes:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"{asset_type!r} is not a known reference.asset_type code "
                    f"(known: {sorted(known_asset_type_codes)})",
                    "asset_type",
                )
            )
            continue
        if asset_type not in ASSET_TYPE_CODES_FOR_ASSET_PURPOSE:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    (
                        f"cluster-purpose asset type {asset_type!r} does not belong in "
                        "input_layout.csv's layout_configuration block -- cluster "
                        "locations belong in input_exploratory_hole.csv's "
                        "cluster_details block instead."
                    ),
                    "asset_type",
                )
            )
            continue
        asset_type_code = asset_type

        # Required: eastings
        easting_raw = row.get("eastings")
        easting_m, easting_ok = _parse_optional_float(easting_raw)
        if not easting_ok or easting_m is None:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"required and must be numeric, got {easting_raw!r}",
                    "eastings",
                )
            )
            continue

        # Required: northings
        northing_raw = row.get("northings")
        northing_m, northing_ok = _parse_optional_float(northing_raw)
        if not northing_ok or northing_m is None:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"required and must be numeric, got {northing_raw!r}",
                    "northings",
                )
            )
            continue

        seabed_level_m, seabed_ok = _parse_optional_float(row.get("seabed_level"))
        if not seabed_ok:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"if present, must be numeric, got {row.get('seabed_level')!r}",
                    "seabed_level",
                )
            )

        water_level, water_ok = _parse_optional_float(row.get("water_level"))
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

        # 'index' is the pdtable row-position column (0, 1, 2, ...) -- not a
        # meaningful business identifier, and unmapped everywhere else in the
        # ETL (see mappings.pdtable.layout.UNMAPPED_LAYOUT_CONFIGURATION_FIELDS).

        foundation_type_raw = _clean_str(row.get("foundation_type"))
        if (
            foundation_type_raw is None
            or foundation_type_raw == FOUNDATION_TYPE_NOT_APPLICABLE_CODE
        ):
            foundation_type_code = None
        elif foundation_type_raw not in known_foundation_type_codes:
            rejections.append(
                _reject(
                    source_file,
                    group,
                    row_number,
                    f"{foundation_type_raw!r} is not a known reference.foundation_type code "
                    f"(known: {sorted(known_foundation_type_codes)})",
                    "foundation_type",
                )
            )
            foundation_type_code = None
        else:
            foundation_type_code = foundation_type_raw

        leg_label = _clean_str(row.get("jacket_leg_label"))
        parent_asset_name = _clean_str(row.get("parent_asset_name"))
        rdspp_code = _clean_str(row.get("rdspp_code"))

        # location.asset_location's own CHECK constraints require both leg_label
        # and parent_location_id (resolved from parent_asset_name) whenever
        # asset_type_code is 'JLEG' -- reject early with a clear message rather
        # than a raw DB error.
        if asset_type_code == "JLEG":
            if not leg_label:
                rejections.append(
                    _reject(
                        source_file,
                        group,
                        row_number,
                        "required when asset_type is 'JLEG', was blank/missing",
                        "jacket_leg_label",
                    )
                )
            if not parent_asset_name:
                rejections.append(
                    _reject(
                        source_file,
                        group,
                        row_number,
                        "required when asset_type is 'JLEG', was blank/missing",
                        "parent_asset_name",
                    )
                )
            if not leg_label or not parent_asset_name:
                continue

        validated.append(
            ValidatedAssetDetails(
                row_number=row_number,
                project_code=project_code,
                layout_code=layout_code,
                asset_name=asset_name,
                asset_type_code=asset_type_code,
                eastings_m=easting_m,
                northings_m=northing_m,
                seabed_level_m=seabed_level_m,
                water_level=water_level,
                foundation_type_code=foundation_type_code,
                leg_label=leg_label,
                parent_asset_name=parent_asset_name,
                rdspp_code=rdspp_code,
            )
        )

    return validated, rejections


def validate_pdtable_layout_document(
    document: PdtableLayoutDocument,
    *,
    known_asset_type_codes: Collection[str],
    known_foundation_type_codes: Collection[str],
    known_layout_status_codes: Collection[str],
) -> tuple[ValidatedPdtableLayoutDocument, list[RejectedRow]]:
    """Validate a parsed ``PdtableLayoutDocument`` end to end.

    Iterates ``document.layout_details_rows_by_project`` (one
    ``**layout_details`` block per project_code) and
    ``document.layout_configuration_rows_by_project`` (a dict of dicts,
    keyed first by project_code then by layout_code), calling
    ``_validate_layout_catalogue``/``_validate_layout_configuration`` once
    per block and passing that block's project_code/layout_code in
    explicitly. Every validated row carries its own project_code (and, for
    asset rows, layout_code) field so downstream stages can still attribute
    a row to its owning project/layout after all blocks are flattened into
    two flat lists. Per-block ``RejectedRow.group`` values disambiguate the
    origin block (``"layout_details[<project_code>]"`` /
    ``"layout_configuration[<project_code>:<layout_code>]"``).

    Returns:
        A (validated_document, rejected_rows) pair. There is no whole-file
        rejection -- individual rows are independently droppable.
    """

    source_file = str(document.source_path)
    rejections: list[RejectedRow] = []

    layout_catalogue: list[ValidatedLayoutCatalogueEntry] = []
    for project_code, rows in document.layout_details_rows_by_project.items():
        block_validated, block_rejections = _validate_layout_catalogue(
            rows,
            source_file,
            project_code,
            known_layout_status_codes=known_layout_status_codes,
        )
        layout_catalogue.extend(block_validated)
        rejections.extend(block_rejections)

    asset_details: list[ValidatedAssetDetails] = []
    for project_code, rows_by_layout_code in document.layout_configuration_rows_by_project.items():
        for layout_code, rows in rows_by_layout_code.items():
            block_validated, block_rejections = _validate_layout_configuration(
                rows,
                source_file,
                project_code,
                layout_code,
                known_asset_type_codes=known_asset_type_codes,
                known_foundation_type_codes=known_foundation_type_codes,
            )
            asset_details.extend(block_validated)
            rejections.extend(block_rejections)

    return (
        ValidatedPdtableLayoutDocument(
            source_path=source_file,
            layout_catalogue=layout_catalogue,
            asset_details=asset_details,
        ),
        rejections,
    )
