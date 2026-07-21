"""LOCA -> geotech.exploratory_hole mapping (tasks/plan.md Phase 3, Task 4).

See geodb/python/docs/ags-etl-mapping.md for narrative rationale.

Two things make this mapping less direct than a plain heading-to-column copy:

1. geotech.exploratory_hole requires a NOT NULL site_investigation_id FK, but
   no single AGS v1 group maps to geotech.site_investigation directly — see
   SITE_INVESTIGATION_RESOLUTION below.
2. geotech.exploratory_hole's coordinate/asset-linkage CHECK constraints are
   satisfied by LOCA's easting/northing alone (layout_asset_id and
   asset_location_id may both be NULL — see geodb/sql/120__geotech_site_investigation.sql)
   so v1 does not need to resolve an asset-layout position at all.
"""

from __future__ import annotations

from ..types import FieldMapping

LOCA_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="LOCA_ID",
        target_table="geotech.exploratory_hole",
        target_column="contractor_hole_name",
        notes=(
            "Free-text as recorded by the contractor — see the schema's own "
            "comment on contractor_hole_name about inconsistent naming "
            "(e.g. 'CPT-001a' vs 'CPT-001A')."
        ),
    ),
    FieldMapping(
        source_field="LOCA_TYPE",
        target_table="geotech.exploratory_hole",
        target_column="hole_type_code",
        notes=(
            "Resolved via lookup into reference.hole_type, not copied "
            "verbatim (AGS LOCA_TYPE values and geoCore hole_type_code "
            "values are not guaranteed to be the same strings) — see "
            "HOLE_TYPE_RESOLUTION below for the unmapped-value rule."
        ),
    ),
    FieldMapping(
        source_field="LOCA_NATE",
        target_table="geotech.exploratory_hole",
        target_column="actual_easting_m",
        notes=(
            "Mapped to actual_* (not planned_*) — an AGS LOCA row describes "
            "where a hole actually was, not a design position. The schema's "
            "CHECK constraint requires at least one of planned/actual to be "
            "set with both members of its pair non-NULL; LOCA alone "
            "satisfies this."
        ),
    ),
    FieldMapping(
        source_field="LOCA_NATN",
        target_table="geotech.exploratory_hole",
        target_column="actual_northing_m",
    ),
    FieldMapping(
        source_field="LOCA_GL",
        target_table="geotech.exploratory_hole",
        target_column="seabed_level_m",
        required=False,
        notes="Ground/seabed level. Optional in the schema.",
    ),
    FieldMapping(
        source_field="LOCA_EPSG",
        target_table="geotech.exploratory_hole",
        target_column="coordinate_system_id",
        notes=(
            "Primary source for coordinate_system_id: a direct EPSG code "
            "(e.g. '25832' for ETRS89 / UTM Zone 32N in the reference AGS "
            "fixture) looked up against reference.coordinate_system. "
            "Preferred over LOCA_GREF/LOCA_HDTM/LOCA_DATM (below) when "
            "present — see COORDINATE_SYSTEM_RESOLUTION for the fallback "
            "order across the AGS4 heading variants different contractor "
            "files actually use. CORRECTED 2026-07-09: LOCA_EPSG is "
            "confirmed ABSENT from both the public AGS4.1.1 dictionary and "
            "the AGS4+ (Revision E) dictionary (direct comparison against "
            "geodb/sample-data/ags/{AGS4-1-1,AGS4+E}.xlsx) — it is NOT a "
            "version-gated standard/in-house heading (an earlier note here "
            "speculated it was an 'AGS4.1 addition'; that speculation is now "
            "superseded by this direct comparison and was wrong). See "
            "version.py's LOCA_EPSG_NOT_IN_EITHER_DICTIONARY. No "
            "min_source_version is set here as a result — the fallback "
            "order below does not depend on it anyway."
        ),
    ),
    FieldMapping(
        source_field="LOCA_GREF",
        target_table="geotech.exploratory_hole",
        target_column="coordinate_system_id",
        required=False,
        notes=(
            "Older-style grid reference heading. Left blank in the reference "
            "AGS fixture (which uses LOCA_EPSG instead) but present as a "
            "heading in some contractor files — see COORDINATE_SYSTEM_RESOLUTION."
        ),
    ),
    FieldMapping(
        source_field="LOCA_HDTM",
        target_table="geotech.exploratory_hole",
        target_column="coordinate_system_id",
        required=False,
        notes=(
            "Horizontal datum name (e.g. 'ETRS89'). Supplements/cross-checks "
            "LOCA_EPSG rather than being the sole resolution source — some "
            "older AGS4 files instead carry LOCA_DATM for the same concept."
        ),
    ),
]

# LOCA_FDEP (final/total depth) has no direct exploratory_hole column in v1 —
# it is read only as a semantic validation bound for SCPT depth consistency
# (Task 8: final SCPT depth should not exceed LOCA_FDEP), never loaded verbatim.
LOCA_VALIDATION_ONLY_HEADINGS: list[str] = ["LOCA_FDEP"]

# AGS 4+ (Revision E) additions confirmed by direct comparison (2026-07-09)
# against the real geodb/sample-data/ags/{AGS4-1-1,AGS4+E}.xlsx dictionary
# templates' LOCA sections. These headings do not exist in the public AGS4.1.1
# dictionary at all — only present when AgsFileVersion.is_revision_e is True
# (see version.py's is_revision_e_marker()/resolve_ags_file_version()).
# Offshore-specific: LOCA_MUDL/LOCA_ZDTM/LOCA_ZMET/LOCA_ZTIM describe a
# mudline (seabed) level measurement, a more precise offshore analogue of the
# base dictionary's generic LOCA_GL.
LOCA_FIELD_MAPPINGS_REVISION_E_EXTRAS: list[FieldMapping] = [
    FieldMapping(
        source_field="LOCA_MUDL",
        target_table="geotech.exploratory_hole",
        target_column="seabed_level_m",
        required=False,
        notes=(
            "Revision E only. Offshore-specific mudline level relative to "
            "datum — preferred over LOCA_GL when both are present, since "
            "LOCA_MUDL is explicitly the seabed/mudline concept "
            "seabed_level_m models, whereas LOCA_GL is the base "
            "dictionary's generic 'ground level' (see LOCA_FIELD_MAPPINGS "
            "above). Not both loaded — same single-target-column precedence "
            "pattern as LOCA_EPSG vs LOCA_GREF/LOCA_HDTM for "
            "coordinate_system_id."
        ),
    ),
]

# LOCA_VESS (vessel name), LOCA_ZDTM (mudline reference datum system),
# LOCA_ZMET (mudline measurement method), LOCA_ZTIM (mudline measurement
# date/time) are also Revision E-only additions confirmed in the same
# comparison, but have no direct v1 target column: LOCA_VESS is
# location-level while the schema's only vessel column
# (geotech.cpt_test.vessel, also used by the CPT-JSON mapping — see
# geodb_etl.mappings.json.cpt) is test-level, a mismatch not resolved here;
# LOCA_ZDTM/ZMET/ZTIM are measurement-provenance metadata for LOCA_MUDL with
# no corresponding exploratory_hole column at all. Tracked as a gap, not
# silently dropped or force-mapped to a mismatched column.
LOCA_REVISION_E_UNMAPPED_HEADINGS: list[str] = [
    "LOCA_VESS",
    "LOCA_ZDTM",
    "LOCA_ZMET",
    "LOCA_ZTIM",
]

# Confirmed (2026-07-09): in the public AGS4.1.1 dictionary, LOCA_FDEP's
# DICT_STAT is "OTHER" (optional). In the AGS4+ (Revision E) dictionary,
# DICT_STAT for the same heading is "REQUIRED". LOCA_VALIDATION_ONLY_HEADINGS
# above still applies to both (LOCA_FDEP is never loaded as a column either
# way) — but a Revision E file missing LOCA_FDEP is a validation failure
# (Task 8), where a base-dictionary file missing it is not.
LOCA_FDEP_REQUIRED_IN_REVISION_E = (
    "LOCA_FDEP is DICT_STAT 'OTHER' (optional) in the public AGS4.1.1 "
    "dictionary but 'REQUIRED' in AGS4+ (Revision E) — confirmed by direct "
    "comparison of geodb/sample-data/ags/{AGS4-1-1,AGS4+E}.xlsx's DICT "
    "sheets. A Revision E file (AgsFileVersion.is_revision_e is True) "
    "missing LOCA_FDEP is a semantic validation failure (Task 8), even "
    "though LOCA_FDEP is never loaded as an exploratory_hole column either "
    "way (see LOCA_VALIDATION_ONLY_HEADINGS)."
)

# geotech.site_investigation (project_id, si_name, survey_phase_code, unique
# per project) is a required parent of exploratory_hole, but v1's AGS groups
# (PROJ, LOCA, SCPG, SCPT) contain nothing that cleanly identifies "which site
# investigation campaign is this file". TRAN would be the natural AGS home for
# file-level campaign metadata, but TRAN is out of v1 scope (file-structural
# group, not parsed for domain data) and does not carry a survey-phase concept
# regardless.
SITE_INVESTIGATION_RESOLUTION = (
    "One geotech.site_investigation row is resolved (or created) per pipeline "
    "run, not per LOCA row. si_name and survey_phase_code are supplied as "
    "required CLI arguments (Task 11: `geodb-etl load file.ags --si-name ... "
    "--survey-phase ...`) rather than parsed from AGS data, because no v1 AGS "
    "group reliably carries them. All LOCA rows in one file resolve to the "
    "same site_investigation_id."
)

HOLE_TYPE_RESOLUTION = (
    "LOCA_TYPE is looked up against reference.hole_type_code (case-insensitive "
    "match against both code and a maintained synonym list, e.g. AGS 'CPT' vs "
    "geoCore's own code for a CPT-type hole). A LOCA_TYPE value with no match "
    "in either the code or the synonym list produces a RejectedRow (Task 8) — "
    "it is not defaulted to any hole type, since hole_type_code is a NOT NULL "
    "column and guessing wrongly here would misclassify every downstream "
    "in_situ_test/cpt_test row attached to that hole. AGS 4+ (Revision E)'s "
    "LOCA_TYPE picklist (confirmed 2026-07-09 by direct comparison) extends "
    "the base dictionary with 'AUG' (generic Hollow/Solid Stem Auger), "
    "'CP+RC' (Cable percussion with Rotary follow-on — a combined value the "
    "base dictionary's own heading example already showed but never listed "
    "as its own ABBR row), and 'DWS' (Drinking water sampling location) — "
    "the synonym list must include these for Revision E files, not just the "
    "base dictionary's codes."
)

COORDINATE_SYSTEM_RESOLUTION = (
    "LOCA_EPSG (a direct EPSG code, e.g. '25832') is the primary source for "
    "coordinate_system_id when present — the reference AGS fixture supplies "
    "it directly, making resolution a straightforward lookup rather than a "
    "grid-reference/datum-name guess. Where LOCA_EPSG is absent, LOCA_GREF "
    "(grid reference) plus LOCA_HDTM (horizontal datum name) or the older "
    "LOCA_DATM heading are looked up together against "
    "reference.coordinate_system instead — different contractor files use "
    "different AGS4 heading variants for the same underlying concept, so all "
    "three are supported. An unrecognised or missing value across all "
    "available headings produces a RejectedRow (Task 8) rather than a "
    "silent default coordinate system — coordinate_system_id is NOT NULL on "
    "exploratory_hole and a wrong default would silently corrupt every "
    "downstream coordinate reading for that hole."
)

# Coordinate sanity checking against a development-area envelope, as an
# external review of this plan initially proposed, is NOT included here:
# location.development_area (geodb/sql/030__location_development_area.sql) has
# no envelope/bounding columns at all. A conditional check against
# location.boundary/boundary_vertex (if a boundary already exists for the
# target project) is noted as a possible v1.1 enhancement, not a v1 rule.
COORDINATE_SANITY_NOTE = (
    "No development_area envelope exists to check LOCA_NATE/LOCA_NATN "
    "against in v1. A per-project location.boundary/boundary_vertex check is "
    "possible in principle but conditional on a boundary already existing for "
    "the resolved project — deferred, not part of v1's semantic validation."
)





