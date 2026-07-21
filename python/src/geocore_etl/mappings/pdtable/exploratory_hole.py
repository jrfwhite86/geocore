"""pdtable exploratory-hole-input CSV -> geoCore mapping (Phase 10c, revised 2026-07-17).

Source: a pdtable ("StarTable") semicolon-delimited .csv describing every
geotechnical cluster location and every exploratory hole installed at a
project (see ``geodb/sample-data/pdtable/input_exploratory_holes_OWF.csv``).

Two block types populate this file (both are pdtable ``**<name>`` TABLE
blocks -- see ``mappings.pdtable.project``'s module docstring for the general
grammar). Unlike ``input_layout.csv``'s N per-``layout_code`` blocks, both
blocks here carry a single project-scoped destination (the project_code,
e.g. ``OWF01``) -- the same simpler single-destination shape used by
``mappings.pdtable.project``:

- Exactly one ``**cluster_details`` block. One row per geotechnical cluster
  location. Feeds ``geotech.cluster_location``.
- Exactly one ``**exploratory_hole_details`` block. One row per exploratory
  hole. Feeds ``geotech.exploratory_hole``.

No I/O, no pdtable import, no database access here -- pure data declarations,
mirroring ``mappings.pdtable.layout``/``mappings.pdtable.project``.

**2026-07-17 revision -- this file is the FINAL, QAQC'd snapshot, not a
second live source (superseding the original Phase 10c design):** per the
user's confirmed real-world workflow, EHS and this pdtable file are not two
concurrently-authoritative sources for the same columns -- they are two
stages of ONE sequential handoff:

    (i)   an EHS workbook is issued before mobilisation (every hole
          ``hole_status`` SCHEDULED) and RE-ISSUED across the campaign to
          report live progress (``load.xlsx.ehs``);
    (ii)  the campaign concludes -- every hole's status is now terminal
          (``!= SCHEDULED``/``INPROGRESS`` -- see reference.hole_status.
          is_terminal);
    (iii) a data engineer performs QAQC on that final EHS revision and
          pushes it, ONCE, as this pdtable file -- the authoritative FINAL
          snapshot of the whole campaign.

Consequently this file's ``**exploratory_hole_details`` block now carries
the SAME progress/final-state columns EHS does (``hole_status``,
``target_depth``, ``final_depth``, ``termination_reason``, ``start_date``,
``end_date``, ``bumpover_parent_hole``, ``comments``) -- not a narrower,
purely-structural subset as the original (now superseded) Phase 10c mapping
assumed. See ``FINAL_QAQC_AUTHORITY`` below for the full rationale and the
``geotech.site_investigation.survey_status_code`` lock
(``geodb/sql/138__geotech_site_investigation_survey_status.sql``) that
enforces the ordering between the two pipelines.
"""

from __future__ import annotations

from ..types import FieldMapping, SourceFormat

# --- Confirmed real pdtable table names (see module docstring) --------------
TABLE_CLUSTER_DETAILS = "cluster_details"
TABLE_EXPLORATORY_HOLE_DETAILS = "exploratory_hole_details"


# --- Authority / resolution rules (design decisions) ------------------------

CLUSTER_LOCATION_AUTHORITY = (
    "input_exploratory_holes.csv is the sole authoritative source for "
    "geotech.cluster_location's GEOMETRY (survey_phase_code, eastings_m, "
    "northings_m, ground_level_m, water_level_m, comments) via its "
    "**cluster_details block. Re-running the same file after a legitimate "
    "edit updates the existing rows to match the file (authoritative "
    "UPSERT), consistent with the layout pipeline's LAYOUT_CATALOGUE_"
    "AUTHORITY discipline. The EHS xlsx pipeline (load.xlsx.ehs) may ALSO "
    "create a geotech.cluster_location row (get-or-create, when a hole "
    "names a not-yet-declared cluster) but deliberately never populates its "
    "geometry (see geodb/sql/136__geotech_cluster_location_nullable_coords."
    "sql) -- this pipeline is the only one that ever writes cluster "
    "geometry, so there is no ordering hazard between the two for "
    "**cluster_details specifically, unlike **exploratory_hole_details "
    "(see FINAL_QAQC_AUTHORITY). This pipeline does NOT create or update "
    "anything in project.layout / location.asset_location / "
    "project.layout_asset -- those are owned by input_layout.csv's "
    "pipeline (out of scope here). It also does NOT create "
    "geotech.site_investigation rows -- those are owned by the EHS xlsx "
    "pipeline (load.xlsx.ehs) and are resolved-only here (see "
    "SITE_INVESTIGATION_RESOLUTION)."
)

FINAL_QAQC_AUTHORITY = (
    "2026-07-17 confirmed workflow: this pipeline is NOT a second, "
    "concurrently-authoritative source for geotech.exploratory_hole -- it "
    "is the FINAL stage of a sequential handoff FROM the EHS xlsx pipeline "
    "(load.xlsx.ehs). The real-world process is: (i) an EHS workbook is "
    "issued pre-mobilisation, every hole 'SCHEDULED'; (ii) it is RE-ISSUED "
    "across the campaign as fieldwork progresses -- hole_status_code moves "
    "through 'INPROGRESS' towards a terminal status per hole; (iii) once "
    "the campaign concludes (every hole terminal), a data engineer performs "
    "QAQC on that final EHS revision and pushes it, ONCE, as this file -- "
    "the authoritative final snapshot.\n\n"
    "Consequently this pipeline's UPSERT of geotech.exploratory_hole is "
    "deliberately just as FULL-OVERWRITE as load.xlsx.ehs's own (same "
    "'no COALESCE, no preserve-on-blank' discipline -- see load.xlsx.ehs's "
    "module docstring) -- the difference is WHEN it runs, not what columns "
    "it is allowed to touch. Enforced by "
    "geotech.site_investigation.survey_status_code (see "
    "geodb/sql/138__geotech_site_investigation_survey_status.sql): "
    "load.pdtable.exploratory_hole sets it to 'COMPLETE' after a successful "
    "load, and load.xlsx.ehs refuses (LoadError) to upsert any further hole "
    "for an already-'COMPLETE' site_investigation -- a live EHS re-issue "
    "can never run AFTER this file's QAQC'd push and silently un-finalise "
    "it, and this file is never expected to run BEFORE the campaign is "
    "genuinely finished (see HOLE_STATUS_MUST_BE_TERMINAL).\n\n"
    "'Full-overwrite' does NOT mean 'fabricate a substitute value' -- see "
    "ACTUAL_POSITION_PRECEDENCE for the 2026-07-20 correction to "
    "actual_easting_m/actual_northing_m, which had been unconditionally "
    "overwritten with a resolved design position rather than the file's "
    "own (or EHS's already-loaded) as-installed value."
)

HOLE_STATUS_MUST_BE_TERMINAL = (
    "exploratory_hole_details.hole_status is validated against "
    "reference.hole_status same as EHS's own 'Hole status' column, but with "
    "an ADDITIONAL rule EHS does not enforce: every row's hole_status must "
    "be a TERMINAL status (reference.hole_status.is_terminal = true, i.e. "
    "COMPLETED/ACCEPTED/FAILED/ABANDONED/CANCELLED, never SCHEDULED or "
    "INPROGRESS). A non-terminal value is REJECTED (RejectedRow), not "
    "silently accepted -- it is a strong signal the data engineer is "
    "pushing the file before the campaign genuinely concluded, i.e. before "
    "EHS's own re-issue cycle is actually done. This is the pipeline-level "
    "enforcement of FINAL_QAQC_AUTHORITY's step (iii): only a truly final "
    "EHS revision should ever reach this file."
)

ASSET_OR_CLUSTER_RESOLUTION = (
    "exploratory_hole_details.asset_or_cluster_name is the single join key "
    "that decides which of geotech.exploratory_hole's THREE mutually "
    "exclusive FK columns (layout_asset_id / asset_location_id / "
    "cluster_location_id) is populated for a given hole. The database CHECK "
    "constraint permits AT MOST one of these to be non-NULL.\n\n"
    "**2026-07-20 revision (STANDALONE support):** asset_or_cluster_name is "
    "OPTIONAL, not required. This corrects a 2026-07-17-era misreading of "
    "the file's own **exploratory_hole_details destination tag (e.g. "
    "'HEW02' on the line immediately below the **exploratory_hole_details "
    "table-name row) as a per-row fallback asset/cluster name -- it is "
    "not: that value is the block's project_code DESTINATION (see this "
    "module's own docstring), identical in kind to **layout_configuration's "
    "own destination tag in input_layout.csv, and is never read as a "
    "per-row value. A blank asset_or_cluster_name is therefore a "
    "genuinely STANDALONE hole (e.g. a one-off reconnaissance location "
    "never tied to an asset or grouped into a cluster) -- validate.pdtable."
    "exploratory_hole accepts a blank value as None, and the load stage "
    "leaves all three FK columns NULL for it, exactly mirroring "
    "load.xlsx.ehs's own optional asset_or_cluster_name handling and the "
    "2026-07-15 relaxation of geotech.exploratory_hole's CHECK constraint "
    "from 'exactly one' to 'at most one' (see "
    "120__geotech_site_investigation.sql).\n\n"
    "When asset_or_cluster_name IS supplied, the load stage must still "
    "resolve it to EXACTLY ONE target -- never more than one -- via the "
    "sequential algorithm below:\n\n"
    "Resolution algorithm (sequential -- (a) is checked first, (b) only "
    "runs if (a) found nothing, so a name that hypothetically matched "
    "both namespaces would always be routed via (a) and never double-"
    "matched):\n\n"
    "    (0) If asset_or_cluster_name is blank/None (2026-07-20: now "
    "        OPTIONAL): skip (a)/(b)/(c) entirely -- no lookups performed. "
    "        Leave layout_asset_id, asset_location_id AND cluster_location_id "
    "        all NULL. This is a STANDALONE hole.\n\n"
    "    (a) Else, look up location.asset_location on "
    "        (project_id, internal_reference = asset_or_cluster_name).\n"
    "        If found, this is an ASSET-purpose hole:\n"
    "          - Find the project's current layout:\n"
    "                SELECT layout_id FROM project.layout\n"
    "                WHERE project_id = %s AND layout_status_code = 'CUR'\n"
    "            LoadError if zero or more than one row -- e.g. a project\n"
    "            that has only the L000 placeholder (whose status is\n"
    "            'PLC', not 'CUR') and no real layout loaded yet hits\n"
    "            this path, which is the correct/expected behaviour.\n"
    "          - Resolve project.layout_asset on\n"
    "                (asset_location_id, layout_id = that CUR layout_id).\n"
    "            LoadError if no such row exists (the asset exists but was\n"
    "            never loaded into the CUR layout's layout_configuration\n"
    "            block -- a real data inconsistency, not silenced).\n"
    "          - Populate layout_asset_id with the resolved id; leave\n"
    "            asset_location_id AND cluster_location_id both NULL.\n\n"
    "    (b) Else, look up geotech.cluster_location on\n"
    "        (project_id, cluster_name = asset_or_cluster_name).\n"
    "        If found, this is a CLUSTER-purpose hole: populate\n"
    "        cluster_location_id with the resolved id; leave layout_asset_id\n"
    "        AND asset_location_id both NULL.\n\n"
    "    (c) Else (non-blank name matches neither namespace) -- LoadError\n"
    "        with a message naming both the asset_location and\n"
    "        cluster_location tables.\n\n"
    "Multi-layout ambiguity: when an asset name (e.g. 'WTG_001') appears "
    "in MORE THAN ONE **layout_configuration block in input_layout.csv "
    "(across layouts L001, L002, L003, ...), the hole is deliberately "
    "attached to the CUR-layout's layout_asset only. Historical/superseded "
    "layouts (SUP) are not re-attached to -- if a hole should be attached "
    "to a specific historical layout instead, that is a schema change, "
    "not a load-stage decision.\n\n"
    "Note: geotech.exploratory_hole.asset_location_id (the SECOND of the "
    "three FK columns) is effectively DEAD for anything loaded through "
    "THIS pipeline -- this format only ever produces layout_asset_id or "
    "cluster_location_id, never asset_location_id directly. That FK exists "
    "for a different, older use case (reconnaissance holes before any "
    "layout exists, resolved directly to a asset_location) which is not "
    "what CUR-status-layout-mediated resolution produces. The load stage "
    "always passes NULL for asset_location_id explicitly.\n\n"
    "actual_easting_m/actual_northing_m are NOT sourced from this "
    "resolution any more than as a fallback -- see "
    "ACTUAL_POSITION_PRECEDENCE below for the 2026-07-20 correction."
)

ACTUAL_POSITION_PRECEDENCE = (
    "2026-07-20 fix: prior to this revision, geotech.exploratory_hole."
    "actual_easting_m/actual_northing_m were unconditionally overwritten "
    "with the resolved layout_asset's/cluster_location's DESIGN position "
    "(see ASSET_OR_CLUSTER_RESOLUTION) on every load -- NOT read from any "
    "file column. Because the EHS xlsx pipeline (load.xlsx.ehs) already "
    "writes the hole's genuine AS-INSTALLED survey position into these "
    "same two columns (its own 'As-installed easting/northing' columns), "
    "and this pipeline's upsert is a full-overwrite (see "
    "FINAL_QAQC_AUTHORITY), running this 'final' file was silently "
    "DESTROYING real as-installed coordinates at the one moment they "
    "should matter most.\n\n"
    "Fixed by adding actual_easting/actual_northing as file columns on "
    "**exploratory_hole_details (optional, both-or-neither -- identical "
    "shape/validation to EHS's own 'As-installed easting/northing' "
    "columns) and changing the load-stage precedence to:\n\n"
    "    1. If the row supplies BOTH actual_easting AND actual_northing, "
    "       those values win -- they become actual_easting_m/"
    "       actual_northing_m verbatim, overriding both the design "
    "       position AND whatever value the row already had in the DB "
    "       (e.g. from an earlier EHS load).\n"
    "    2. Else (both blank), fall back to the pre-fix behaviour: echo "
    "       the resolved link target's design position. This is a "
    "       deliberate, documented degradation path for files that "
    "       haven't yet been updated to carry real as-installed "
    "       coordinates -- not a claim that design position equals "
    "       as-installed position.\n\n"
    "geotech.exploratory_hole.seabed_level_m is a related, previously "
    "entirely-unpopulated column (no source anywhere, EHS included) -- "
    "see the seabed_level FieldMapping: copied straight through, "
    "optional, no fallback (no other source exists for it)."
)

SITE_INVESTIGATION_RESOLUTION = (
    "exploratory_hole_details.site_investigation_reference is a "
    "reference.survey_phase_code value (GTP/GTL/GTR/GTD -- confirmed by "
    "the file's own site_investigation_reference.choice picklist), NOT a "
    "free-text si_name. Resolved via a lookup into geotech.site_investigation "
    "on (project_id, survey_phase_code) -- exactly the same resolve-only "
    "discipline the OLD input_exploratory_hole pipeline documented for "
    "this misleadingly-named column. This pipeline never CREATES a "
    "geotech.site_investigation row -- the EHS xlsx pipeline "
    "(load.xlsx.ehs) is the only pipeline that creates them. LoadError if "
    "no matching row exists (EHS must have been loaded for this project "
    "first) or if more than one exists for the same (project_id, "
    "survey_phase_code) pair (ambiguous -- EHS's own upsert should "
    "prevent this but the check is defensive). The load stage also checks "
    "the resolved row's survey_status_code is not already 'COMPLETE' from "
    "an EARLIER run of this same pipeline against the same campaign -- "
    "re-running this file is expected to be idempotent (an authoritative "
    "upsert), so re-processing an already-COMPLETE site_investigation is "
    "explicitly ALLOWED (unlike load.xlsx.ehs's lock, which is one-way): "
    "this pipeline is what sets 'COMPLETE' in the first place."
)

COORDINATE_SYSTEM_RESOLUTION = (
    "cluster_details rows carry eastings/northings but no "
    "coordinate_system_id column of their own; exploratory_hole_details "
    "rows carry no coordinates at all -- the hole's actual position is "
    "resolved from its resolved link target (a layout_asset's planned "
    "position, or its cluster_location's position). Both are resolved via "
    "the project's own 'ARRAY'-type location.boundary row, which "
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
    "project before input_exploratory_holes.csv can be. Identical mechanism "
    "to the layout pipeline's COORDINATE_SYSTEM_RESOLUTION."
)

BUMPOVER_PARENT_HOLE_RESOLUTION = (
    "exploratory_hole_details.bumpover_parent_hole is a raw "
    "contractor_hole_name string (mirrors EHS's own 'Bumpover parent hole' "
    "column and mappings.xlsx.ehs.BUMPOVER_PARENT_HOLE_RESOLUTION) -- "
    "resolved to parent_exploratory_hole_id by the load stage via a lookup "
    "scoped to the same site_investigation_id. Both-or-neither with "
    "bumpover_label, and self-reference, are rejected at validate time (no "
    "DB access needed) -- identical rules to EHS's own validate stage. An "
    "unresolvable name (typo, or the named parent hole genuinely never "
    "existed in the final EHS revision) is a load-time WARNING, not a "
    "LoadError -- same flag-don't-block discipline as EHS, since this is "
    "still an UPSERT of independently-droppable rows, not an all-or-nothing "
    "file."
)

HOLE_PURPOSE_INFORMATIONAL_ONLY = (
    "exploratory_hole_details.hole_purpose (picklist "
    "ANS/ECR/IAC/MET/OCS/OSS/OTHER/RCS/REC/WTG) is INFORMATIONAL only -- "
    "it exists purely to help a human reader understand at a glance "
    "whether a given hole was installed for a physical asset (WTG/OSS/...) "
    "or for a geotechnical cluster (REC/IAC/ECR/OTHER). It does NOT map "
    "to any DB column. The REAL discriminator for FK resolution is whether "
    "asset_or_cluster_name is blank (STANDALONE) or matches an entry in "
    "location.asset_location or in geotech.cluster_location (see "
    "ASSET_OR_CLUSTER_RESOLUTION). Kept in "
    "UNMAPPED_EXPLORATORY_HOLE_DETAILS_FIELDS to make the "
    "'read but not stored' status explicit."
)

POSITION_CONTEXT_OUT_OF_SCOPE = (
    "A 'hole_context' or similar reader-facing column (analogous to EHS's "
    "'Position context') is deliberately NOT part of this file's schema and "
    "must not be added. geotech.exploratory_hole.position_context_code is a "
    "DB-computed GENERATED ALWAYS column (see "
    "geodb/sql/120__geotech_site_investigation.sql) derived from which of "
    "layout_asset_id/asset_location_id/cluster_location_id ended up "
    "populated -- authoring it as a plain input column here would create "
    "exactly the drift risk this repo's data-integrity standard warns "
    "against (a human-entered value that can silently disagree with the "
    "DB-derived truth). EHS's own 'Position context' column exists only "
    "because that pipeline benefits from a soft cross-check against a "
    "human's expectation (Task 14a) -- this pipeline's asset_or_cluster_name "
    "always resolves authoritatively (blank -> STANDALONE, non-blank -> "
    "ASSET or CLUSTER via ASSET_OR_CLUSTER_RESOLUTION), so no such "
    "cross-check is needed here."
)


# --- cluster_details -> geotech.cluster_location ----------------------------

CLUSTER_LOCATION_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="cluster_name",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.cluster_location",
        target_column="cluster_name",
        notes=(
            "Natural key for the authoritative upsert, unique on "
            "(project_id, cluster_name). See CLUSTER_LOCATION_AUTHORITY."
        ),
    ),
    FieldMapping(
        source_field="site_investigation_reference",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.cluster_location",
        target_column="survey_phase_code",
        notes=(
            "Despite the column name, this is a reference.survey_phase_code "
            "value (GTP/GTL/GTR/GTD), not a free-text si_name. Validated "
            "against known_survey_phase_codes."
        ),
    ),
    FieldMapping(
        source_field="eastings",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.cluster_location",
        target_column="eastings_m",
    ),
    FieldMapping(
        source_field="northings",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.cluster_location",
        target_column="northings_m",
    ),
    FieldMapping(
        source_field="ground_level",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.cluster_location",
        target_column="ground_level_m",
        required=False,
        notes="Metres relative to the coordinate system's vertical datum (unit row 'm RL').",
    ),
    FieldMapping(
        source_field="water_level",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.cluster_location",
        target_column="water_level_m",
        required=False,
    ),
    FieldMapping(
        source_field="comments",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.cluster_location",
        target_column="comments",
        required=False,
    ),
    FieldMapping(
        source_field=None,
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.cluster_location",
        target_column="coordinate_system_id",
        notes="See COORDINATE_SYSTEM_RESOLUTION.",
    ),
]

UNMAPPED_CLUSTER_DETAILS_FIELDS: list[str] = [
    "index",
]


# --- exploratory_hole_details -> geotech.exploratory_hole -------------------

EXPLORATORY_HOLE_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="contractor_hole_name",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="contractor_hole_name",
        notes=(
            "Natural key for the authoritative upsert, unique on "
            "(site_investigation_id, contractor_hole_name)."
        ),
    ),
    FieldMapping(
        source_field="site_investigation_reference",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="site_investigation_id",
        notes="Resolved via SITE_INVESTIGATION_RESOLUTION -- not copied verbatim.",
    ),
    FieldMapping(
        source_field="hole_type",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="hole_type_code",
        notes=(
            "Validated against known_hole_type_codes (reference.hole_type). "
            "The file's own hole_type.choice picklist lists 'TCPT' (thermal "
            "CPT) which is NOT seeded in reference.hole_type -- any row "
            "using it is rejected, same defensive discipline other picklist "
            "validations use."
        ),
    ),
    FieldMapping(
        source_field="hole_number",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="hole_number",
        required=False,
    ),
    FieldMapping(
        source_field="jacket_leg_label",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="leg_label",
        required=False,
    ),
    FieldMapping(
        source_field="bumpover_label",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="bumpover_label",
        required=False,
        notes=(
            "Single lowercase letter if present. geotech.exploratory_hole's "
            "own CHECK constraint (~ '^[a-z]$') is mirrored at validate stage."
        ),
    ),
    FieldMapping(
        source_field="bumpover_parent_hole",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="parent_exploratory_hole_id",
        required=False,
        notes="Resolved via BUMPOVER_PARENT_HOLE_RESOLUTION -- not copied verbatim.",
    ),
    FieldMapping(
        source_field="hole_status",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="hole_status_code",
        notes="Must be a TERMINAL status -- see HOLE_STATUS_MUST_BE_TERMINAL.",
    ),
    FieldMapping(
        source_field="target_depth",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="target_depth_m",
        required=False,
    ),
    FieldMapping(
        source_field="final_depth",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="final_depth_m",
        required=False,
    ),
    FieldMapping(
        source_field="termination_reason",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="termination_reason_code",
        required=False,
        notes="Validated against known_termination_reason_codes if present.",
    ),
    FieldMapping(
        source_field="start_date",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="start_date",
        required=False,
        notes="yyyymmdd, mirrors EHS's own date columns.",
    ),
    FieldMapping(
        source_field="end_date",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="end_date",
        required=False,
        notes="yyyymmdd, mirrors EHS's own date columns.",
    ),
    FieldMapping(
        source_field="comments",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="comments",
        required=False,
    ),
    FieldMapping(
        source_field="asset_or_cluster_name",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="layout_asset_id",
        required=False,
        notes=(
            "OPTIONAL (2026-07-20): resolved to AT MOST ONE of "
            "layout_asset_id / cluster_location_id (never "
            "asset_location_id -- see ASSET_OR_CLUSTER_RESOLUTION); a "
            "blank value leaves both NULL, producing a STANDALONE hole. "
            "The target_column here is the primary of the two -- see the "
            "cluster_location_id mapping below for the other."
        ),
    ),
    FieldMapping(
        source_field="asset_or_cluster_name",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="cluster_location_id",
        required=False,
        notes="Second target of the two-way ASSET_OR_CLUSTER_RESOLUTION.",
    ),
    FieldMapping(
        source_field=None,
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="coordinate_system_id",
        notes="See COORDINATE_SYSTEM_RESOLUTION.",
    ),
    FieldMapping(
        source_field="actual_easting",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="actual_easting_m",
        required=False,
        notes=(
            "2026-07-20 fix (see ACTUAL_POSITION_PRECEDENCE): the file's own "
            "as-installed coordinate, carried over from the final EHS "
            "re-issue, WINS when present. Only falls back to echoing the "
            "resolved link target's (layout_asset's or cluster_location's) "
            "design position when both actual_easting/actual_northing are "
            "blank. Both-or-neither with actual_northing, mirroring "
            "validate.xlsx.ehs's identical rule for its own "
            "'As-installed easting/northing' columns."
        ),
    ),
    FieldMapping(
        source_field="actual_northing",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="actual_northing_m",
        required=False,
        notes="See actual_easting mapping above.",
    ),
    FieldMapping(
        source_field="seabed_level",
        source_format=SourceFormat.PDTABLE_CSV,
        target_table="geotech.exploratory_hole",
        target_column="seabed_level_m",
        required=False,
        notes=(
            "2026-07-20 addition: per-hole seabed/ground level as observed "
            "at time of works (AGS LOCA_GL). Distinct from "
            "cluster_details.ground_level, which is only an approximate "
            "level for the cluster as a whole. No other source exists for "
            "this column today -- copied straight through, optional, no "
            "fallback."
        ),
    ),
]

UNMAPPED_EXPLORATORY_HOLE_DETAILS_FIELDS: list[str] = [
    "index",
    "hole_purpose",
]


# --- Out of scope (documented, never loaded) --------------------------------

OUT_OF_SCOPE = (
    "File-metadata lines (BlockType.METADATA): human documentation only. "
    "***revision_history (BlockType.DIRECTIVE): structural/provenance only. "
    "Every ::<table>/:<column> comment and .choice picklist line "
    "(BlockType.TEMPLATE_ROW): human documentation only -- though the "
    "hole_type/hole_status/termination_reason/site_investigation_reference "
    "picklists remain a useful cross-check against this schema's seeded "
    "reference.* tables. hole_purpose is INFORMATIONAL only -- see "
    "HOLE_PURPOSE_INFORMATIONAL_ONLY. A 'hole_context'/'Position context' "
    "style column must never be added -- see POSITION_CONTEXT_OUT_OF_SCOPE."
)
