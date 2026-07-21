"""Load stage for pdtable layout-input (Phase 10b rewrite; multi-project
support added -- see mappings.pdtable.layout.MULTI_PROJECT_DESTINATION_CONVENTION).

Loads a ``PdtableLayoutTransformResult`` into geoCore within one transaction
-- the same ``cursor()/commit()/rollback()`` protocol as
``load.pdtable.project`` and ``load.xlsx.ehs``. Resolves every FK this
format needs (project_id, coordinate_system_id, layout_id, asset_location_id)
via lookup against already-seeded/already-loaded data, raising LoadError
(never a raw IntegrityError) for anything unresolvable.

Authority (see mappings.pdtable.layout.LAYOUT_CATALOGUE_AUTHORITY): this
pipeline CREATES-AND-OWNS project.layout catalogue entries (via each
**layout_details block) AND location.asset_location / project.layout_asset
positions (via each **layout_configuration block) -- for every project the
file covers.

A single file may cover multiple projects (e.g. input_layout_HEW.csv has
both HEW01 and HEW02) -- every record carries its own project_code, and
project_id/coordinate_system_id are resolved and cached per project_code
the first time each is actually needed (see below), rather than once
file-wide.

Order within the transaction:

1. Upsert every ``layout_catalogue`` entry, resolving/caching project_id
   per project_code the first time it is seen -> build a
   ``layout_id_by_project_and_code`` cache keyed by (project_code,
   layout_code). ``layout_status_code`` is authoritative-upserted here on
   every run, same as every other layout_details field -- see
   mappings.pdtable.layout.LAYOUT_STATUS_AUTHORITY (this pipeline is the
   sole write authority for layout status; input_project.csv no longer
   carries any layout-status-controlling field).
2. Pass 1: upsert every non-JLEG asset_location (parent_location_id always
   NULL). Pass 2: upsert every JLEG asset_location, resolving
   parent_location_id from pass 1's in-memory map for the SAME project_code
   (falling back to a DB lookup for an asset already stored from an earlier
   run).
3. For every asset row: resolve layout_id from
   ``layout_id_by_project_and_code`` (LoadError if missing -- indicates a
   validate/parse bug), lazily resolve/cache that project's
   coordinate_system_id the first time it is needed (a project whose only
   layout_details rows are placeholders with no layout_configuration block
   never needs input_project.csv's array-area boundary to already exist),
   then upsert project.layout_asset keyed on (asset_location_id, layout_id).

The ``_PENDING_LAYOUT_CODE = "L000"`` constant is retained here as a
historical documentation reference only -- in the new file shape every
asset row lives inside a block whose destination IS the (project_code,
layout_code) pair, so there is no runtime blank-layout fallback path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ...transform.pdtable.layout import (
    AssetDetailsRecord,
    LayoutCatalogueRecord,
    PdtableLayoutTransformResult,
)
from .. import LoadError

# Historical reference only -- see module docstring. No runtime code path
# reads this any more; kept so future readers understand why the old
# "blank layout_reference" fallback disappeared.
_PENDING_LAYOUT_CODE = "L000"


@dataclass(frozen=True)
class PdtableLayoutLoadResult:
    """Result of loading one input_layout_{area_code}.csv (may span multiple
    projects -- see mappings.pdtable.layout.MULTI_PROJECT_DESTINATION_CONVENTION).

    ``project_ids`` (project_code -> project_id) replaces the old
    single-project ``project_id`` field now that one file may cover
    multiple projects.

    ``layout_ids``/``asset_location_ids``/``layout_asset_ids_by_layout_code``
    are keyed by ``(project_code, layout_code)`` /
    ``(project_code, internal_reference)`` tuples (rather than bare
    layout_code/internal_reference) so that two different projects' own
    "L001" or reused asset_name never collide.
    ``layout_asset_ids_by_layout_code[(project_code, layout_code)][asset_name]``
    yields the project.layout_asset PK for that (project, layout, asset)
    triple, resolving the "same asset_name appears in multiple layouts"
    ambiguity without a second DB round-trip -- exposed for a future
    pipeline (e.g. exploratory-hole loading) that needs to look up the
    currently-``CUR`` layout's layout_asset_id for a given project.
    """

    project_ids: dict[str, int]
    layout_ids: dict[tuple[str, str], int]
    asset_location_ids: dict[tuple[str, str], int]
    layout_asset_ids_by_layout_code: dict[tuple[str, str], dict[str, int]] = field(
        default_factory=dict
    )


def load_pdtable_layout_transform_result(
    result: PdtableLayoutTransformResult, connection: Any
) -> PdtableLayoutLoadResult:
    """Load a ``PdtableLayoutTransformResult`` into geoCore in one transaction.

    Args:
        result: The output of
            ``geodb_etl.transform.pdtable.transform_pdtable_layout_document``.
        connection: A psycopg.Connection (or, in tests, anything satisfying
            the same cursor()/commit()/rollback() protocol).

    Returns:
        See ``PdtableLayoutLoadResult``.

    Raises:
        LoadError: a record's project_code doesn't match any project.project
            row; a project with at least one asset position row has no
            'ARRAY'-type boundary yet (input_project.csv not loaded first,
            see COORDINATE_SYSTEM_RESOLUTION); a JLEG row's parent_asset_name
            doesn't resolve to any asset_location row in the same project
            (see PARENT_LOCATION_RESOLUTION); or a layout_configuration
            block references a (project_code, layout_code) pair that has no
            matching entry in the same file's layout_details blocks (see
            LAYOUT_RESOLUTION). Any other failure rolls back the
            transaction and re-raises unchanged.
    """

    cursor = connection.cursor()
    try:
        project_ids: dict[str, int] = {}
        coordinate_system_ids: dict[str, int] = {}

        def get_project_id(project_code: str) -> int:
            if project_code not in project_ids:
                project_ids[project_code] = _resolve_project_id(cursor, project_code)
            return project_ids[project_code]

        def get_coordinate_system_id(project_code: str) -> int:
            if project_code not in coordinate_system_ids:
                coordinate_system_ids[project_code] = _resolve_coordinate_system_id(
                    cursor, get_project_id(project_code)
                )
            return coordinate_system_ids[project_code]

        layout_id_by_project_and_code: dict[tuple[str, str], int] = {}
        for entry in result.layout_catalogue:
            project_id = get_project_id(entry.project_code)
            layout_id_by_project_and_code[(entry.project_code, entry.layout_code)] = (
                _upsert_layout_catalogue(cursor, project_id, entry)
            )

        asset_location_ids: dict[tuple[str, str], int] = {}
        # Per-project view of the same map, kept in lockstep -- needed so
        # JLEG parent resolution (below) never matches an identically-named
        # asset in a DIFFERENT project.
        asset_location_ids_by_project: dict[str, dict[str, int]] = {}
        layout_asset_ids_by_layout_code: dict[tuple[str, str], dict[str, int]] = {}

        non_jleg_details = [
            d for d in result.asset_details if d.location.asset_type_code != "JLEG"
        ]
        jleg_details = [d for d in result.asset_details if d.location.asset_type_code == "JLEG"]

        # Pass 1: every non-JLEG asset location -- parent_location_id NULL.
        for detail in non_jleg_details:
            project_id = get_project_id(detail.project_code)
            asset_location_id = _upsert_asset_location(
                cursor, project_id, detail, parent_location_id=None
            )
            internal_reference = detail.location.internal_reference
            asset_location_ids[(detail.project_code, internal_reference)] = asset_location_id
            asset_location_ids_by_project.setdefault(detail.project_code, {})[
                internal_reference
            ] = asset_location_id

        # Pass 2: JLEG rows, resolving parent_location_id from pass 1's map
        # for the SAME project (falling back to a DB lookup for a parent
        # that already existed).
        for detail in jleg_details:
            project_id = get_project_id(detail.project_code)
            parent_name = detail.location.parent_asset_name
            parent_location_id = _resolve_asset_location_id(
                cursor,
                project_id,
                parent_name,
                asset_location_ids_by_project.setdefault(detail.project_code, {}),
            )
            if parent_location_id is None:
                raise LoadError(
                    f"layout_configuration row {detail.location.internal_reference!r} "
                    f"(project {detail.project_code!r}) is asset_type 'JLEG' but its "
                    f"parent_asset_name {parent_name!r} does not match any "
                    "asset_location row in this file or any existing "
                    "location.asset_location row for this project."
                )
            asset_location_id = _upsert_asset_location(
                cursor, project_id, detail, parent_location_id=parent_location_id
            )
            internal_reference = detail.location.internal_reference
            asset_location_ids[(detail.project_code, internal_reference)] = asset_location_id
            asset_location_ids_by_project[detail.project_code][
                internal_reference
            ] = asset_location_id

        # project.layout_asset -- one per asset_details row.
        for detail in result.asset_details:
            internal_reference = detail.location.internal_reference
            layout_key = (detail.project_code, detail.layout_code)
            if layout_key not in layout_id_by_project_and_code:
                raise LoadError(
                    f"layout_configuration block for project {detail.project_code!r}, "
                    f"layout_code {detail.layout_code!r} references a layout not "
                    "present in this file's layout_details blocks -- every "
                    "layout_configuration destination must have a matching "
                    "layout_details entry for the same project in the same file."
                )
            layout_id = layout_id_by_project_and_code[layout_key]
            coordinate_system_id = get_coordinate_system_id(detail.project_code)
            asset_location_id = asset_location_ids[(detail.project_code, internal_reference)]
            layout_asset_id = _upsert_layout_asset(
                cursor,
                asset_location_id,
                layout_id,
                coordinate_system_id,
                detail.position,
            )
            layout_asset_ids_by_layout_code.setdefault(layout_key, {})[
                internal_reference
            ] = layout_asset_id
    except Exception:
        connection.rollback()
        raise
    else:
        try:
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    finally:
        cursor.close()

    return PdtableLayoutLoadResult(
        project_ids=project_ids,
        layout_ids=layout_id_by_project_and_code,
        asset_location_ids=asset_location_ids,
        layout_asset_ids_by_layout_code=layout_asset_ids_by_layout_code,
    )


def _resolve_project_id(cursor: Any, project_code: str) -> int:
    cursor.execute(
        "SELECT project_id FROM project.project WHERE project_code = %s",
        (project_code,),
    )
    row = cursor.fetchone()
    if row is None:
        raise LoadError(
            f"input_layout.csv's project_code {project_code!r} does not match any "
            "project.project row -- this pipeline never creates a project, only loads "
            "into an existing one (input_project.csv must be loaded first)."
        )
    return row[0]


def _resolve_coordinate_system_id(cursor: Any, project_id: int) -> int:
    """See mappings.pdtable.layout.COORDINATE_SYSTEM_RESOLUTION."""

    cursor.execute(
        """
        SELECT b.coordinate_system_id
        FROM location.project_boundary pb
        JOIN location.boundary b ON b.boundary_id = pb.boundary_id
        WHERE pb.project_id = %s AND b.boundary_type_code = 'ARRAY'
        """,
        (project_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise LoadError(
            f"project_id {project_id} has no 'ARRAY'-type location.boundary yet -- "
            "input_project.csv must be loaded for this project before input_layout.csv can be."
        )
    return row[0]


def _upsert_layout_catalogue(
    cursor: Any, project_id: int, entry: LayoutCatalogueRecord
) -> int:
    """Upsert one project.layout row.

    Per mappings.pdtable.layout.LAYOUT_STATUS_AUTHORITY, this pipeline is the
    sole write authority for layout_status_code -- every column, including
    layout_status_code, is authoritative-upserted on every run (re-running
    this pipeline after a genuine status edit in the source file, e.g.
    promoting a new revision to 'CUR', updates the existing row to match).
    """

    cursor.execute(
        """
        INSERT INTO project.layout
            (project_id, layout_code, layout_name, layout_status_code,
             effective_date, description)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (project_id, layout_code) DO UPDATE SET
            layout_name = EXCLUDED.layout_name,
            layout_status_code = EXCLUDED.layout_status_code,
            effective_date = EXCLUDED.effective_date,
            description = EXCLUDED.description
        RETURNING layout_id
        """,
        (
            project_id,
            entry.layout_code,
            entry.layout_name,
            entry.layout_status_code,
            _date_param(entry.effective_date),
            entry.description,
        ),
    )
    return cursor.fetchone()[0]


def _date_param(value: date | None) -> date | None:
    """psycopg accepts a ``datetime.date`` directly -- kept as a thin helper
    so a future change (e.g. serialising to an ISO string for a different
    driver) has exactly one place to change.
    """

    return value


def _resolve_asset_location_id(
    cursor: Any, project_id: int, internal_reference: str, known: dict[str, int]
) -> int | None:
    """Resolve an asset_location_id by internal_reference -- first against
    the in-memory map already built for this project in this load, falling
    back to a DB lookup (the parent already existed from an earlier run of
    this file and wasn't repeated in this one). Returns None if neither
    resolves.
    """

    if internal_reference in known:
        return known[internal_reference]

    cursor.execute(
        "SELECT asset_location_id FROM location.asset_location "
        "WHERE project_id = %s AND internal_reference = %s",
        (project_id, internal_reference),
    )
    row = cursor.fetchone()
    return row[0] if row is not None else None


def _upsert_asset_location(
    cursor: Any,
    project_id: int,
    detail: AssetDetailsRecord,
    *,
    parent_location_id: int | None,
) -> int:
    location = detail.location
    cursor.execute(
        """
        INSERT INTO location.asset_location
            (project_id, parent_location_id, internal_reference,
             asset_type_code, leg_label)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (project_id, internal_reference) DO UPDATE SET
            parent_location_id = EXCLUDED.parent_location_id,
            asset_type_code = EXCLUDED.asset_type_code,
            leg_label = EXCLUDED.leg_label
        RETURNING asset_location_id
        """,
        (
            project_id,
            parent_location_id,
            location.internal_reference,
            location.asset_type_code,
            location.leg_label,
        ),
    )
    return cursor.fetchone()[0]


def _upsert_layout_asset(
    cursor: Any,
    asset_location_id: int,
    layout_id: int,
    coordinate_system_id: int,
    position: Any,
) -> int:
    cursor.execute(
        """
        INSERT INTO project.layout_asset
            (asset_location_id, layout_id, rdspp_code,
             eastings_m, northings_m, seabed_level_m,
             water_level_m, foundation_type_code, coordinate_system_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (asset_location_id, layout_id) DO UPDATE SET
            rdspp_code = EXCLUDED.rdspp_code,
            eastings_m = EXCLUDED.eastings_m,
            northings_m = EXCLUDED.northings_m,
            seabed_level_m = EXCLUDED.seabed_level_m,
            water_level_m = EXCLUDED.water_level_m,
            foundation_type_code = EXCLUDED.foundation_type_code,
            coordinate_system_id = EXCLUDED.coordinate_system_id
        RETURNING layout_asset_id
        """,
        (
            asset_location_id,
            layout_id,
            position.rdspp_code,
            position.eastings_m,
            position.northings_m,
            position.seabed_level_m,
            position.water_level,
            position.foundation_type_code,
            coordinate_system_id,
        ),
    )
    return cursor.fetchone()[0]
