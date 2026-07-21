"""Transform stage for pdtable exploratory-hole-input (Phase 10c, revised 2026-07-17).

Pure functions -- no I/O, no database access. Shapes here are the
load.py-verified contract: every field name and nullability matches how
``load.pdtable.exploratory_hole.load_pdtable_exploratory_hole_transform_result()``
and its ``_upsert_*()`` helpers consume them.

The load stage resolves foreign keys (project_id, coordinate_system_id,
site_investigation_id, layout_asset_id / cluster_location_id,
parent_exploratory_hole_id) itself -- none of them appear on the records
defined here.

**2026-07-17 revision (FINAL_QAQC_AUTHORITY):** ``ExploratoryHoleRecord`` now
also carries the progress/final-state fields EHS's own
``transform.xlsx.ehs.ExploratoryHoleRecord`` does (``hole_status_code``,
``target_depth_m``, ``final_depth_m``, ``termination_reason_code``,
``start_date``, ``end_date``, ``comments``, ``parent_hole_name``) --
passed through unchanged, exactly as validated. See
``mappings.pdtable.exploratory_hole``'s module docstring for why this file
now mirrors EHS's column set instead of a narrower structural-only subset.

**2026-07-20 revision (ACTUAL_POSITION_PRECEDENCE):** also carries
``actual_easting_m``/``actual_northing_m``/``seabed_level_m``, passed
through unchanged. The load stage decides whether to use the file's
actual_easting_m/actual_northing_m verbatim or fall back to echoing the
resolved link target's design position (see
``mappings.pdtable.exploratory_hole.ACTUAL_POSITION_PRECEDENCE``) -- this
stage does no such branching, it is a pure 1:1 passthrough like every other
field here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ...validate.pdtable.exploratory_hole import ValidatedPdtableExploratoryHoleDocument


@dataclass(frozen=True)
class ClusterLocationRecord:
    """geotech.cluster_location upsert shape (one per cluster_details row)."""

    cluster_name: str
    survey_phase_code: str
    eastings_m: float
    northings_m: float
    ground_level_m: float | None = None
    water_level_m: float | None = None
    comments: str | None = None


@dataclass(frozen=True)
class ExploratoryHoleRecord:
    """geotech.exploratory_hole upsert shape (one per exploratory_hole_details row).

    ``asset_or_cluster_name`` is deliberately kept as a plain, OPTIONAL string
    here -- the load stage does the two-namespace resolution (see
    ``mappings.pdtable.exploratory_hole.ASSET_OR_CLUSTER_RESOLUTION``), and
    ``None`` means a genuinely STANDALONE hole (no asset/cluster link at
    all -- all three FK columns left NULL). ``parent_hole_name`` is likewise
    a plain string (the raw "bumpover_parent_hole" cell) -- resolved to
    ``parent_exploratory_hole_id`` by the load stage (see
    ``BUMPOVER_PARENT_HOLE_RESOLUTION``).
    """

    contractor_hole_name: str
    site_investigation_reference: str
    hole_type_code: str
    asset_or_cluster_name: str | None
    hole_status_code: str
    hole_number: str | None = None
    leg_label: str | None = None
    bumpover_label: str | None = None
    parent_hole_name: str | None = None
    target_depth_m: float | None = None
    final_depth_m: float | None = None
    termination_reason_code: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    actual_easting_m: float | None = None
    actual_northing_m: float | None = None
    seabed_level_m: float | None = None
    comments: str | None = None


@dataclass(frozen=True)
class PdtableExploratoryHoleTransformResult:
    """Full transform result for one input_exploratory_holes_{area_code}.csv."""

    project_code: str
    cluster_details: list[ClusterLocationRecord] = field(default_factory=list)
    exploratory_holes: list[ExploratoryHoleRecord] = field(default_factory=list)


def transform_pdtable_exploratory_hole_document(
    document: ValidatedPdtableExploratoryHoleDocument,
) -> PdtableExploratoryHoleTransformResult:
    """Map a ``ValidatedPdtableExploratoryHoleDocument`` onto load-ready records.

    Pure 1:1 mapping only -- coordinate_system_id, project_id,
    site_investigation_id, asset/cluster resolution, and
    parent_exploratory_hole_id resolution are deferred to load.py (they
    require database access).
    """

    cluster_details = [
        ClusterLocationRecord(
            cluster_name=entry.cluster_name,
            survey_phase_code=entry.survey_phase_code,
            eastings_m=entry.eastings_m,
            northings_m=entry.northings_m,
            ground_level_m=entry.ground_level_m,
            water_level_m=entry.water_level_m,
            comments=entry.comments,
        )
        for entry in document.cluster_details
    ]

    exploratory_holes = [
        ExploratoryHoleRecord(
            contractor_hole_name=hole.contractor_hole_name,
            site_investigation_reference=hole.site_investigation_reference,
            hole_type_code=hole.hole_type_code,
            asset_or_cluster_name=hole.asset_or_cluster_name,
            hole_status_code=hole.hole_status_code,
            hole_number=hole.hole_number,
            leg_label=hole.leg_label,
            bumpover_label=hole.bumpover_label,
            parent_hole_name=hole.parent_hole_name,
            target_depth_m=hole.target_depth_m,
            final_depth_m=hole.final_depth_m,
            termination_reason_code=hole.termination_reason_code,
            start_date=hole.start_date,
            end_date=hole.end_date,
            actual_easting_m=hole.actual_easting_m,
            actual_northing_m=hole.actual_northing_m,
            seabed_level_m=hole.seabed_level_m,
            comments=hole.comments,
        )
        for hole in document.exploratory_holes
    ]

    return PdtableExploratoryHoleTransformResult(
        project_code=document.project_code,
        cluster_details=cluster_details,
        exploratory_holes=exploratory_holes,
    )
