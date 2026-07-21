"""EHS workbook -> geotech.site_investigation / geotech.exploratory_hole mapping.

An Exploratory Hole Schedule (EHS) is issued to the SI contractor prior to
mobilisation and then **RE-ISSUED across the life of the campaign** to report
progress (revision control r01, r02, ... — see the workbook's own Guidance
sheet). This is the FIRST record of a campaign to reach geoCore —
geotech.site_investigation is created here, not merely resolved (contrast
with the AGS path, see geodb_etl.mappings.ags.proj.PROJECT_RESOLUTION, where
project.project already exists and is never created by ETL). See
SITE_INVESTIGATION_AUTHORITY below.

**Grounded (2026-07-16) against the real, revised workbook**
(geodb/sample-data/xlsx/EHS/EHS_OWF01_GTP_r01.xlsx, sheet "EHS") via
openpyxl — not assumed. This supersedes the earlier (2026-07-10) grounding
against the now-retired EHS_HEW02_GTP_r01.xlsx layout — see
UNMAPPED_HEADINGS/"Position context" discussion below for what changed.
Confirmed layout:

- Header block: rows 4-18, label in column A, value in column D — unchanged
  in shape from the earlier layout. See HEADER_FIELD_CELLS below.
- Table header: row 22 (columns A-T, was A-K in the original layout) —
  **"Hole number" has been dropped entirely** and 10 new columns added since
  the original layout: Position context, Hole status, Start date, End date,
  As-installed easting/northing, Final depth, Termination reason (2026-07-16
  progress-tracking revision), plus **Bumpover label, Bumpover parent hole**
  (added in a second 2026-07-16 revision, inserted immediately before
  Remarks — see BUMPOVER_PARENT_HOLE_RESOLUTION below). Data rows: 23
  onward, terminated by the first row with an empty column A ("No.").
- A "Reference" sheet mirrors geoCore's own reference.hole_type/
  reference.survey_phase/reference.depth_reference/priority/**hole_status**/
  **termination_reason** code lists (confirmed character-for-character
  identical to this schema's seeded reference tables, including the
  hole_status/termination_reason tables added in
  geodb/sql/122__reference_hole_status_enums.sql) — usable directly for
  semantic validation's unmapped-value check, not just a human aid.
- A "Guidance" sheet confirms (in the file's own words): "geoCore will reject
  rows lacking a coordinate system" (coordinate_system_id, see below) and
  that "Exploratory hole name is the definitive planned name... used
  verbatim... in AGS deliverables (LOCA_ID)" — i.e. contractor_hole_name is
  the confirmed join key between this format and the AGS LOCA path.

**coordinate_system_id gap RESOLVED (2026-07-10):** an earlier draft of this
module treated coordinate_system_id as unavailable from EHS data (see the
retired COORDINATE_SYSTEM_RESOLUTION note). The real workbook's header row 10
("Horizontal CRS (EPSG)", e.g. "EPSG:25831 (ETRS89 / UTM 31N)") does supply
it — see COORDINATE_SYSTEM_RESOLUTION below for the corrected rule.

**Full-overwrite upsert semantics (2026-07-16, confirmed user decision):** a
blank progress cell (Hole status/Start date/End date/As-installed
easting+northing/Final depth/Termination reason/Remarks) on a re-issued EHS
revision is an EXPLICIT INSTRUCTION to clear that field back to NULL — the
most recently loaded revision is the sole source of truth for every mapped
column on that hole. This is NOT a COALESCE-style preserve-on-blank; see
load.xlsx.ehs's module docstring for the load-stage consequence. This also
means a blank As-installed easting/northing on a later revision overwrites
(clears) a previously-populated actual_easting_m/actual_northing_m pair, even
one originally sourced from an AGS delivery — a deliberate reversal of this
module's own historical "never clobber actual_*" rule (see the retired
"Coordinates: planned-only" framing in earlier revisions of this docstring).

leg_label remains explicitly OUT OF SCOPE for this mapping — it is inferred
 later from either the AGS delivery or a future dedicated leg-naming
 convention, never from EHS ingestion. No "leg" column exists in the
 workbook. exploratory_hole rows loaded via this mapping leave leg_label
 NULL.

 bumpover_label (table column R, "Bumpover label") and "Bumpover parent hole"
 (table column S) are NEW in this layout (second 2026-07-16 revision,
 inserted immediately before Remarks) and ARE NOW IMPLEMENTED — superseding
 the earlier "deferred" framing above for bumpover_label specifically. The
 workbook's own "Bumpover naming convention" header (row 14) documents HOW a
 bumpover is named ("lowercase suffix a, b, c... appended to hole name");
 these two table columns record THAT a given row IS a bumpover (its single
 lowercase letter suffix) and WHICH prior hole it bumps over from, making the
 relationship explicit rather than inferred from the hole name string.
 bumpover_label maps directly to geotech.exploratory_hole.bumpover_label
 (validated against the same `^[a-z]$` pattern as the DB CHECK). "Bumpover
 parent hole" does NOT map directly to a column — it is a raw hole-name
 string, resolved at the load stage to parent_exploratory_hole_id via a
 lookup on (site_investigation_id, contractor_hole_name), mirroring the
 "Cluster / asset name" resolution pattern below. See
 BUMPOVER_PARENT_HOLE_RESOLUTION.

 "Cluster / asset name" (table column B) resolution: (2026-07-15) IMPLEMENTED.
 The "Cluster / asset name" column contains asset or cluster identifiers that
 map to exactly one of layout_asset_id, asset_location_id, or cluster_location_id
 per the exploratory_hole table's CHECK constraint. The load stage resolves the
 name to the appropriate ID via lookups in project.layout_asset,
 location.asset_location, and geotech.cluster_location. Matches the pdtable
 exploratory_hole resolution discipline (see
 mappings.pdtable.exploratory_hole.ASSET_OR_CLUSTER_RESOLUTION).

 "Position context" (table column J, new in this layout) is NOT itself
 stored — the DB derives position_context_code from which of
 layout_asset_id/asset_location_id/cluster_location_id ended up populated
 (see geotech.exploratory_hole's GENERATED ALWAYS column). This column is
 read through to the load stage purely as a SOFT CROSS-CHECK: if it
 disagrees with what the load stage actually resolved, a warning is emitted
 (never a rejection) — see load.xlsx.ehs's Position-context cross-check.

 "Layout code / revision" (header row 9) hints at a project.layout_asset
 resolution path (confirmed by the real workbook's own H9 annotation) — left
 unmapped since this EHS document is not tied to a specific deployment
 layout.
 """

from __future__ import annotations

from ..types import FieldMapping, SourceFormat

# --- Confirmed real workbook structure (sheet "EHS") ---------------------
EHS_SHEET_NAME = "EHS"

# Header block: label in column A, value in column D, row per field below.
HEADER_LABEL_COLUMN = "A"
HEADER_VALUE_COLUMN = "D"
HEADER_FIELD_CELLS: dict[str, int] = {
    "Project name": 4,
    "Project code": 5,
    "Site investigation name": 6,
    "Survey phase code": 7,
    "Contractor": 8,
    "Layout code / revision": 9,
    "Horizontal CRS (EPSG)": 10,
    "Vertical datum (water depths)": 11,
    "Depth reference (hole depths)": 12,
    "Position tolerance": 13,
    "Bumpover naming convention": 14,
    "Form revision": 15,
    "Date issued": 16,
    "Prepared by": 17,
    "Approved by": 18,
}

# Tabular hole schedule: header row, then data rows terminated by the first
# row with a blank "No." (column A) cell — not a fixed row count, since the
# schedule's length varies per campaign (6/15/27 holes across the three
# sample OWF01 fixtures). Column letters as confirmed in the real workbook's
# row 22 (2026-07-16 grounding, EHS_OWF01_GTP_r01.xlsx). Header cell text
# contains embedded literal newlines (e.g. "Hole type\ncode") — parse.py
# normalizes whitespace before comparing against these labels. "Hole number"
# (formerly column D) has been REMOVED from this layout entirely — do not
# reintroduce it here.
TABLE_HEADER_ROW = 22
TABLE_DATA_FIRST_ROW = 23
TABLE_COLUMNS: dict[str, str] = {
    "No.": "A",
    "Cluster / asset name": "B",
    "Exploratory hole name": "C",
    "Hole type code": "D",
    "Target easting [m]": "E",
    "Target northing [m]": "F",
    "Water depth [m relative to vertical datum]": "G",
    "Target depth [m BSF]": "H",
    "Priority": "I",
    "Position context": "J",
    "Hole status": "K",
    "Start date [yyyymmdd]": "L",
    "End date [yyyymmdd]": "M",
    "As-installed easting [m]": "N",
    "As-installed northing [m]": "O",
    "Final depth [m BSF]": "P",
    "Termination reason": "Q",
    "Bumpover label": "R",
    "Bumpover parent hole": "S",
    "Remarks": "T",
}

# geotech.site_investigation is CREATED (get-or-create) by this mapping, not
# merely cross-checked — the reverse of mappings.ags.proj's PROJECT_RESOLUTION
# rule, because an EHS workbook is (by definition) the earliest document in a
# campaign's lifecycle: it exists before mobilisation, before any AGS
# deliverable does. project_id itself is still operator-supplied
# (--project-code, same rule as the AGS path — no workbook column identifies
# which project.project row this belongs to).
SITE_INVESTIGATION_AUTHORITY = (
    "si_name (EHS header 'Site investigation name') is the AUTHORITATIVE "
    "initial value for geotech.site_investigation.si_name: this load path "
    "get-or-creates the row (unique on project_id, si_name) rather than "
    "resolving an already-existing one. Any later AGS delivery for the same "
    "campaign is expected to be checked AGAINST this EHS-sourced si_name "
    "(mirroring, but inverting, mappings.ags.proj.PROJ_INCONSISTENCY_POLICY's "
    "flag-don't-block rule) -- not the other way around: geoCore's "
    "EHS-derived site_investigation row is always the 'true' value once "
    "created, and a mismatching AGS heading (were one to exist) would be "
    "flagged, not used to overwrite si_name. start_date, end_date, "
    "report_reference and description are never populated by this or any "
    "other ETL path; they remain NULL until manually populated by the Data "
    "Manager/Steward after the works and field report (see "
    "geodb/sql/120__geotech_site_investigation.sql's column comments)."
)

SITE_INVESTIGATION_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="Site investigation name",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.site_investigation",
        target_column="si_name",
        notes="Header field. See SITE_INVESTIGATION_AUTHORITY above.",
    ),
    FieldMapping(
        source_field="Survey phase code",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.site_investigation",
        target_column="survey_phase_code",
        notes=(
            "Resolved via lookup into reference.survey_phase, not copied "
            "verbatim -- same unmapped-value-is-a-RejectedRow rule as "
            "mappings.ags.loca.HOLE_TYPE_RESOLUTION uses for hole_type_code."
        ),
    ),
    FieldMapping(
        source_field="Contractor",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.site_investigation",
        target_column="contractor",
        required=False,
    ),
]

EXPLORATORY_HOLE_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="Exploratory hole name",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.exploratory_hole",
        target_column="contractor_hole_name",
    ),
    FieldMapping(
        source_field="Hole type code",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.exploratory_hole",
        target_column="hole_type_code",
        notes=(
            "Same reference.hole_type lookup/unmapped-value rule as the AGS "
            "LOCA_TYPE path (see mappings.ags.loca.HOLE_TYPE_RESOLUTION)."
        ),
    ),
    FieldMapping(
        source_field="Cluster / asset name",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.exploratory_hole",
        target_column="asset_or_cluster_name",
        required=False,
        notes=(
            "A hole links to AT MOST one of: layout_asset_id, "
            "asset_location_id, or cluster_location_id (2026-07-15: loosened "
            "from 'exactly one' to support genuinely standalone holes -- see "
            "geodb/sql/120__geotech_site_investigation.sql). This field "
            "carries the name/identifier from the EHS workbook; the load "
            "stage resolves it to one of the three ID columns via lookups "
            "in project.layout_asset, location.asset_location, and "
            "geotech.cluster_location (creating a new cluster_location "
            "get-or-create style if the name matches neither an existing "
            "asset nor an existing cluster). A blank/missing value means "
            "the hole is standalone -- all three ID columns are left NULL, "
            "not a validation failure."
        ),
    ),
    FieldMapping(
        source_field="Target easting [m]",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.exploratory_hole",
        target_column="planned_easting_m",
        notes=(
            "Mapped to planned_* (not actual_*) -- an EHS row's Target "
            "easting/northing always describe the DESIGN position, distinct "
            "from the same row's own As-installed easting/northing (mapped "
            "to actual_easting_m/actual_northing_m below). Unlike the "
            "retired 'planned-only' design, this format now supplies BOTH "
            "planned_* and actual_* on the same row once a hole has actually "
            "been occupied -- see actual_easting_m's FieldMapping below for "
            "the full-overwrite upsert semantics that now apply to actual_* "
            "too (2026-07-16 confirmed decision)."
        ),
    ),
    FieldMapping(
        source_field="Target northing [m]",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.exploratory_hole",
        target_column="planned_northing_m",
    ),
    FieldMapping(
        source_field="Horizontal CRS (EPSG)",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.exploratory_hole",
        target_column="coordinate_system_id",
        notes=(
            "Header field (not a table column) -- applies to every hole row "
            "in the file. Value is of the form 'EPSG:25831 (ETRS89 / UTM "
            "31N)'; only the leading 'EPSG:<code>' token is significant, "
            "looked up against reference.coordinate_system. See "
            "COORDINATE_SYSTEM_RESOLUTION below -- confirmed available "
            "(2026-07-10, real workbook), a genuine header field, not an "
            "operator-supplied fallback."
        ),
    ),
    FieldMapping(
        source_field="Hole status",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.exploratory_hole",
        target_column="hole_status_code",
        required=False,
        notes=(
            "Resolved via lookup into reference.hole_status (see "
            "geodb/sql/122__reference_hole_status_enums.sql), same "
            "unmapped-value-is-a-RejectedRow rule as hole_type_code. A "
            "blank cell defaults to 'SCHEDULED', mirroring the DB column's "
            "own NOT NULL DEFAULT 'SCHEDULED'."
        ),
    ),
    FieldMapping(
        source_field="Target depth [m BSF]",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.exploratory_hole",
        target_column="target_depth_m",
        required=False,
        notes="Optional numeric, must be >= 0 (mirrors the DB's own CHECK).",
    ),
    FieldMapping(
        source_field="Start date [yyyymmdd]",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.exploratory_hole",
        target_column="start_date",
        required=False,
        notes=(
            "openpyxl may return either a date/datetime (date-formatted "
            "cell) or a bare yyyymmdd int/string (text-formatted cell, per "
            "the header's own '[yyyymmdd]' hint) -- both are parsed to the "
            "same date by the validate stage."
        ),
    ),
    FieldMapping(
        source_field="End date [yyyymmdd]",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.exploratory_hole",
        target_column="end_date",
        required=False,
    ),
    FieldMapping(
        source_field="As-installed easting [m]",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.exploratory_hole",
        target_column="actual_easting_m",
        required=False,
        notes=(
            "As-installed (actual) position, distinct from the same row's "
            "Target easting/northing (planned_*). Must be present-or-absent "
            "together with 'As-installed northing [m]' (mirrors the DB's "
            "(actual_easting_m IS NULL) = (actual_northing_m IS NULL) "
            "CHECK). FULL-OVERWRITE on every load (2026-07-16 confirmed "
            "decision) -- a blank cell on a later revision clears a "
            "previously-populated value, including one originally sourced "
            "from an AGS delivery. See load.xlsx.ehs's module docstring."
        ),
    ),
    FieldMapping(
        source_field="As-installed northing [m]",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.exploratory_hole",
        target_column="actual_northing_m",
        required=False,
    ),
    FieldMapping(
        source_field="Final depth [m BSF]",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.exploratory_hole",
        target_column="final_depth_m",
        required=False,
        notes="Optional numeric, must be >= 0 (mirrors the DB's own CHECK).",
    ),
    FieldMapping(
        source_field="Termination reason",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.exploratory_hole",
        target_column="termination_reason_code",
        required=False,
        notes=(
            "Resolved via lookup into reference.termination_reason (see "
            "geodb/sql/122__reference_hole_status_enums.sql), optional -- "
            "not every hole_status_code implies a termination_reason_code "
            "(e.g. SCHEDULED/INPROGRESS holes have none)."
        ),
    ),
    FieldMapping(
        source_field="Bumpover label",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.exploratory_hole",
        target_column="bumpover_label",
        required=False,
        notes=(
            "2026-07-16 confirmed decision (second revision) -- previously "
            "deferred, see LEG_LABEL_DEFERRED. Optional single "
            "lowercase letter, validated against the same '^[a-z]$' pattern "
            "as the DB CHECK (geodb/sql/120__geotech_site_investigation.sql). "
            "Only meaningful together with 'Bumpover parent hole' -- see "
            "BUMPOVER_PARENT_HOLE_RESOLUTION for the both-or-neither rule "
            "and the (deliberately unenforced at DB level) relationship "
            "between the two columns."
        ),
    ),
    FieldMapping(
        source_field="Remarks",
        source_format=SourceFormat.EHS_XLSX,
        target_table="geotech.exploratory_hole",
        target_column="comments",
        required=False,
        notes=(
            "2026-07-16 confirmed decision -- previously unmapped. "
            "Free-text, no validation beyond full-overwrite-on-reload."
        ),
    ),
]

# geotech.project.project cross-check ONLY -- never used to select/insert a
# project, identical discipline to mappings.ags.proj.PROJ_FIELD_MAPPINGS.
# project_id remains resolved via the operator's --project-code CLI argument.
PROJECT_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="Project name",
        source_format=SourceFormat.EHS_XLSX,
        target_table="project.project",
        target_column="project_name",
        required=False,
        notes="Cross-checked only -- see mappings.ags.proj.PROJ_INCONSISTENCY_POLICY's rule.",
    ),
    FieldMapping(
        source_field="Project code",
        source_format=SourceFormat.EHS_XLSX,
        target_table="project.project",
        target_column="project_code",
        required=False,
        notes="Cross-checked only -- same discipline as PROJ_ID in the AGS mapping.",
    ),
]

# leg_label deliberately absent from EXPLORATORY_HOLE_FIELD_MAPPINGS above --
# see module docstring. Tracked here, not silently forgotten, so a future
# mapping module has an explicit anchor to extend. bumpover_label was moved
# OUT of this deferred set on 2026-07-16 (second revision) -- it is now
# mapped above; only leg_label remains deferred.
LEG_LABEL_DEFERRED = (
    "leg_label is not populated by this mapping. No leg-naming column exists "
    "in the EHS workbook (unlike bumpover_label, which the 2026-07-16 second "
    "revision added as 'Bumpover label'). leg_label is expected to be "
    "resolved later from either (a) an AGS delivery for the same hole, or "
    "(b) a future dedicated leg-naming mapping path -- neither source is "
    "implemented yet. Do not add a heuristic parse of contractor_hole_name "
    "to infer it here; wait for one of the two named sources."
)

# "Bumpover parent hole" (table column S) is READ but deliberately not itself
# a FieldMapping target with a fixed target_column -- it is a raw hole-name
# STRING, not an ID, so it cannot be written directly to
# parent_exploratory_hole_id. Instead it is plumbed through
# parse -> validate -> transform as an unresolved string, and the load stage
# resolves it to parent_exploratory_hole_id via a lookup on
# (site_investigation_id, contractor_hole_name) -- mirroring the "Cluster /
# asset name" -> asset_or_cluster_name resolution pattern above, but with a
# FLAG-DON'T-BLOCK failure mode (2026-07-16 confirmed decision, chosen over
# rejecting the row): an unresolvable name (typo, wrong load order, parent
# not yet loaded) loads the row with parent_exploratory_hole_id = NULL and
# emits a warning via EhsLoadResult.warnings, reusing the exact mechanism
# built for POSITION_CONTEXT_CROSS_CHECK_ONLY. See load.xlsx.ehs's module
# docstring for the resolution logic itself.
BUMPOVER_PARENT_HOLE_RESOLUTION = (
    "'Bumpover parent hole' (table column S) is a raw contractor_hole_name "
    "string, resolved at the load stage -- via a lookup scoped to the same "
    "site_investigation_id -- to parent_exploratory_hole_id "
    "(geodb/sql/134__geotech_exploratory_hole_bumpover.sql). An unresolvable "
    "name does NOT reject the row: it loads with "
    "parent_exploratory_hole_id = NULL and a warning is emitted (flag-don't- "
    "block, matching the Position-context cross-check's failure mode). The "
    "DB deliberately has NO CHECK constraint tying bumpover_label and "
    "parent_exploratory_hole_id together (e.g. no both-or-neither rule) -- "
    "an unresolved parent reference can legitimately leave "
    "parent_exploratory_hole_id NULL even when bumpover_label is set; this "
    "is documented as a convention (see the column's own COMMENT ON COLUMN), "
    "not enforced. The validate stage separately rejects a row whose "
    "'Bumpover parent hole' names itself (self-reference), and requires "
    "bumpover_label/'Bumpover parent hole' to be present-or-absent together "
    "at the source-data level, ahead of any DB-level lookup."
)

# CORRECTED 2026-07-10 (real workbook comparison): an earlier draft of this
# note treated coordinate_system_id as unavailable from EHS data and requiring
# an operator-supplied fallback. The real workbook's header row 10 does
# supply it -- see the coordinate_system_id FieldMapping above.
COORDINATE_SYSTEM_RESOLUTION = (
    "coordinate_system_id is resolved from the 'Horizontal CRS (EPSG)' "
    "header field (e.g. 'EPSG:25831 (ETRS89 / UTM 31N)') -- the leading "
    "'EPSG:<code>' token is extracted and looked up against "
    "reference.coordinate_system. Applies to every hole row in the file "
    "(one CRS per EHS workbook, not per row). Per the workbook's own "
    "Guidance sheet: 'coordinates are meaningless without it and geoCore "
    "will reject rows lacking a coordinate system' -- a missing or "
    "unparseable EPSG code is a hard, whole-file semantic validation "
    "failure (RejectedRow for every hole row), not a per-row default."
)

# EHS headers read for context/validation but never loaded as a column value —
# no target_table/target_column exists for any of them. Retained here (rather
# than silently ignored) per this repo's data-integrity convention of never
# discarding source data without a documented reason. "Target depth [m BSF]"
# and "Remarks" moved OUT of this list on 2026-07-16 (now mapped to
# target_depth_m/comments respectively, above).
UNMAPPED_HEADINGS: list[str] = [
    "Water depth [m relative to vertical datum]",
    "Priority",
    "Layout code / revision",
    "Vertical datum (water depths)",
    "Depth reference (hole depths)",
    "Position tolerance",
    "Bumpover naming convention",
    "Form revision",
    "Date issued",
    "Prepared by",
    "Approved by",
]

# "Position context" (table column J) is READ but deliberately not itself a
# FieldMapping target -- no target_table/target_column exists for it because
# geotech.exploratory_hole.position_context_code is a DB-computed
# (GENERATED ALWAYS) column derived from which of layout_asset_id/
# asset_location_id/cluster_location_id ended up populated, not something an
# ETL stage writes directly. This heading is instead plumbed through
# parse -> validate -> transform as a raw, unvalidated string, purely so the
# load stage can perform a SOFT cross-check: compare the workbook's stated
# Position context against what the load stage actually resolved, and warn
# (never reject) on a mismatch (2026-07-16 confirmed decision -- see
# load.xlsx.ehs's module docstring for the cross-check itself).
POSITION_CONTEXT_CROSS_CHECK_ONLY = (
    "'Position context' (table column J) is read through to the load stage "
    "as an unvalidated string purely for a soft cross-check against the "
    "DB-computed position_context_code -- it is never itself written to any "
    "column. A mismatch produces a warning, not a RejectedRow, since the "
    "resolved asset/cluster association (not this human-entered column) is "
    "always the authoritative value."
)




