"""Transform stage: ValidatedEhsDocument -> typed, load-ready records (Increment 4).

Pure functions only — no DB I/O, no FK resolution (that is load.py's job, a
later increment, since it needs a live connection to look up
project.project/reference.coordinate_system rows). Mirrors the shape
tasks/plan/phase-3b-pipeline-implementation.md Task 9 describes for
transform/ags.py: typed dataclasses, no raw dicts crossing the boundary.

**2026-07-16 progress-tracking revision:** ExploratoryHoleRecord now also
carries hole_status_code/target_depth_m/final_depth_m/
termination_reason_code/start_date/end_date/actual_easting_m/
actual_northing_m/comments — every field this stage receives is passed
through UNCHANGED (this stage still does no interpretation or defaulting;
that already happened in the validate stage). position_context is carried
through too, but purely for the load stage's soft cross-check (Task 14a) —
it is never itself written to any DB column.

**2026-07-16 second revision:** ExploratoryHoleRecord also carries
bumpover_label (passed through unchanged) and parent_hole_name (the raw,
unresolved "Bumpover parent hole" string) — the load stage resolves
parent_hole_name to parent_exploratory_hole_id.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ...validate.xlsx import ValidatedEhsDocument


@dataclass(frozen=True)
class SiteInvestigationRecord:
    """geotech.site_investigation, get-or-create shape (see mappings.xlsx.ehs.
    SITE_INVESTIGATION_AUTHORITY — this record's si_name is authoritative,
    not merely a cross-check value).

    project_code is the OPERATOR-supplied --project-code CLI argument, never
    the EHS header's own 'Project code' cell (see mappings.xlsx.ehs.
    PROJECT_FIELD_MAPPINGS: that header field is cross-check-only, identical
    discipline to mappings.ags.proj.PROJECT_RESOLUTION) — resolved to a
    project_id by load.py, not here.
    """

    project_code: str
    si_name: str
    survey_phase_code: str
    contractor: str | None


@dataclass(frozen=True)
class ExploratoryHoleRecord:
    """geotech.exploratory_hole, planned + progress-tracking fields shape.

    coordinate_system_epsg is resolved to a coordinate_system_id by load.py
    (a reference.coordinate_system lookup) — kept as the raw EPSG code here
    since this stage does no DB I/O. leg_label is deliberately absent — see
    mappings.xlsx.ehs's module docstring (LEG_LABEL_DEFERRED): no leg-naming
    column exists in the workbook. bumpover_label IS present (2026-07-16
    second revision, "Bumpover label" column) and parent_hole_name carries
    the raw "Bumpover parent hole" string, resolved to
    parent_exploratory_hole_id by the load stage (mirrors
    asset_or_cluster_name's resolution below) — see
    mappings.xlsx.ehs.BUMPOVER_PARENT_HOLE_RESOLUTION.

    asset_or_cluster_name is a plain string from the EHS workbook's
    "Cluster / asset name" column, or None for a genuinely standalone hole
    (no cluster/asset association at all -- see geotech.exploratory_hole's
    CHECK constraint, loosened 2026-07-15 to allow this). The load stage
    resolves a non-None value to one of layout_asset_id, asset_location_id,
    or cluster_location_id via database lookups (creating a new
    cluster_location get-or-create style if it matches neither an existing
    asset nor an existing cluster); a None value leaves all three columns
    NULL.

    **Full-overwrite semantics (2026-07-16 confirmed decision):** every
    optional field below (hole_status_code excepted, which the validate
    stage already defaults to 'SCHEDULED') is None when the workbook cell is
    blank -- the load stage's upsert then writes that None unconditionally
    on every (re-)load, clearing a previously-populated value. This is a
    deliberate reversal of the format's original "never populate actual_*"
    design; see load.xlsx.ehs's module docstring for the load-stage
    consequence.

    position_context is the raw "Position context" cell value
    (ASSET/CLUSTER/STANDALONE, or None if blank) -- carried through purely
    for the load stage's soft cross-check against the DB-resolved
    position_context_code (Task 14a); it is never itself a DB column.
    """

    contractor_hole_name: str
    hole_type_code: str
    asset_or_cluster_name: str | None
    planned_easting_m: float
    planned_northing_m: float
    coordinate_system_epsg: int
    hole_status_code: str
    target_depth_m: float | None
    final_depth_m: float | None
    termination_reason_code: str | None
    start_date: date | None
    end_date: date | None
    actual_easting_m: float | None
    actual_northing_m: float | None
    comments: str | None
    position_context: str | None
    bumpover_label: str | None
    parent_hole_name: str | None


@dataclass(frozen=True)
class EhsTransformResult:
    site_investigation: SiteInvestigationRecord
    exploratory_holes: list[ExploratoryHoleRecord]


def transform_ehs_document(
    document: ValidatedEhsDocument, *, project_code: str
) -> EhsTransformResult:
    """Turn a validated EHS document into load-ready records.

    Args:
        document: The output of geodb_etl.validate.xlsx.validate_ehs_document
            (never a raw/unvalidated EhsDocument).
        project_code: The operator's --project-code CLI argument (see
            SiteInvestigationRecord's docstring for why this is never read
            from the document's own header).
    """

    site_investigation = SiteInvestigationRecord(
        project_code=project_code,
        si_name=document.header.si_name,
        survey_phase_code=document.header.survey_phase_code,
        contractor=document.header.contractor,
    )

    exploratory_holes = [
        ExploratoryHoleRecord(
            contractor_hole_name=row.contractor_hole_name,
            hole_type_code=row.hole_type_code,
            asset_or_cluster_name=row.asset_or_cluster_name,
            planned_easting_m=row.planned_easting_m,
            planned_northing_m=row.planned_northing_m,
            coordinate_system_epsg=document.header.coordinate_system_epsg,
            hole_status_code=row.hole_status_code,
            target_depth_m=row.target_depth_m,
            final_depth_m=row.final_depth_m,
            termination_reason_code=row.termination_reason_code,
            start_date=row.start_date,
            end_date=row.end_date,
            actual_easting_m=row.actual_easting_m,
            actual_northing_m=row.actual_northing_m,
            comments=row.comments,
            position_context=row.position_context,
            bumpover_label=row.bumpover_label,
            parent_hole_name=row.parent_hole_name,
        )
        for row in document.hole_rows
    ]

    return EhsTransformResult(
        site_investigation=site_investigation, exploratory_holes=exploratory_holes
    )


