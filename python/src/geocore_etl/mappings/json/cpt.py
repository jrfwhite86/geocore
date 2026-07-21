"""CPT "silver" JSON -> geoCore mapping declarations (new format, under development).

Sibling to geodb_etl.mappings.ags — see that package's docstring for the
shared, format-agnostic contract (geodb_etl.mappings.types) both rely on.

This is the JSON counterpart of geodb/python/docs/ags-etl-mapping.md's AGS4
mapping design (Task 4), grounded against the real schema artefact
`tasks/cpt_silver.schema.json` ($id "urn:ags4+f:cone_penetration_test:1.0")
rather than invented field names. Narrative rationale lives in
geodb/python/docs/json-etl-mapping.md.
"""

from __future__ import annotations

from ..types import FieldMapping, SourceFormat

# One JSON document -> one geotech.exploratory_hole row (the CPT test
# location). Unlike AGS's LOCA, this document has no coordinate_system field
# at all (see COORDINATE_SYSTEM_GAP) and no project/site_investigation
# identity either (see SITE_INVESTIGATION_RESOLUTION) — both resolved
# per-run, the same pattern geodb_etl.mappings.ags.loca already established.
LOCATION_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="contractor_location_id",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.exploratory_hole",
        target_column="contractor_hole_name",
        notes="Direct equivalent of AGS LOCA_ID — free text as recorded by the contractor.",
    ),
    FieldMapping(
        source_field="eastings",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.exploratory_hole",
        target_column="actual_easting_m",
        notes=(
            "Schema's own x-units is already 'm' — no unit conversion needed "
            "(contrast with AGS, where a conversion is never required for "
            "coordinates but is required for CPT trace data)."
        ),
    ),
    FieldMapping(
        source_field="northings",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.exploratory_hole",
        target_column="actual_northing_m",
    ),
    FieldMapping(
        source_field="ground_level",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.exploratory_hole",
        target_column="seabed_level_m",
        required=False,
        notes="x-units 'm', matching seabed_level_m directly.",
    ),
]

# water_depth and final_depth have no direct exploratory_hole column, same
# pattern as AGS's LOCA_FDEP (see geodb_etl.mappings.ags.loca):
# final_depth is a validation-only bound (max logged_data.depth per push
# should not exceed it); water_depth has no v1 use yet (no AGS LOCA equivalent
# was mapped either, and no downstream column currently consumes it).
LOCATION_VALIDATION_ONLY_FIELDS: list[str] = ["final_depth", "water_depth"]

# geotech.exploratory_hole.coordinate_system_id is NOT NULL, but this JSON
# format's document schema (tasks/cpt_silver.schema.json) has no
# coordinate-system/EPSG/datum field at all — a genuine gap, not an oversight
# in this mapping. AGS at least carries LOCA_EPSG/LOCA_GREF/LOCA_HDTM; this
# format carries nothing equivalent. Until the schema (still under
# development) adds one, coordinate_system_id must be supplied out of band
# (e.g. a required CLI argument, the same pattern as
# SITE_INVESTIGATION_RESOLUTION below) rather than guessed or defaulted.
COORDINATE_SYSTEM_GAP = (
    "tasks/cpt_silver.schema.json has no coordinate-system/EPSG/datum field "
    "at all (unlike AGS's LOCA_EPSG/LOCA_GREF/LOCA_HDTM). "
    "geotech.exploratory_hole.coordinate_system_id is NOT NULL, so this must "
    "be supplied out of band (e.g. a required CLI argument or a per-project "
    "default) until/unless the schema is revised to carry one — never "
    "silently defaulted, per the same reject-don't-default rule as AGS's "
    "COORDINATE_SYSTEM_RESOLUTION."
)

# Same resolution pattern as AGS (geodb_etl.mappings.ags.loca's
# SITE_INVESTIGATION_RESOLUTION): this JSON document carries no project or
# site_investigation identity at all (not even an unresolved PROJ-equivalent
# group like AGS has) — project/site_investigation must be supplied entirely
# out of band per pipeline run.
SITE_INVESTIGATION_RESOLUTION = (
    "This JSON format has no project or site_investigation identity field "
    "anywhere in the document (not even an unresolved PROJ-style group, "
    "unlike AGS) — project_id, si_name and survey_phase_code must all be "
    "supplied as required CLI arguments per pipeline run, the same pattern "
    "as geodb_etl.mappings.ags.loca.SITE_INVESTIGATION_RESOLUTION. All "
    "exploratory_hole rows from one JSON document resolve to the same "
    "site_investigation_id."
)

# One JSON document -> one geotech.in_situ_test + one geotech.cpt_test row
# (test/location-level metadata) — NOT one per push (contrast with AGS's
# SCPG, which has no document-level wrapper and models one push as one
# in_situ_test; see geodb_etl.mappings.ags.cpt's module docstring). This is a
# genuine, deliberate structural difference between the two formats' target
# shapes, not an inconsistency to "fix" — the JSON schema's "pushes" object
# already groups multiple pushes under one location-level test document,
# which maps naturally onto geoCore's own in_situ_test (1) -> cpt_push (N)
# shape.
TEST_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field=None,
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.in_situ_test",
        target_column="test_reference",
        notes=(
            "Synthesized from contractor_location_id (no separate test-level "
            "reference exists in the schema) — one in_situ_test per document."
        ),
    ),
    FieldMapping(
        source_field="test_mode",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_test",
        target_column="cpt_test_mode_code",
        notes=(
            "Direct copy, not a lookup: the schema's enum ['seabed', "
            "'downhole'] is identical to reference.cpt_test_mode's seed "
            "codes (geodb/sql/170__reference_cpt_enums.sql) — unlike AGS's "
            "LOCA_TYPE, no synonym-list resolution is needed."
        ),
    ),
    FieldMapping(
        source_field="test_status",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_test",
        target_column="cpt_test_status_code",
        required=False,
        notes="Direct copy — enum ['APPROVED', 'PRELIMINARY'] matches reference.cpt_test_status.",
    ),
    FieldMapping(
        source_field="test_method",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_test",
        target_column="test_method",
        required=False,
    ),
    FieldMapping(
        source_field="test_accreditation",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_test",
        target_column="test_accreditation",
        required=False,
    ),
    FieldMapping(
        source_field="test_contractor",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_test",
        target_column="test_contractor",
        required=False,
    ),
    FieldMapping(
        source_field="test_conditions",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_test",
        target_column="test_conditions",
        required=False,
    ),
    FieldMapping(
        source_field="test_deviations",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_test",
        target_column="test_deviations",
        required=False,
    ),
    FieldMapping(
        source_field="vessel",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_test",
        target_column="vessel",
        required=False,
    ),
    FieldMapping(
        source_field="metadata.schema_id",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_test",
        target_column="schema_id",
        required=False,
        notes=(
            "cpt_test.schema_id/compiled_at/compiled_by/validation_status/"
            "notes exist specifically to mirror this schema's metadata block."
        ),
    ),
    FieldMapping(
        source_field="metadata.compiled_at",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_test",
        target_column="compiled_at",
        required=False,
    ),
    FieldMapping(
        source_field="metadata.compiled_by",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_test",
        target_column="compiled_by",
        required=False,
    ),
    FieldMapping(
        source_field="metadata.validation_status",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_test",
        target_column="validation_status",
        required=False,
    ),
    FieldMapping(
        source_field="metadata.notes",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_test",
        target_column="notes",
        required=False,
    ),
]

# pushes.<key> -> geotech.cpt_push, one row per key in the "pushes" object.
# The object key itself is the push identifier (no separate reference field
# exists at this level in the schema).
PUSH_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="pushes.<key>",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_push",
        target_column="push_reference",
        notes="The object key under 'pushes' is the push identifier itself, not a nested field.",
    ),
    FieldMapping(
        source_field="pushes.<key>.test_date",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_push",
        target_column="test_date",
        required=False,
    ),
    FieldMapping(
        source_field="pushes.<key>.cone_type",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_push",
        target_column="cone_type",
        required=False,
    ),
    FieldMapping(
        source_field="pushes.<key>.pre_drilled_depth",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_push",
        target_column="pre_drilled_depth_m",
        required=False,
        notes="x-units 'm', matching pre_drilled_depth_m directly.",
    ),
    FieldMapping(
        source_field="pushes.<key>.nominal_penetration_rate",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_push",
        target_column="nominal_penetration_rate_m_s",
        required=False,
        notes=(
            "x-units 'm/s', matching nominal_penetration_rate_m_s directly — "
            "no conversion needed, unlike AGS's SCPG_RATE (mm/s) which is a "
            "known v1 gap (see geodb_etl.mappings.ags.cpt.CPT_UNIT_CONVERSION_GAP)."
        ),
    ),
    FieldMapping(
        source_field="pushes.<key>.cross_sectional_area",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_push",
        target_column="cross_sectional_area_m2",
        required=False,
        notes=(
            "x-units 'm^2', matching cross_sectional_area_m2 directly — no "
            "conversion needed, unlike AGS's SCPG_CSA (cm2) gap."
        ),
    ),
    FieldMapping(
        source_field="pushes.<key>.cone_reference",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_push",
        target_column="cone_reference",
        required=False,
    ),
    FieldMapping(
        source_field="pushes.<key>.cone_manufacturer",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_push",
        target_column="cone_manufacturer",
        required=False,
    ),
    FieldMapping(
        source_field="pushes.<key>.calibration_date",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_push",
        target_column="calibration_date",
        required=False,
    ),
    FieldMapping(
        source_field="pushes.<key>.zero_location",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_push",
        target_column="zero_location_code",
        required=False,
        notes="Direct copy — enum ['BB', 'S', 'SB'] matches reference.cpt_zero_location exactly.",
    ),
    FieldMapping(
        source_field="pushes.<key>.termination",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_push",
        target_column="termination",
        required=False,
    ),
    FieldMapping(
        source_field="pushes.<key>.test_category",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_push",
        target_column="test_category_code",
        required=False,
        notes="Direct copy — enum matches reference.cpt_test_category exactly.",
    ),
    FieldMapping(
        source_field="pushes.<key>.load_cell_arrangement",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_push",
        target_column="load_cell_arrangement_code",
        required=False,
        notes="Direct copy — enum ['CC', 'SC', 'TC'] matches reference.cpt_load_cell_arrangement.",
    ),
]

# pushes.<key>.logged_data -> geotech.cpt_logged_data, one row per push.
# Same structured NUMERIC[] array shape as AGS's SCPT mapping (see
# geodb_etl.mappings.ags.cpt) — but every array here is already in the
# schema's declared x-units, which match geoCore's stored SI units exactly
# (Pa, m, m/s, rad, s, N, degC — see geodb/sql/200__geotech_cpt_logged_data.sql's
# comment "All physical quantities in SI base units"). No unit conversion is
# required anywhere in this mapping, unlike AGS's MPa->Pa conversions.
LOGGED_DATA_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="pushes.<key>.logged_data.depth",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="depth_m",
        notes=(
            "Required array; must be strictly increasing within a push "
            "(see LOGGED_DATA_DEPTH_CONSISTENCY)."
        ),
    ),
    FieldMapping(
        source_field="pushes.<key>.logged_data.cone_resistance",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="cone_resistance_pa",
        notes="x-units already 'Pa' — no conversion needed (contrast with AGS's SCPT_RES).",
    ),
    FieldMapping(
        source_field="pushes.<key>.logged_data.sleeve_friction",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="sleeve_friction_pa",
        notes="x-units already 'Pa' — no conversion needed.",
    ),
    FieldMapping(
        source_field="pushes.<key>.logged_data.pore_pressure_u1",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="pore_pressure_u1_pa",
        required=False,
        notes="x-units already 'Pa' — no conversion needed.",
    ),
    FieldMapping(
        source_field="pushes.<key>.logged_data.pore_pressure_u2",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="pore_pressure_u2_pa",
        required=False,
        notes="x-units already 'Pa' — no conversion needed.",
    ),
    FieldMapping(
        source_field="pushes.<key>.logged_data.pore_pressure_u3",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="pore_pressure_u3_pa",
        required=False,
        notes=(
            "No AGS v1 equivalent at all (AGS's SCPT has no u3 heading) — "
            "cpt_logged_data.pore_pressure_u3_pa exists specifically for "
            "this JSON format's u3_transducer support."
        ),
    ),
    FieldMapping(
        source_field="pushes.<key>.logged_data.record_index",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="record_index",
        required=False,
    ),
    FieldMapping(
        source_field="pushes.<key>.logged_data.penetration_length",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="penetration_length_m",
        required=False,
    ),
    FieldMapping(
        source_field="pushes.<key>.logged_data.inclination_x",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="inclination_x_rad",
        required=False,
        notes=(
            "x-units 'radians' (x-display is degrees, but the stored value "
            "is already radians) — matches inclination_x_rad."
        ),
    ),
    FieldMapping(
        source_field="pushes.<key>.logged_data.inclination_y",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="inclination_y_rad",
        required=False,
    ),
    FieldMapping(
        source_field="pushes.<key>.logged_data.datetime",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="datetime",
        required=False,
    ),
    FieldMapping(
        source_field="pushes.<key>.logged_data.elapsed_time",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="elapsed_time_s",
        required=False,
    ),
    FieldMapping(
        source_field="pushes.<key>.logged_data.total_thrust",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="total_thrust_n",
        required=False,
        notes="x-units already 'N' (x-display is kN) — matches total_thrust_n.",
    ),
    FieldMapping(
        source_field="pushes.<key>.logged_data.soil_temperature",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="soil_temperature_c",
        required=False,
    ),
    FieldMapping(
        source_field="pushes.<key>.logged_data.tip_temperature",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="tip_temperature_c",
        required=False,
    ),
    FieldMapping(
        source_field="pushes.<key>.logged_data.sleeve_temperature",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="sleeve_temperature_c",
        required=False,
    ),
    FieldMapping(
        source_field="pushes.<key>.logged_data.pwp_temperature",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_logged_data",
        target_column="pwp_temperature_c",
        required=False,
    ),
]

# pushes.<key>.seismic_data -> geotech.cpt_seismic_data, optional, one row per
# push. No AGS v1 equivalent at all — AGS's SCPT/SCPG mapping (Task 4) never
# targeted cpt_seismic_data, so this is new schema coverage this JSON format
# adds, not a re-mapping of an existing AGS field.
SEISMIC_DATA_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="pushes.<key>.seismic_data.depth",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_seismic_data",
        target_column="depth_m",
    ),
    FieldMapping(
        source_field="pushes.<key>.seismic_data.shear_wave_velocity",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_seismic_data",
        target_column="shear_wave_velocity_m_s",
    ),
    FieldMapping(
        source_field="pushes.<key>.seismic_data.seismic_receiver",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_seismic_data",
        target_column="seismic_receiver",
        required=False,
        notes="Direct copy — enum ['X', 'Y', 'A', null] matches reference.cpt_seismic_receiver.",
    ),
    FieldMapping(
        source_field="pushes.<key>.seismic_data.hammer_direction",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_seismic_data",
        target_column="hammer_direction",
        required=False,
        notes="Direct copy — enum matches reference.cpt_hammer_direction exactly.",
    ),
    FieldMapping(
        source_field="pushes.<key>.seismic_data.interval_method",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_seismic_data",
        target_column="interval_method",
        required=False,
        notes=(
            "Known schema data-quality quirk: tasks/cpt_silver.schema.json's "
            "own enum lists both 'TRUE' and 'True' as distinct values (a "
            "case-variant duplicate, not two real values) — see "
            "INTERVAL_METHOD_CASE_QUIRK. reference.cpt_seismic_interval_method "
            "only seeds the uppercase 'TRUE'; case must be normalized at "
            "validate/transform time, not copied verbatim."
        ),
    ),
    FieldMapping(
        source_field="pushes.<key>.seismic_data.confidence_interval",
        source_format=SourceFormat.CPT_JSON,
        target_table="geotech.cpt_seismic_data",
        target_column="confidence_interval",
        required=False,
    ),
]

# The four tables a single JSON document (one location, one test, N pushes)
# populates, in FK dependency order. Same shape as AGS's CPT_TABLE_CHAIN
# (geodb_etl.mappings.ags.cpt) — reused verbatim by the load stage regardless
# of source format, since both formats target the identical geoCore chain.
CPT_JSON_TABLE_CHAIN: list[str] = [
    "geotech.in_situ_test",
    "geotech.cpt_test",
    "geotech.cpt_push",
    "geotech.cpt_logged_data",
]

# cpt_seismic_data is optional (only present if seismic_data was supplied for
# a push) and 1:1 with cpt_push, same as cpt_logged_data — not part of the
# required chain above since a push with no seismic geophones has none.
CPT_JSON_OPTIONAL_TABLES: list[str] = ["geotech.cpt_seismic_data"]

LOGGED_DATA_DEPTH_CONSISTENCY = (
    "pushes.<key>.logged_data.depth must be strictly increasing within one "
    "push — same rule as AGS's SCPT_DEPTH_CONSISTENCY (a non-increasing step "
    "is a RejectedRow, never silently sorted/de-duplicated). All arrays "
    "under one push's logged_data must be the same length as depth, matching "
    "geotech.cpt_logged_data's own CHECK constraints exactly (this schema's "
    "'additionalProperties: false' plus per-array 'items' typing gives "
    "syntactic validation a head start AGS's flat CSV-like rows don't have, "
    "but length-equality across arrays must still be checked semantically). "
    "Where final_depth is present at the document level, a push's maximum "
    "depth exceeding it is flagged, not silently accepted — same pattern as "
    "AGS's LOCA_FDEP check."
)

INTERVAL_METHOD_CASE_QUIRK = (
    "tasks/cpt_silver.schema.json's own seismic_data.interval_method enum "
    "lists ['PSEUDO', 'TRUE', 'True', 'AVERAGE', null] — 'TRUE' and 'True' "
    "are the same value with inconsistent casing, not two distinct methods. "
    "reference.cpt_seismic_interval_method (geodb/sql/170__reference_cpt_enums.sql) "
    "only seeds the uppercase 'TRUE'. Validation must case-normalize (or "
    "reject the lowercase-mixed variant with a clear reason) rather than "
    "attempt to insert 'True' verbatim and fail with an opaque FK violation."
)








