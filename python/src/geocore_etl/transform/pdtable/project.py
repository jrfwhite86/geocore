"""Transform stage for pdtable project-input (Phase 6, Tasks 4-5; implemented
in Phase 6b, see tasks/plan/phase-6b-pdtable-cli-completion.md).

Pure functions -- no I/O, no database access. Shapes here ARE the real,
load.py-verified contract (not throwaway guesses): every field name, order,
and nullability matches how geodb_etl.load's
load_pdtable_project_transform_result()/_upsert_*()/_get_or_create_*()
helpers already consume them, and how the pre-existing test suite
(test_load_pdtable.py, test_transform_pdtable_project.py) already constructs
them -- both were grounded against directly rather than re-guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...mappings.pdtable.project import (
    ARRAY_AREA_BOUNDARY_TYPE_CODE,
    EXPORT_CABLE_ROUTE_BOUNDARY_TYPE_CODE,
)
from ...validate.pdtable.project import ValidatedBoundaryVertex, ValidatedPdtableProjectDocument


@dataclass(frozen=True)
class DevelopmentAreaRecord:
    """location.development_area upsert shape (see load._upsert_development_area)."""

    area_code: str
    area_name: str
    region_code: str
    sea_area_code: str
    country_code: str


@dataclass(frozen=True)
class ProjectRecord:
    """project.project upsert shape (see load._upsert_project).

    area_id is NOT a field here -- load._upsert_project receives it as a
    separate parameter (resolved once via DevelopmentAreaRecord's own
    upsert), so it is never read off this record.
    """

    project_code: str
    project_name: str | None = None
    capacity_mw: float | None = None
    number_of_turbines: int | None = None
    foundation_type_code: str | None = None
    project_status_code: str | None = None


@dataclass(frozen=True)
class CoordinateSystemRecord:
    """reference.coordinate_system get-or-create shape (see
    load._get_or_create_coordinate_system).

    epsg_code_vertical/vertical_unit are Optional -- mirrors
    _get_or_create_coordinate_system's own (int | None, str | None)
    parameters and the two-partial-index design
    (050__reference_boundary_enums.sql) that supports a horizontal-only
    coordinate system with no vertical component at all.
    """

    project_code: str
    epsg_code_horizontal: int
    horizontal_unit: str
    epsg_code_vertical: int | None
    vertical_unit: str | None


@dataclass(frozen=True)
class BoundaryVertexRecord:
    """location.boundary_vertex upsert shape (see load._sync_boundary_vertices).

    No boundary_id field -- _sync_boundary_vertices receives boundary_id as
    a separate parameter (resolved once per boundary via its own upsert) and
    never reads it off the vertex itself. Field order matches the
    established positional-construction convention already used throughout
    the test suite: BoundaryVertexRecord(vertex_no, easting_m, northing_m).
    """

    vertex_no: int
    easting_m: float
    northing_m: float


@dataclass(frozen=True)
class BoundaryRecord:
    """location.boundary upsert shape (see load._upsert_boundary)."""

    project_code: str
    boundary_type_code: str
    boundary_name: str
    vertices: list[BoundaryVertexRecord]


@dataclass(frozen=True)
class PdtableProjectTransformResult:
    """Full transform result for one input_project_{area_code}.csv (see
    load.load_pdtable_project_transform_result).

    coordinate_systems/boundaries default to empty -- a file need not
    declare either block (matches the pre-existing test suite's own
    partial constructions, e.g. development_area/projects only).
    """

    development_area: DevelopmentAreaRecord
    projects: list[ProjectRecord]
    coordinate_systems: list[CoordinateSystemRecord] = field(default_factory=list)
    boundaries: list[BoundaryRecord] = field(default_factory=list)


def transform_pdtable_project_document(
    document: ValidatedPdtableProjectDocument,
) -> PdtableProjectTransformResult:
    """Map a ValidatedPdtableProjectDocument onto load-ready records.

    Pure mapping only -- boundary_name/boundary_type_code are synthesized per
    mappings.pdtable.project.BOUNDARY_AUTHORITY (f"{project_code} array area" /
    f"{project_code} export cable route"), everything else is a straight
    field-for-field copy.
    """

    development_area = DevelopmentAreaRecord(
        area_code=document.development_area.area_code,
        area_name=document.development_area.area_name,
        region_code=document.development_area.region_code,
        sea_area_code=document.development_area.sea_area_code,
        country_code=document.development_area.country_code,
    )

    projects = [
        ProjectRecord(
            project_code=project.project_code,
            project_name=project.project_name,
            capacity_mw=project.capacity_mw,
            number_of_turbines=project.number_of_turbines,
            foundation_type_code=project.foundation_type_code,
            project_status_code=project.project_status_code,
        )
        for project in document.projects
    ]

    coordinate_systems = [
        CoordinateSystemRecord(
            project_code=project_code,
            epsg_code_horizontal=crs.epsg_code_horizontal,
            horizontal_unit=crs.horizontal_unit,
            epsg_code_vertical=crs.epsg_code_vertical,
            vertical_unit=crs.vertical_unit,
        )
        for project_code, crs in document.coordinate_reference_systems.items()
    ]

    boundaries = [
        _boundary_record(
            project_code,
            ARRAY_AREA_BOUNDARY_TYPE_CODE,
            f"{project_code} array area",
            vertices,
        )
        for project_code, vertices in document.array_area_boundaries.items()
    ] + [
        _boundary_record(
            project_code,
            EXPORT_CABLE_ROUTE_BOUNDARY_TYPE_CODE,
            f"{project_code} export cable route",
            vertices,
        )
        for project_code, vertices in document.export_cable_route_boundaries.items()
    ]

    return PdtableProjectTransformResult(
        development_area=development_area,
        projects=projects,
        coordinate_systems=coordinate_systems,
        boundaries=boundaries,
    )


def _boundary_record(
    project_code: str,
    boundary_type_code: str,
    boundary_name: str,
    vertices: list[ValidatedBoundaryVertex],
) -> BoundaryRecord:
    return BoundaryRecord(
        project_code=project_code,
        boundary_type_code=boundary_type_code,
        boundary_name=boundary_name,
        vertices=[
            BoundaryVertexRecord(
                vertex_no=vertex.vertex_no,
                easting_m=vertex.easting_m,
                northing_m=vertex.northing_m,
            )
            for vertex in vertices
        ],
    )

