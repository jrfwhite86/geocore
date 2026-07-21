"""SCPG + SCPT -> the geotech CPT chain (tasks/plan.md Phase 3, Task 4).

See geodb/python/docs/ags-etl-mapping.md for narrative rationale.

The real target is a four-table FK chain, not one or two tables (an earlier,
external review of this plan described this as "in-situ test tables",
undercounting it — corrected here per tasks/plan.md's revision note):

    geotech.exploratory_hole (already resolved by LOCA, see loca.py)
        -> geotech.in_situ_test        (type=CPT; one row per SCPG push)
        -> geotech.cpt_test            (1:1 extension of in_situ_test)
        -> geotech.cpt_push            (one row per SCPG push)
        -> geotech.cpt_logged_data     (1:1 extension of cpt_push; SCPT arrays)

Contrast with geodb_etl.mappings.json.cpt (the newer CPT-silver JSON format):
that format models one in_situ_test + cpt_test row per *document* (a whole
CPT investigation at a location, potentially many pushes for downhole mode),
not one per push. AGS's SCPG has no concept of a document-level test wrapping
several pushes, so this mapping's simpler "one push = one in_situ_test" model
is a v1 simplification specific to AGS ingestion, not a general pipeline rule.
"""

from __future__ import annotations

from ..types import FieldMapping, UnitConversion

# SCPG -> geotech.in_situ_test (the generic parent row) + geotech.cpt_test
# (the CPT-specific 1:1 extension) + geotech.cpt_push (per-push metadata).
# in_situ_test_type_code is resolved to the fixed 'CPT'-family code, not read
# from SCPG (SCPG carries no test-type heading of its own — the group itself
# implies the type).
SCPG_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="SCPG_TESN",
        target_table="geotech.in_situ_test",
        target_column="test_reference",
        notes=(
            "Also mirrored onto cpt_push.push_reference (see below) — "
            "SCPG_TESN identifies the push."
        ),
    ),
    FieldMapping(
        source_field="SCPG_TESN",
        target_table="geotech.cpt_push",
        target_column="push_reference",
    ),
    FieldMapping(
        source_field="SCPG_CSA",
        target_table="geotech.cpt_push",
        target_column="cross_sectional_area_m2",
        unit_conversion=UnitConversion.NONE,
        required=False,
        notes=(
            "AGS unit is cm2 in the reference AGS fixture; needs a cm2->m2 "
            "conversion, not currently a named UnitConversion — flagged in "
            "the mapping doc as a v1 gap to add before Task 10 implements it."
        ),
    ),
    FieldMapping(
        source_field="SCPG_RATE",
        target_table="geotech.cpt_push",
        target_column="nominal_penetration_rate_m_s",
        required=False,
        notes=(
            "AGS unit mm/s vs. schema's m/s — needs a mm/s->m/s conversion "
            "(same v1 gap as SCPG_CSA)."
        ),
    ),
    FieldMapping(
        source_field="SCPG_TYPE",
        target_table="geotech.cpt_push",
        target_column="cone_type",
        required=False,
    ),
    FieldMapping(
        source_field="SCPG_CAR",
        target_table="geotech.cpt_push",
        target_column="cone_area_ratio",
        required=False,
        notes=(
            "Dimensionless (alpha) — no unit conversion needed. Confirmed "
            "present in the base AGS4.1.1 dictionary (not Revision E-only); "
            "added 2026-07-09 after direct comparison against "
            "geodb/sample-data/ags/reference-files/AGS4-1-1.xlsx's SCPG "
            "section surfaced this as a pre-existing v1 gap (a real "
            "dictionary heading with a matching schema column, "
            "geotech.cpt_push.cone_area_ratio, that the mapping had simply "
            "never covered)."
        ),
    ),
    FieldMapping(
        source_field="SCPG_SLAR",
        target_table="geotech.cpt_push",
        target_column="sleeve_area_ratio",
        required=False,
        notes="Dimensionless (beta) — same base-dictionary gap as SCPG_CAR above.",
    ),
    FieldMapping(
        source_field="SCPG_METH",
        target_table="geotech.cpt_test",
        target_column="test_method",
        required=False,
    ),
]

# AGS 4+ (Revision E) additions confirmed by direct comparison (2026-07-09)
# against geodb/sample-data/ags/{AGS4-1-1,AGS4+E}.xlsx's SCPG sections. These
# three headings do not exist in the public AGS4.1.1 dictionary's SCPG group
# at all — only present when AgsFileVersion.is_revision_e is True (see
# version.py). All three happen to have matching, previously-unmapped
# geotech.cpt_push columns already — a genuinely useful find, not a schema
# gap needing a migration.
SCPG_FIELD_MAPPINGS_REVISION_E_EXTRAS: list[FieldMapping] = [
    FieldMapping(
        source_field="SCPG_ZLOC",
        target_table="geotech.cpt_push",
        target_column="zero_location_code",
        required=False,
        notes=(
            "Revision E only. Direct copy, not a lookup: Revision E's own "
            "picklist ('SB'/'BB', per its DICT_UNIT PA reference) matches "
            "reference.cpt_zero_location's seed codes exactly — same "
            "'already matches, no synonym resolution needed' pattern as "
            "geodb_etl.mappings.json.cpt's zero_location field."
        ),
    ),
    FieldMapping(
        source_field="SCPG_TERM",
        target_table="geotech.cpt_push",
        target_column="termination",
        required=False,
        notes="Revision E only. Termination reason for the push.",
    ),
    FieldMapping(
        source_field="SCPG_APCL",
        target_table="geotech.cpt_push",
        target_column="application_class",
        required=False,
        notes=(
            "Revision E only. CPT application class per ISO 19901-8 — "
            "matches geotech.cpt_push.application_class exactly (the same "
            "'now obsolete, ISO 22476-1:2012' column the base schema already "
            "carries, per its own SQL comment)."
        ),
    ),
]


# SCPT -> geotech.cpt_logged_data. Parallel NUMERIC[] arrays, one row per push
# (matching geotech.cpt_logged_data's own 1:1-per-push shape) — NOT JSONB (see
# module docstring and tasks/plan.md's revision note correcting an external
# review that suggested JSONB here).
SCPT_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="SCPT_DPTH",
        target_table="geotech.cpt_logged_data",
        target_column="depth_m",
        notes=(
            "Required array; must be strictly increasing within a push "
            "(see SCPT_DEPTH_CONSISTENCY)."
        ),
    ),
    FieldMapping(
        source_field="SCPT_RES",
        target_table="geotech.cpt_logged_data",
        target_column="cone_resistance_pa",
        unit_conversion=UnitConversion.MPA_TO_PA,
        notes="AGS unit MPa (confirmed in the reference fixture's own UNIT row) -> schema's Pa.",
    ),
    FieldMapping(
        source_field="SCPT_FRES",
        target_table="geotech.cpt_logged_data",
        target_column="sleeve_friction_pa",
        unit_conversion=UnitConversion.MPA_TO_PA,
        notes="AGS unit MPa -> schema's Pa.",
    ),
    FieldMapping(
        source_field="SCPT_PWP2",
        target_table="geotech.cpt_logged_data",
        target_column="pore_pressure_u2_pa",
        unit_conversion=UnitConversion.MPA_TO_PA,
        required=False,
        notes=(
            "AGS unit MPa in the current reference fixture -> schema's Pa. "
            "A previously-used (now superseded) reference fixture recorded "
            "this same heading in kPa — exactly the 'AGS units are per-file, "
            "not fixed' problem this pipeline's unit-conversion step exists "
            "to handle. KPA_TO_PA remains available in UnitConversion for "
            "contractor files that do report it in kPa."
        ),
    ),
    FieldMapping(
        source_field="SCPT_PWP1",
        target_table="geotech.cpt_logged_data",
        target_column="pore_pressure_u1_pa",
        unit_conversion=UnitConversion.MPA_TO_PA,
        required=False,
        notes=(
            "Not present at all in the current reference fixture's SCPT "
            "HEADING row (some contractor files omit u1 entirely). Mapping "
            "kept for files that do report it; confirm unit per-file rather "
            "than assuming MPa."
        ),
    ),
    FieldMapping(
        source_field="SCPT_PWP3",
        target_table="geotech.cpt_logged_data",
        target_column="pore_pressure_u3_pa",
        unit_conversion=UnitConversion.MPA_TO_PA,
        required=False,
        notes=(
            "Confirmed present in the BASE AGS4.1.1 dictionary (not "
            "Revision E-only) — added 2026-07-09 after direct comparison "
            "surfaced this as a pre-existing v1 gap: geotech.cpt_logged_data."
            "pore_pressure_u3_pa already exists (originally added for "
            "geodb_etl.mappings.json.cpt's u3_transducer support) but no AGS "
            "mapping targeted it. Not present in the reference Gardline "
            "fixture's own SCPT HEADING row, same as SCPT_PWP1 above."
        ),
    ),
]

# AGS 4+ (Revision E) adds a per-record SCPT_RATE heading (penetration rate
# at each depth point) with NO equivalent in the public AGS4.1.1 dictionary's
# SCPT group at all (confirmed 2026-07-09 by direct comparison against
# geodb/sample-data/ags/{AGS4-1-1,AGS4+E}.xlsx) — the base dictionary only
# has SCPG_RATE, a single nominal rate per whole push, not per depth record.
# Unlike SCPG_ZLOC/SCPG_TERM/SCPG_APCL above, geotech.cpt_logged_data has NO
# column for a per-record rate array — this is a genuine schema gap, not
# just an unmapped-but-already-supported heading, so it is NOT added as a
# FieldMapping (there is no target column to point it at yet).
SCPT_RATE_REVISION_E_GAP = (
    "AGS 4+ (Revision E)'s SCPT group adds SCPT_RATE (per-depth-record "
    "penetration rate, mm/s) with no equivalent in the public AGS4.1.1 "
    "dictionary (which only has SCPG_RATE — one nominal rate per whole "
    "push). geotech.cpt_logged_data has no per-record rate array column "
    "(unlike SCPG_ZLOC/SCPG_TERM/SCPG_APCL, which matched existing "
    "geotech.cpt_push columns) — this is a genuine schema gap requiring a "
    "migration decision (a new NUMERIC[] column, e.g. "
    "penetration_rate_m_s, with the same array-length CHECK pattern as "
    "depth_m/cone_resistance_pa), not just a missing FieldMapping. Tracked "
    "here rather than silently dropped or force-mapped to an unrelated "
    "column; not resolved in this pass."
)

# The four tables a single SCPG+SCPT push populates, in FK dependency order.
# Declared as data so Task 10's load stage inserts in an order that never
# forward-references a not-yet-created row.
CPT_TABLE_CHAIN: list[str] = [
    "geotech.in_situ_test",
    "geotech.cpt_test",
    "geotech.cpt_push",
    "geotech.cpt_logged_data",
]

SCPT_DEPTH_CONSISTENCY = (
    "SCPT_DPTH must be strictly increasing within one push (a non-increasing "
    "step is a RejectedRow, Task 8 — not silently sorted or de-duplicated). "
    "All arrays mapped from SCPT (depth_m, cone_resistance_pa, "
    "sleeve_friction_pa, pore_pressure_u1_pa/u2_pa) must end up the same "
    "length per push, matching geotech.cpt_logged_data's own CHECK "
    "constraints — a length mismatch is a validation failure (Task 8), never "
    "a constraint violation surfacing from the database. Where LOCA_FDEP "
    "(final hole depth, see loca.py) is present, the push's maximum SCPT_DPTH "
    "should not exceed it; a violation is flagged, not silently accepted."
)

CPT_UNIT_CONVERSION_GAP = (
    "SCPG_CSA (cm2) and SCPG_RATE (mm/s) need unit conversions that are not "
    "yet named UnitConversion members (only MPA_TO_PA and KPA_TO_PA exist so "
    "far, covering the SCPT trace columns actually needed for v1's core "
    "depth/qc/fs/u2 series). Adding CM2_TO_M2 and MM_S_TO_M_S is deferred to "
    "Task 10 (implementation), tracked here so it isn't forgotten — SCPG_CSA/"
    "SCPG_RATE are marked required=False in the meantime since they are "
    "push metadata, not required for the core trace data. Note: this gap is "
    "AGS-specific — geodb_etl.mappings.json.cpt's equivalent fields are "
    "already stored in m2/(m/s), needing no conversion at all."
)




