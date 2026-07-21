"""pdtable project-input CSV -> geoCore mapping (Phase 6, Task 1).

Source: a pdtable ("StarTable" -- https://pypi.org/project/pdtable/)
semicolon-delimited .csv, the first file a data engineer prepares when
creating a new asset project (see geodb/sample-data/pdtable/input_project_HEW.csv).
This is the earliest document in a project's overall lifecycle -- earlier
than EHS, AGS4, or CPT-JSON, and is the single source of truth for
project.project/location.development_area, which every other format only ever
resolves against (see PROJECT_AUTHORITY/DEVELOPMENT_AREA_AUTHORITY below).

- `pdtable.store.BlockType` has five real members: METADATA, DIRECTIVE,
  TEMPLATE_ROW, TABLE, BLANK. The file's rows 1-6 (free-text file-metadata:
  "File description:", "File purpose:", ...) parse as one BlockType.METADATA
  block -- never loaded, human documentation only.
- `***revision_history` parses as BlockType.DIRECTIVE (a `Directive` object)
  -- pdtable's own term for a single-row key/value config block, NOT a
  multi-row table (confirmed: this file's directive has exactly one data
  row). Structural/provenance only, never loaded as a geoCore row.
- `::<table>` / `:<column>` comment and picklist lines parse as
  BlockType.TEMPLATE_ROW -- raw, unstructured rows (pdtable's plain
  `read_csv` doesn't build a rich object for these). Documentation only,
  never loaded -- see UNMAPPED_TEMPLATE_ROWS below for the genuinely useful
  cross-check they enable.
- `**<table_name>` parses as BlockType.TABLE -- a `pdtable.Table` object with
  `.name` (str) and `.df` (a pandas DataFrame, already type-coerced per the
  unit row -- numeric columns like `capacity`/`number_of_turbines`/`index`/
  `eastings`/`northings`/`EPSG_code` arrive as float64 with NaN for blank
  cells, e.g. HEW01's `number_of_turbines` is NaN for its literal "-" cell).
- **Confirmed, non-obvious finding:** the second row under `**<table_name>`
  is pdtable's own **destination** tag (`Table.metadata.destinations: set[str]`)
  -- StarTable's mechanism for declaring which downstream consumer(s) a
  table block is intended for. This OptiSoil-derived template **repurposes it
  as the per-table project_code** for the three project-scoped blocks, rather
  than a literal consumer-system name. `development_area`/`project` always
  use the literal `{'all'}` destination (one file-wide table, not project-scoped)
  -- see DEVELOPMENT_AREA_AUTHORITY/PROJECT_AUTHORITY below.
- **Confirmed data-quality gap in the fixture itself:** the raw file is valid
  UTF-8 (decodes cleanly, `data.decode("utf-8")` raises no error) -- this is
  NOT an encoding-detection problem. However, every non-ASCII character in
  "Hesselø"/"Ørsted"-derived text (`area_name`, `project_name`, the
  QA-level narrative text) has *already* been replaced, byte-for-byte, by
  U+FFFD (the Unicode replacement character) upstream of this repo -- a
  real, pre-existing lossy round-trip, not something this pipeline can
  recover. See MOJIBAKE_CHECK below: semantic validation must reject any
  text field containing U+FFFD rather than silently loading a corrupted
  name into `project.project`/`location.development_area`.

No I/O, no pdtable import, no database access here -- pure data declarations,
mirroring every other format's mappings module.
"""

from __future__ import annotations

from ..types import FieldMapping, SourceFormat

# --- Confirmed real pdtable block/table names (see module docstring) ------
DIRECTIVE_REVISION_HISTORY = "revision_history"
TABLE_DEVELOPMENT_AREA = "development_area"
TABLE_PROJECT = "project"
TABLE_COORDINATE_REFERENCE_SYSTEM = "coordinate_reference_system"
TABLE_ARRAY_AREA_COORDINATES = "array_area_coordinates"
TABLE_EXPORT_CABLE_ROUTE_COORDINATES = "export_cable_route_coordinates"

# The literal destination value used by file-wide (non-project-scoped) tables.
FILE_WIDE_DESTINATION = "all"

# reference.boundary_type codes these two per-project boundary tables map to
# (geodb/sql/050__reference_boundary_enums.sql) -- fixed, not read from the file.
ARRAY_AREA_BOUNDARY_TYPE_CODE = "ARRAY"
EXPORT_CABLE_ROUTE_BOUNDARY_TYPE_CODE = "ECR"

# --- Authority / resolution rules (design decisions, confirmed 2026-07-13) -

DEVELOPMENT_AREA_AUTHORITY = (
    "UNLIKE every other geodb_etl format, this pipeline CREATES and OWNS "
    "location.development_area rows -- an authoritative upsert keyed on "
    "area_code, not a resolve-or-reject lookup. This file is 'the single source "
    "of truth for all project-related metadata', and is the earliest document in a "
    "project's lifecycle (before EHS's SITE_INVESTIGATION_AUTHORITY get-"
    "or-create, before any AGS/CPT-JSON delivery). Re-running the same file "
    "after a legitimate edit (e.g. a corrected area_name) UPDATES the "
    "existing row to match the file, the same discipline "
    "065__location_boundary_hew.sql's vertex ON CONFLICT ... DO UPDATE "
    "already uses."
)

PROJECT_AUTHORITY = (
    "UNLIKE mappings.ags.proj.PROJECT_RESOLUTION (project_code is operator-"
    "supplied, AGS never creates a project) and EHS's identical rule, this "
    "pipeline CREATES and OWNS project.project rows -- same authoritative-"
    "upsert discipline as DEVELOPMENT_AREA_AUTHORITY, keyed on project_code. "
    "AGS4/CPT-JSON/EHS_XLSX are unaffected: they still only resolve against "
    "whatever project.project row THIS pipeline already created. area_id is "
    "resolved via the file's own development_area block (area_code), "
    "never an operator-supplied argument -- see the project.area_id "
    "FieldMapping below."
)

COORDINATE_SYSTEM_RESOLUTION = (
    "reference.coordinate_system is get-or-create, keyed on "
    "(epsg_code_horizontal, horizontal_unit, epsg_code_vertical, "
    "vertical_unit) -- the same natural key "
    "050__reference_boundary_enums.sql's unique indexes already enforce. "
    "spheroid/datum/map_projection/coordinate_system_type have NO column "
    "home in reference.coordinate_system -- a genuine schema gap, flagged "
    "here (UNMAPPED_COORDINATE_REFERENCE_SYSTEM_FIELDS below), not force-"
    "mapped, same discipline as the AGS LOCA_EPSG gap. The file's "
    "coordinate_reference_system destination tag (e.g. 'HEW01') identifies "
    "which project.project row this CRS applies to -- it is NOT a "
    "reference.coordinate_system column itself."
)

BOUNDARY_AUTHORITY = (
    "location.boundary rows are get-or-create, keyed on a synthesized "
    "boundary_name -- f'{project_code} array area' for "
    "array_area_coordinates (boundary_type_code='ARRAY'), f'{project_code} "
    "export cable route' for export_cable_route_coordinates "
    "(boundary_type_code='ECR') -- matching "
    "065__location_boundary_hew.sql's own naming convention exactly, so "
    "this ETL path and that hand-written seed file are interchangeable/"
    "idempotent against each other. location.boundary_vertex rows are "
    "upserted keyed on (boundary_id, vertex_no) -- vertex_no is the file's "
    "0-based 'index' column, +1 (boundary_vertex.vertex_no CHECKs > 0; the "
    "file's index starts at 0) -- ON CONFLICT (boundary_id, vertex_no) DO "
    "UPDATE, identical shape to 065's vertex upsert. location."
    "project_boundary is get-or-create (project_id, boundary_id), never "
    "deleted by a re-run (a project's boundary set only grows across "
    "re-runs of this pipeline, e.g. if a later file adds a new boundary "
    "type this table doesn't yet cover)."
)

BOUNDARY_CLOSURE_PRE_CHECK = (
    "Reproduces location.validate_boundary_closure()'s three checks as a "
    "semantic-validation failure (RejectedRow), so a malformed ring never "
    "reaches the DB trigger as a raw, unexplained exception: (1) at least 4 "
    "vertices, (2) vertex_no contiguous from 1 (i.e. the file's 'index' "
    "column contiguous from 0), (3) first vertex's (eastings, northings) "
    "== last vertex's (eastings, northings) -- a closed ring. Applies to "
    "both array_area_coordinates and export_cable_route_coordinates."
)

LAYOUT_AUTHORITY_NOTE = (
    "Removed 2026-07-15 (superseded design): this file's **project table "
    "previously carried a 'layout_code' field used to promote one of a "
    "project's project.layout rows to layout_status_code='CUR' at load "
    "time. That mechanism has been dropped -- it duplicated (and could "
    "directly contradict) the layout_status_code already carried by "
    "input_layout.csv's own **layout_details block, which is the single "
    "authoritative source of a project's current layout status (see "
    "mappings.pdtable.layout.LAYOUT_STATUS_AUTHORITY). A brand-new "
    "project.project row still gets its 'L000' placeholder "
    "project.layout row for free (project.create_default_layout(), "
    "status 'PLC', see 105__project_default_layout.sql) -- this pipeline "
    "does nothing further to it. When a real input_layout.csv is later "
    "loaded for that project, its **layout_details rows (including "
    "whichever one is marked 'CUR') supersede the placeholder entirely; "
    "there is no longer any project-level field driving that transition."
)

MOJIBAKE_CHECK = (
    "A confirmed, pre-existing data-quality defect in the fixture (see "
    "module docstring): every non-ASCII character in area_name/project_name "
    "has already been replaced by U+FFFD upstream of this repo -- the file "
    "itself is valid UTF-8, this is not an encoding-detection problem. "
    "Semantic validation rejects (RejectedRow) any text field containing "
    "U+FFFD rather than silently loading a corrupted name into "
    "project.project/location.development_area -- per this repo's data-"
    "integrity standard, corrupted source data is never silently accepted."
)

# --- development_area -------------------------------------------------------

DEVELOPMENT_AREA_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="area_code",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="location.development_area",
        target_column="area_code",
        notes="Natural key for the authoritative upsert. See DEVELOPMENT_AREA_AUTHORITY.",
    ),
    FieldMapping(
        source_field="area_name",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="location.development_area",
        target_column="area_name",
        notes="Subject to MOJIBAKE_CHECK -- rejected if it contains U+FFFD.",
    ),
    FieldMapping(
        source_field="region_code",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="location.development_area",
        target_column="region_code",
        notes="Resolved via lookup into reference.region; unmapped value is a RejectedRow.",
    ),
    FieldMapping(
        source_field="sea_area_code",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="location.development_area",
        target_column="sea_area_code",
        required=False,
        notes=(
            "Resolved via lookup into reference.sea_area; column is nullable "
            "on location.development_area (see 030__location_development_area.sql), "
            "but an unmapped non-blank value is still a RejectedRow."
        ),
    ),
    FieldMapping(
        source_field="country_code",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="location.development_area",
        target_column="country_code",
        notes="Resolved via lookup into reference.country; unmapped value is a RejectedRow.",
    ),
]

# --- project -----------------------------------------------------------------

PROJECT_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field=None,
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.project",
        target_column="area_id",
        required=True,
        notes=(
            "Resolved via lookup against location.development_area.area_code "
            "-- this file's own development_area block, not an operator-"
            "supplied argument (contrast every AGS/EHS project_code lookup, "
            "which IS operator-supplied). Every project_code in this file's "
            "project table is assumed to belong to the single area_code the "
            "same file's development_area block declares."
        ),
    ),
    FieldMapping(
        source_field="project_code",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.project",
        target_column="project_code",
        notes="Natural key for the authoritative upsert. See PROJECT_AUTHORITY.",
    ),
    FieldMapping(
        source_field="project_name",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.project",
        target_column="project_name",
        notes="Subject to MOJIBAKE_CHECK -- rejected if it contains U+FFFD.",
    ),
    FieldMapping(
        source_field="capacity",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.project",
        target_column="capacity_mw",
        required=False,
        notes="Unit row confirmed 'MW' -- matches capacity_mw, no conversion.",
    ),
    FieldMapping(
        source_field="number_of_turbines",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.project",
        target_column="number_of_turbines",
        required=False,
        notes="pdtable already coerces the file's literal '-' placeholder to NaN/None.",
    ),
    FieldMapping(
        source_field="foundation_type",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.project",
        target_column="foundation_type_code",
        required=False,
        notes="Resolved via lookup into reference.foundation_type; unmapped value rejected.",
    ),
    FieldMapping(
        source_field="status",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.project",
        target_column="project_status_code",
        required=False,
        notes="Resolved via lookup into reference.project_status; unmapped value rejected.",
    ),
]

# --- coordinate_reference_system (per project_code destination) -------------

COORDINATE_REFERENCE_SYSTEM_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="EPSG_code",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="reference.coordinate_system",
        target_column="epsg_code_horizontal",
        notes="See COORDINATE_SYSTEM_RESOLUTION.",
    ),
    FieldMapping(
        source_field="horizontal_unit",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="reference.coordinate_system",
        target_column="horizontal_unit",
    ),
    FieldMapping(
        source_field="EPSG_code_vertical",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="reference.coordinate_system",
        target_column="epsg_code_vertical",
        required=False,
        notes="reference.coordinate_system CHECKs vertical fields both-or-neither NULL.",
    ),
    FieldMapping(
        source_field="vertical_unit",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="reference.coordinate_system",
        target_column="vertical_unit",
        required=False,
    ),
]

UNMAPPED_COORDINATE_REFERENCE_SYSTEM_FIELDS: list[str] = [
    "coordinate_system_type",
    "spheroid",
    "datum",
    "map_projection",
    "vertical_datum",
]

# --- array_area_coordinates / export_cable_route_coordinates ---------------
# Both tables share an identical column shape; only boundary_type_code and
# the synthesized boundary_name differ -- see BOUNDARY_AUTHORITY.

BOUNDARY_VERTEX_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="index",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="location.boundary_vertex",
        target_column="vertex_no",
        notes="File's 0-based index + 1 -- boundary_vertex.vertex_no CHECKs > 0.",
    ),
    FieldMapping(
        source_field="eastings",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="location.boundary_vertex",
        target_column="easting_m",
    ),
    FieldMapping(
        source_field="northings",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="location.boundary_vertex",
        target_column="northing_m",
    ),
]

# --- Out of scope (documented, never loaded) --------------------------------

OUT_OF_SCOPE = (
    "File-metadata lines (rows 1-6, BlockType.METADATA): human documentation "
    "only. ***revision_history (BlockType.DIRECTIVE): structural/provenance "
    "only. Every ::<table>/:<column> comment and .choice picklist line "
    "(BlockType.TEMPLATE_ROW): human documentation only -- though several "
    "of the picklists (region_code, sea_area_code, foundation_type, status) are "
    "a genuinely useful, independent cross-check against this schema's own "
    "seeded reference.* tables (confirmed to match on inspection, not diffed "
    "programmatically here -- a possible future doc-sync test, not implemented)."
)









