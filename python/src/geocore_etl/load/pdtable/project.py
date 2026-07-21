"""Load stage for the pdtable project-input source format (input_project.csv).

Moved here from the top-level `geodb_etl/load.py` per
`tasks/plan/codebase-structure-cleanup.md` -- the load stage now follows the
same `{xlsx,pdtable}/...` format-subdirectory pattern already used by
`parse/`, `validate/`, `transform/`, and `cli/`. Only the file's *location*
changed in this increment, not its behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...transform.pdtable import (
    BoundaryRecord,
    BoundaryVertexRecord,
    DevelopmentAreaRecord,
    PdtableProjectTransformResult,
    ProjectRecord,
)
from .. import LoadError


@dataclass(frozen=True)
class PdtableProjectLoadResult:
    area_id: int
    project_ids: dict[str, int]
    boundary_ids: dict[str, int]


def load_pdtable_project_transform_result(
    result: PdtableProjectTransformResult, connection: Any
) -> PdtableProjectLoadResult:
    """Load a PdtableProjectTransformResult into geoCore within one transaction.

    UNLIKE load_ehs_transform_result (and every AGS/CPT-JSON load path), this
    is an AUTHORITATIVE UPSERT of location.development_area/project.project --
    per mappings.pdtable.project.DEVELOPMENT_AREA_AUTHORITY/PROJECT_AUTHORITY
    (confirmed by the user 2026-07-13): re-running the same file after a
    legitimate edit updates the existing row to match the file, rather than
    resolving-or-rejecting on mismatch.

    Args:
        result: The output of
            geodb_etl.transform.pdtable.transform_pdtable_project_document.
        connection: A psycopg.Connection (or, in tests, anything satisfying
            the same cursor()/commit()/rollback() protocol).

    Returns:
        The upserted area_id, one project_id per loaded project (keyed by
        project_code), and one boundary_id per loaded boundary (keyed by
        boundary_name).

    Raises:
        LoadError: a boundary references a project_code not present in this
            file's own project block, or has no matching
            coordinate_reference_system block in this file. Any other
            failure rolls back the transaction and re-raises unchanged.
    """

    cursor = connection.cursor()
    try:
        area_id = _upsert_development_area(cursor, result.development_area)

        project_ids: dict[str, int] = {
            project.project_code: _upsert_project(cursor, area_id, project)
            for project in result.projects
        }

        coordinate_system_id_by_project: dict[str, int] = {
            cs.project_code: _get_or_create_coordinate_system(
                cursor,
                cs.epsg_code_horizontal,
                cs.horizontal_unit,
                cs.epsg_code_vertical,
                cs.vertical_unit,
            )
            for cs in result.coordinate_systems
        }

        boundary_ids: dict[str, int] = {}
        for boundary in result.boundaries:
            project_id = project_ids.get(boundary.project_code)
            if project_id is None:
                raise LoadError(
                    f"boundary {boundary.boundary_name!r} references project_code "
                    f"{boundary.project_code!r}, which was not loaded from this file's "
                    "own project block."
                )
            coordinate_system_id = coordinate_system_id_by_project.get(boundary.project_code)
            if coordinate_system_id is None:
                raise LoadError(
                    f"boundary {boundary.boundary_name!r} for project_code "
                    f"{boundary.project_code!r} has no matching "
                    "coordinate_reference_system block in this file."
                )
            boundary_id = _upsert_boundary(cursor, boundary, coordinate_system_id)
            _sync_boundary_vertices(cursor, boundary_id, boundary.vertices)
            _link_project_boundary(cursor, project_id, boundary_id)
            boundary_ids[boundary.boundary_name] = boundary_id
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

    return PdtableProjectLoadResult(
        area_id=area_id, project_ids=project_ids, boundary_ids=boundary_ids
    )


def _upsert_development_area(cursor: Any, record: DevelopmentAreaRecord) -> int:
    cursor.execute(
        """
        INSERT INTO location.development_area
            (area_code, area_name, region_code, sea_area_code, country_code)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (area_code) DO UPDATE SET
            area_name = EXCLUDED.area_name,
            region_code = EXCLUDED.region_code,
            sea_area_code = EXCLUDED.sea_area_code,
            country_code = EXCLUDED.country_code
        RETURNING area_id
        """,
        (
            record.area_code,
            record.area_name,
            record.region_code,
            record.sea_area_code,
            record.country_code,
        ),
    )
    return cursor.fetchone()[0]


def _upsert_project(cursor: Any, area_id: int, record: ProjectRecord) -> int:
    cursor.execute(
        """
        INSERT INTO project.project
            (area_id, project_code, project_name, capacity_mw, number_of_turbines,
             foundation_type_code, project_status_code)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (project_code) DO UPDATE SET
            area_id = EXCLUDED.area_id,
            project_name = EXCLUDED.project_name,
            capacity_mw = EXCLUDED.capacity_mw,
            number_of_turbines = EXCLUDED.number_of_turbines,
            foundation_type_code = EXCLUDED.foundation_type_code,
            project_status_code = EXCLUDED.project_status_code
        RETURNING project_id
        """,
        (
            area_id,
            record.project_code,
            record.project_name,
            record.capacity_mw,
            record.number_of_turbines,
            record.foundation_type_code,
            record.project_status_code,
        ),
    )
    return cursor.fetchone()[0]


def _get_or_create_coordinate_system(
    cursor: Any,
    epsg_code_horizontal: int,
    horizontal_unit: str,
    epsg_code_vertical: int | None,
    vertical_unit: str | None,
) -> int:
    """Get-or-create, never update -- reference.coordinate_system's natural key
    (epsg_code_horizontal, horizontal_unit, epsg_code_vertical, vertical_unit)
    IS the data; nothing else on the row is ever mutated. A plain SELECT-then-
    INSERT (not an INSERT ... ON CONFLICT) because the table's uniqueness is
    enforced via two partial indexes (with/without a vertical component -- see
    050__reference_boundary_enums.sql), which ON CONFLICT can't target with a
    single arbiter across both cases.
    """

    if epsg_code_vertical is None:
        cursor.execute(
            "SELECT coordinate_system_id FROM reference.coordinate_system "
            "WHERE epsg_code_horizontal = %s AND horizontal_unit = %s "
            "AND epsg_code_vertical IS NULL AND vertical_unit IS NULL",
            (epsg_code_horizontal, horizontal_unit),
        )
    else:
        cursor.execute(
            "SELECT coordinate_system_id FROM reference.coordinate_system "
            "WHERE epsg_code_horizontal = %s AND horizontal_unit = %s "
            "AND epsg_code_vertical = %s AND vertical_unit = %s",
            (epsg_code_horizontal, horizontal_unit, epsg_code_vertical, vertical_unit),
        )
    row = cursor.fetchone()
    if row is not None:
        return row[0]

    cursor.execute(
        "INSERT INTO reference.coordinate_system "
        "(epsg_code_horizontal, horizontal_unit, epsg_code_vertical, vertical_unit) "
        "VALUES (%s, %s, %s, %s) RETURNING coordinate_system_id",
        (epsg_code_horizontal, horizontal_unit, epsg_code_vertical, vertical_unit),
    )
    return cursor.fetchone()[0]


def _upsert_boundary(cursor: Any, boundary: BoundaryRecord, coordinate_system_id: int) -> int:
    cursor.execute(
        """
        INSERT INTO location.boundary (boundary_name, boundary_type_code, coordinate_system_id)
        VALUES (%s, %s, %s)
        ON CONFLICT (boundary_name) DO UPDATE SET
            boundary_type_code = EXCLUDED.boundary_type_code,
            coordinate_system_id = EXCLUDED.coordinate_system_id
        RETURNING boundary_id
        """,
        (boundary.boundary_name, boundary.boundary_type_code, coordinate_system_id),
    )
    return cursor.fetchone()[0]


def _sync_boundary_vertices(
    cursor: Any, boundary_id: int, vertices: list[BoundaryVertexRecord]
) -> None:
    """Upsert every vertex, then DELETE any vertex_no beyond the new count --
    the authoritative-upsert discipline (decision #3) means a corrected,
    *shorter* ring must not leave stale trailing vertices behind, unlike
    065__location_boundary_hew.sql's one-time seed (which never deletes).
    """

    for vertex in vertices:
        cursor.execute(
            """
            INSERT INTO location.boundary_vertex (boundary_id, vertex_no, easting_m, northing_m)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (boundary_id, vertex_no) DO UPDATE SET
                easting_m = EXCLUDED.easting_m,
                northing_m = EXCLUDED.northing_m
            """,
            (boundary_id, vertex.vertex_no, vertex.easting_m, vertex.northing_m),
        )

    max_vertex_no = max((v.vertex_no for v in vertices), default=0)
    cursor.execute(
        "DELETE FROM location.boundary_vertex WHERE boundary_id = %s AND vertex_no > %s",
        (boundary_id, max_vertex_no),
    )


def _link_project_boundary(cursor: Any, project_id: int, boundary_id: int) -> None:
    cursor.execute(
        """
        INSERT INTO location.project_boundary (project_id, boundary_id)
        VALUES (%s, %s)
        ON CONFLICT DO NOTHING
        """,
        (project_id, boundary_id),
    )

