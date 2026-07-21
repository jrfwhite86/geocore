"""pdtable layout-input CSV -> geoCore mapping (Phase 10b rewrite).

Source: a pdtable ("StarTable") semicolon-delimited .csv describing the
complete catalogue of layout revisions for a project plus, for every revision,
the position (planned, or as-built if the revision's own status says so) of
every physical asset in that layout (see
`geodb/sample-data/pdtable/input_layout_OWF.csv`).

Two block types populate this file (both are pdtable ``**<name>`` TABLE
blocks — see ``mappings.pdtable.project``'s module docstring for the general
grammar). Like ``input_project_{area_code}.csv``, a single
``input_layout_{area_code}.csv`` may cover **multiple projects** sharing the
same area_code (e.g. ``HEW01``/``HEW02`` both live in ``input_layout_HEW.csv``
— see MULTI_PROJECT_DESTINATION_CONVENTION below):

- N ``**layout_details`` blocks — one per project, whose pdtable
  *destination* tag is that project's project_code (e.g. ``HEW02``), same
  single-tag convention as ``mappings.pdtable.project``'s per-project blocks.
  One row per layout revision for that project, catalogued by ``layout_code``
  (``L000`` / ``L001`` / ``L002`` / ...). Feeds ``project.layout``.
- N ``**layout_configuration`` blocks — one per (project, layout revision)
  that has a concrete configuration. Its *destination* is TWO
  space-separated tags: the owning project_code AND the layout_code (e.g.
  a destination cell of ``HEW02 L001``) — see
  MULTI_PROJECT_DESTINATION_CONVENTION. One row per physical asset position
  in that layout revision. Feeds ``location.asset_location`` +
  ``project.layout_asset``.

Note: a placeholder ``layout_details`` row (typically ``L000``) may have NO
matching ``layout_configuration`` block — the catalogue entry exists but
carries no positions yet. (This is also why a project with only a
placeholder entry, e.g. ``HEW01`` in the real fixture, never requires
input_project.csv's array-area boundary to already exist — load only
resolves coordinate_system_id for a project lazily, the first time an actual
asset position row for it is encountered.)

Exploratory-hole and cluster-location content has been **removed** from this
file — those live in the separate ``input_exploratory_hole.csv`` file (a
different pipeline, out of scope here). Any ``asset_type`` value that would
have implied a cluster-purpose location (``REC``/``IAC``/``ECR``/``OTHER``) is
rejected outright by ``validate.pdtable.layout`` rather than silently
reclassified — see ASSET_TYPE_SCOPE below.

No I/O, no pdtable import, no database access here — pure data declarations,
mirroring ``mappings.pdtable.project``.
"""

from __future__ import annotations

from ..types import FieldMapping, SourceFormat

# --- Confirmed real pdtable table names (see module docstring) -------------
TABLE_LAYOUT_DETAILS = "layout_details"
TABLE_LAYOUT_CONFIGURATION = "layout_configuration"

# --- Authority / resolution rules (design decisions) ------------------------

LAYOUT_CATALOGUE_AUTHORITY = (
    "input_layout.csv is the sole authoritative source for project.layout "
    "catalogue rows (via its **layout_details block) AND for the physical "
    "asset positions each layout revision defines (location.asset_location + "
    "project.layout_asset, via its N **layout_configuration blocks). "
    "Re-running the same file after a legitimate edit updates the existing "
    "rows to match the file (authoritative UPSERT), consistent with the "
    "project pipeline's DEVELOPMENT_AREA_AUTHORITY / PROJECT_AUTHORITY "
    "discipline. This pipeline does NOT create or update anything in "
    "geotech.exploratory_hole or location.cluster_location -- those are "
    "owned by input_exploratory_hole.csv's pipeline (out of scope here)."
)

LAYOUT_STATUS_AUTHORITY = (
    "project.layout.layout_status_code has ONE write authority: this "
    "pipeline (input_layout.csv), via its **layout_details block. Every "
    "layout revision's status (CUR/SUP/PLC/PROP/ASB) is read directly from "
    "that block's own layout_status_code column and is authoritative-"
    "upserted on every load, same as every other layout_details field -- "
    "there is no other pipeline that may transition it. (Superseded design, "
    "removed 2026-07-15: input_project.csv's 'layout_code' field used to "
    "promote a project.layout row to 'CUR' via "
    "load.pdtable.project._promote_current_layout -- that duplicated write "
    "path directly conflicted with layout_details' own CUR/SUP assignments "
    "and has been dropped; see "
    "mappings.pdtable.project.LAYOUT_AUTHORITY_NOTE.) A brand-new "
    "project.project row gets an 'L000' / 'PLC' placeholder project.layout "
    "row for free (project.create_default_layout(), see "
    "105__project_default_layout.sql) -- when input_layout.csv is later "
    "loaded for that project, its **layout_details rows (including the "
    "placeholder's own row, if repeated, and whichever revision is marked "
    "'CUR') supersede it entirely. Concretely, the UPSERT here MUST be:\n\n"
    "    INSERT INTO project.layout (project_id, layout_code, layout_name,\n"
    "                                layout_status_code, effective_date,\n"
    "                                description)\n"
    "    VALUES (%s, %s, %s, %s, %s, %s)\n"
    "    ON CONFLICT (project_id, layout_code) DO UPDATE SET\n"
    "        layout_name = EXCLUDED.layout_name,\n"
    "        layout_status_code = EXCLUDED.layout_status_code,\n"
    "        effective_date = EXCLUDED.effective_date,\n"
    "        description = EXCLUDED.description\n\n"
    "so re-running this pipeline after a genuine status edit in the source "
    "file (e.g. promoting a new revision to 'CUR') updates the existing row "
    "to match, the same authoritative-upsert discipline every other field "
    "in this block already follows."
)

COORDINATE_SYSTEM_RESOLUTION = (
    "layout_configuration rows carry eastings/northings but "
    "no coordinate_system_id column of their own. Resolved via the "
    "project's own 'ARRAY'-type location.boundary row, which "
    "input_project.csv's array_area_coordinates block always creates "
    "(mappings.pdtable.project.BOUNDARY_AUTHORITY) --"
    "\n\n"
    "    SELECT b.coordinate_system_id\n"
    "    FROM location.project_boundary pb\n"
    "    JOIN location.boundary b ON b.boundary_id = pb.boundary_id\n"
    "    WHERE pb.project_id = %s AND b.boundary_type_code = 'ARRAY'\n"
    "\n"
    "LoadError (never a raw None/KeyError) if a project has no 'ARRAY'-type "
    "boundary yet -- i.e. input_project.csv must have been loaded for this "
    "project before input_layout.csv can be."
)

LAYOUT_RESOLUTION = (
    "In the new file shape, every layout_configuration row lives inside a "
    "specific **layout_configuration block whose *destination* tag pair IS "
    "(project_code, layout_code) -- see MULTI_PROJECT_DESTINATION_CONVENTION. "
    "There is no per-row layout_reference (or project_code) column any more; "
    "both are always known at parse time from the block's own destination. "
    "Load-stage rule: within a single file, every **layout_details block "
    "MUST be upserted before any **layout_configuration block is processed "
    "(same transaction), so that the project.layout row for every "
    "referenced (project_code, layout_code) pair already exists when its "
    "layout_configuration rows are inserted. LoadError if a "
    "layout_configuration block's (project_code, layout_code) does not "
    "match any layout_details entry from the same file -- that would "
    "indicate a parse-stage bug and the transaction is rolled back."
)

MULTI_PROJECT_DESTINATION_CONVENTION = (
    "input_layout_{area_code}.csv may cover multiple projects sharing the "
    "same area_code (e.g. input_layout_HEW.csv has both HEW01 and HEW02 -- "
    "same convention as input_project_{area_code}.csv, see "
    "mappings.pdtable.project's module docstring). This means the file may "
    "contain N **layout_details blocks (one per project_code, its own "
    "single-tag destination) whose layout_code namespaces are otherwise "
    "independent -- both HEW01 and HEW02 may legitimately define their own "
    "'L001'. A **layout_configuration block's destination can therefore no "
    "longer be the layout_code alone (which project's 'L001' would that "
    "be?). Instead it reuses pdtable's OWN multi-destination mechanism "
    "(table.metadata.destinations is natively a set, parsed by splitting "
    "the destination cell on whitespace -- see "
    "pdtable.io.parsers.blocks._get_destinations_safely_stripped): the "
    "destination cell carries TWO space-separated tags, the owning "
    "project_code and the layout_code (e.g. a cell reading 'HEW02 L001'). "
    "No custom delimiter/concatenation scheme (e.g. 'HEW02_L001') is "
    "invented -- this is pdtable's existing multi-tag destination feature, "
    "used exactly as designed. parse.pdtable.layout resolves which of the "
    "two tags is the project_code by cross-referencing the project_codes "
    "already seen from this file's own **layout_details blocks (collected "
    "in a first pass over all blocks before **layout_configuration blocks "
    "are processed in a second pass, so declaration order within the file "
    "does not matter). PdtableLayoutParseError if the destination set does "
    "not have exactly two non-file-wide tags, if neither tag matches a "
    "known project_code, or if both do (ambiguous)."
)

ASSET_TYPE_SCOPE = (
    "location.asset_location is populated exclusively by this pipeline from "
    "physical-structure asset types (ANS/WTG/OSS/OCS/RCS/JLEG/MET). The "
    "earlier CLUSTER-purpose branch (REC/IAC/ECR/OTHER) has moved to "
    "input_exploratory_hole.csv's cluster_details block (geotech.cluster_location), "
    "which is owned by a different pipeline. A stray cluster-purpose "
    "asset_type value in a layout_configuration row is REJECTED by "
    "validate.pdtable.layout (RejectedRow, not silently reclassified) with "
    "a cross-file message pointing to the correct file. There is no "
    "location_purpose_code column on location.asset_location any more -- the "
    "ASSET/CLUSTER distinction is now structural (which table a row lives "
    "in), not a column value; see geodb/sql/080__location_asset_location.sql."
)

PARENT_LOCATION_RESOLUTION = (
    "location.asset_location.parent_location_id (required whenever "
    "asset_type_code is 'JLEG', per its own CHECK constraint) has no direct "
    "file column -- layout_configuration.parent_asset_name names the parent "
    "asset's own layout_configuration.asset_name in the SAME "
    "**layout_configuration block (same layout_code). Resolved via: "
    "location.asset_location on (project_id, internal_reference = "
    "parent_asset_name) -> that row's asset_location_id becomes "
    "parent_location_id. validate.pdtable.layout rejects a JLEG row missing "
    "either jacket_leg_label or parent_asset_name outright (mirrors the "
    "DB's own CHECK constraints), rather than deferring to a raw constraint "
    "violation at load time."
)

RDSPP_CODE_MAPPING = (
    "project.layout_asset.rdspp_code ('RDS-PP code as assigned for this "
    "asset in this layout, e.g. WTG_A01'). layout_configuration.rdspp_code "
    "is the same column name in the real fixture -- a direct, unresolved "
    "copy."
)

WATER_LEVEL_MAPPING = (
    "layout_configuration.water_level (metres, relative to the coordinate "
    "system's vertical datum, unit row 'm') maps onto "
    "project.layout_asset.water_level_m. Column order within a "
    "layout_configuration block can vary between layout revisions (e.g. "
    "L003's block swaps water_level/asset_type vs L001/L002); columns are "
    "always read by header name, never positionally."
)

FOUNDATION_TYPE_MAPPING = (
    "layout_configuration.foundation_type maps onto "
    "project.layout_asset.foundation_type_code (FK to "
    "reference.foundation_type). The input file's picklist (GBS/MB/MP/PJ/SBJ) "
    "matches the seeded reference.foundation_type codes verbatim. A value "
    "not in the seeded set is rejected (RejectedRow) and the "
    "foundation_type_code is resolved to NULL, never force-inserted."
)

GROUND_LEVEL_MAPPING = (
    "layout_configuration.seabed_level (unit row 'm') maps onto "
    "project.layout_asset.seabed_level_m -- the same 'relative to the "
    "coordinate system's vertical datum' quantity 100__project_layout.sql "
    "documents."
)

EASTINGS_NORTHINGS_MAPPING = (
    "Simplified 2026-07-15: layout_configuration.eastings/northings (renamed "
    "from planned_eastings/planned_northings; the separate as_built_eastings/"
    "as_built_northings columns were dropped entirely) map onto "
    "project.layout_asset.eastings_m/northings_m (renamed from "
    "planned_eastings_m/planned_northings_m, per 100__project_layout.sql). "
    "There is no per-row 'is this planned or as-built' flag any more -- "
    "the layout REVISION itself carries that meaning via its own "
    "**layout_details.layout_status_code: unless a layout's status is "
    "'ASB' (as-built), its eastings_m/northings_m are implicitly the "
    "planned (design) position. A layout that has genuinely been "
    "as-built is expected to appear as its own **layout_details entry "
    "(status 'ASB') with its own **layout_configuration block carrying "
    "the as-installed coordinates -- not a second coordinate pair on the "
    "same row."
)

ASSET_TYPE_CODE_GAP = (
    "RESOLVED: reference.asset_type is seeded with codes matching the "
    "file's own asset_type.choice picklist verbatim (ANS/WTG/OSS/OCS/RCS/"
    "MET/JLEG plus REC/IAC/ECR/OTHER for the cluster-side pipeline). No "
    "translation is needed for asset_type_code itself."
)

# --- layout_details -> project.layout ---------------------------------------

LAYOUT_CATALOGUE_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="layout_code",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.layout",
        target_column="layout_code",
        notes=(
            "Natural key for the authoritative upsert, unique on "
            "(project_id, layout_code). Also the destination tag on every "
            "**layout_configuration block that references this revision."
        ),
    ),
    FieldMapping(
        source_field="layout_name",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.layout",
        target_column="layout_name",
        required=False,
    ),
    FieldMapping(
        source_field="layout_status_code",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.layout",
        target_column="layout_status_code",
        notes=(
            "Resolved/validated against reference.layout_status. "
            "Authoritative-upserted on every load (INSERT and UPDATE) -- "
            "see LAYOUT_STATUS_AUTHORITY."
        ),
    ),
    FieldMapping(
        source_field="effective_date",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.layout",
        target_column="effective_date",
        required=False,
        notes="yyyymmdd shape; parsed to date at validate stage.",
    ),
    FieldMapping(
        source_field="description",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.layout",
        target_column="description",
        required=False,
    ),
]

# --- layout_configuration -> location.asset_location ------------------------

ASSET_LOCATION_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="asset_name",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="location.asset_location",
        target_column="internal_reference",
        notes=(
            "Natural key for the authoritative upsert, unique on "
            "(project_id, internal_reference). See LAYOUT_CATALOGUE_AUTHORITY."
        ),
    ),
    FieldMapping(
        source_field="asset_type",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="location.asset_location",
        target_column="asset_type_code",
        notes="Resolved via lookup into reference.asset_type. See ASSET_TYPE_CODE_GAP.",
    ),
    FieldMapping(
        source_field="jacket_leg_label",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="location.asset_location",
        target_column="leg_label",
        required=False,
        notes="Required when asset_type is 'JLEG'.",
    ),
    FieldMapping(
        source_field="parent_asset_name",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="location.asset_location",
        target_column="parent_location_id",
        required=False,
        notes=(
            "Same-block join key (this row's parent asset's own asset_name). "
            "Required when asset_type is 'JLEG'. See PARENT_LOCATION_RESOLUTION."
        ),
    ),
]

# --- layout_configuration -> project.layout_asset ---------------------------

LAYOUT_ASSET_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field=None,
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.layout_asset",
        target_column="layout_id",
        notes=(
            "Resolved from the layout_configuration block's own destination "
            "tag (the layout_code itself) -- see LAYOUT_RESOLUTION."
        ),
    ),
    FieldMapping(
        source_field="eastings",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.layout_asset",
        target_column="eastings_m",
        notes="See EASTINGS_NORTHINGS_MAPPING.",
    ),
    FieldMapping(
        source_field="northings",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.layout_asset",
        target_column="northings_m",
        notes="See EASTINGS_NORTHINGS_MAPPING.",
    ),
    FieldMapping(
        source_field="seabed_level",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.layout_asset",
        target_column="seabed_level_m",
        required=False,
        notes="See GROUND_LEVEL_MAPPING.",
    ),
    FieldMapping(
        source_field="water_level",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.layout_asset",
        target_column="water_level_m",
        required=False,
        notes="See WATER_LEVEL_MAPPING.",
    ),
    FieldMapping(
        source_field="foundation_type",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.layout_asset",
        target_column="foundation_type_code",
        required=False,
        notes="Resolved via lookup into reference.foundation_type. See FOUNDATION_TYPE_MAPPING.",
    ),
    FieldMapping(
        source_field="rdspp_code",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.layout_asset",
        target_column="rdspp_code",
        required=False,
        notes="See RDSPP_CODE_MAPPING.",
    ),
    FieldMapping(
        source_field=None,
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="project.layout_asset",
        target_column="coordinate_system_id",
        notes="See COORDINATE_SYSTEM_RESOLUTION.",
    ),
]

UNMAPPED_LAYOUT_CONFIGURATION_FIELDS: list[str] = [
    "index",
    "alt_code",
    "comments",
]

# --- Out of scope (documented, never loaded) --------------------------------

OUT_OF_SCOPE = (
    "File-metadata lines (BlockType.METADATA): human documentation only. "
    "***revision_history (BlockType.DIRECTIVE): structural/provenance only. "
    "Every ::<table>/:<column> comment and .choice picklist line "
    "(BlockType.TEMPLATE_ROW): human documentation only -- though the "
    "asset_type and foundation_type picklists remain a useful cross-check "
    "against this schema's own seeded reference.* tables. "
    "as_built_eastings/as_built_northings columns were REMOVED from the "
    "**layout_configuration block entirely (2026-07-15) -- unless a "
    "layout's own **layout_details.layout_status_code is 'ASB' "
    "(as-built), its eastings/northings are implicitly the planned "
    "(design) position; there is no longer a separate as-built pair of "
    "columns to carry. See EASTINGS_NORTHINGS_MAPPING."
)
