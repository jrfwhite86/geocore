"""Load stage for pdtable exploratory-hole-input (Phase 10c, revised 2026-07-17).

Loads a ``PdtableExploratoryHoleTransformResult`` into geoCore within one
transaction -- the same ``cursor()/commit()/rollback()`` protocol as
``load.pdtable.layout`` and ``load.pdtable.project``. Resolves every FK
this format needs (project_id, coordinate_system_id, site_investigation_id,
exactly one of layout_asset_id / cluster_location_id per hole via the
two-namespace ``ASSET_OR_CLUSTER_RESOLUTION`` algorithm, and
parent_exploratory_hole_id for a bumpover hole) via lookup against
already-seeded/already-loaded data, raising ``LoadError`` (never a raw
IntegrityError) for anything unresolvable.

Authority (see ``mappings.pdtable.exploratory_hole.CLUSTER_LOCATION_AUTHORITY``
and ``FINAL_QAQC_AUTHORITY``): this pipeline CREATES-AND-OWNS
``geotech.cluster_location`` rows (via the ``**cluster_details`` block) AND
``geotech.exploratory_hole`` rows (via the ``**exploratory_hole_details``
block) -- as the FINAL, QAQC'd snapshot of a campaign already reported live
by the EHS xlsx pipeline (``load.xlsx.ehs``), not a second concurrently
authoritative source. Accordingly:

- ``_upsert_exploratory_hole``'s ``ON CONFLICT ... DO UPDATE SET`` is a
  uniform, unconditional ``EXCLUDED.col`` assignment for every mapped
  column, mirroring ``load.xlsx.ehs``'s own FULL-OVERWRITE discipline (no
  ``COALESCE``/preserve-on-blank branching).
- After a successful load, every touched ``site_investigation`` row has its
  ``survey_status_code`` set to ``'COMPLETE'`` (see
  ``geodb/sql/138__geotech_site_investigation_survey_status.sql``) -- this is
  the ONLY pipeline that ever sets that value, and doing so locks the
  campaign against any further ``load.xlsx.ehs`` re-issue.

Order within the transaction:

1. Resolve ``project_id`` and ``coordinate_system_id``.
2. Upsert every ``cluster_details`` row -> build a ``cluster_location_ids``
   cache. This must happen BEFORE any hole is processed so a hole
   referencing a same-file cluster resolves against the freshly-upserted
   row.
3. For every ``exploratory_hole_details`` row:
   a. Resolve ``site_investigation_id`` via
      ``(project_id, survey_phase_code)`` -- LoadError if missing or
      ambiguous (see SITE_INVESTIGATION_RESOLUTION). Unlike
      ``load.xlsx.ehs``, this pipeline does NOT reject an already-'COMPLETE'
      site_investigation -- re-running this file is expected to be
      idempotent, and this pipeline is what sets 'COMPLETE' in the first
      place.
   b. Resolve ``asset_or_cluster_name`` to at most one of
      ``(layout_asset_id, cluster_location_id)`` per
      ASSET_OR_CLUSTER_RESOLUTION -- LoadError for every failure mode
      described there. A blank ``asset_or_cluster_name`` (2026-07-20:
      now OPTIONAL) resolves both to None, producing a STANDALONE hole.
   c. Resolve the hole's ``actual_easting_m`` / ``actual_northing_m``.
      **2026-07-20 fix (ACTUAL_POSITION_PRECEDENCE):** the file's own
      ``actual_easting``/``actual_northing`` columns WIN when both are
      present -- they override both the resolved link target's design
      position and whatever the row already had in the DB (e.g. from an
      earlier EHS load). Only when the file leaves both blank does this
      pipeline fall back to echoing the resolved ``project.layout_asset``'s
      or ``geotech.cluster_location``'s own ``eastings_m``/``northings_m``
      (its DESIGN position) -- the pre-fix behaviour, now demoted to a
      fallback rather than the only source. ``LoadError`` if neither is
      available (file blank AND resolved target has no design position
      either) -- ``geotech.exploratory_hole``'s CHECK constraint requires at
      least one position pair to be set.
   d. Resolve ``parent_hole_name`` (a "bumpover_parent_hole" string) to
      ``parent_exploratory_hole_id`` -- an unresolvable name is a
      non-blocking WARNING (see ``BUMPOVER_PARENT_HOLE_RESOLUTION``), not a
      LoadError.
   e. Upsert ``geotech.exploratory_hole`` keyed on
      ``(site_investigation_id, contractor_hole_name)`` (FULL-OVERWRITE).
4. Set ``survey_status_code = 'COMPLETE'`` for every distinct
   ``site_investigation_id`` touched in step 3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...transform.pdtable.exploratory_hole import (
    ClusterLocationRecord,
    ExploratoryHoleRecord,
    PdtableExploratoryHoleTransformResult,
)
from .. import LoadError

_CURRENT_LAYOUT_STATUS_CODE = "CUR"


@dataclass(frozen=True)
class PdtableExploratoryHoleLoadResult:
    """Result of loading one input_exploratory_holes_{area_code}.csv."""

    project_id: int
    cluster_location_ids: dict[str, int] = field(default_factory=dict)
    exploratory_hole_ids: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def load_pdtable_exploratory_hole_transform_result(
    result: PdtableExploratoryHoleTransformResult, connection: Any
) -> PdtableExploratoryHoleLoadResult:
    """Load a ``PdtableExploratoryHoleTransformResult`` into geoCore in one transaction.

    Args:
        result: The output of
            ``geodb_etl.transform.pdtable.transform_pdtable_exploratory_hole_document``.
        connection: A psycopg.Connection (or, in tests, anything satisfying
            the same cursor()/commit()/rollback() protocol).

    Returns:
        See ``PdtableExploratoryHoleLoadResult``. ``warnings`` carries zero
        or more non-blocking "bumpover_parent_hole" resolution failures (see
        ``BUMPOVER_PARENT_HOLE_RESOLUTION``) -- every hole still loads
        regardless of whether it produced a warning.

    Raises:
        LoadError: ``result.project_code`` doesn't match any
            ``project.project`` row; the project has no 'ARRAY'-type
            boundary yet (input_project.csv not loaded first); a hole's
            ``site_investigation_reference`` doesn't resolve against
            ``geotech.site_investigation`` for this project (EHS xlsx not
            loaded yet, or ambiguous); a hole's non-blank
            ``asset_or_cluster_name`` matches neither
            ``location.asset_location.internal_reference`` nor
            ``geotech.cluster_location.cluster_name`` (a blank/None value
            is valid -- see ASSET_OR_CLUSTER_RESOLUTION -- and produces a
            STANDALONE hole with all three FK columns NULL); an asset match
            occurs but the project has no CUR-status layout, or more than
            one; an asset+CUR-layout match occurs but no matching
            ``project.layout_asset`` row exists for that pair. Any other
            failure rolls back the transaction and re-raises unchanged.
    """

    cursor = connection.cursor()
    try:
        project_id = _resolve_project_id(cursor, result.project_code)
        coordinate_system_id = _resolve_coordinate_system_id(cursor, project_id)

        cluster_location_ids: dict[str, int] = {}
        for cluster in result.cluster_details:
            cluster_location_ids[cluster.cluster_name] = _upsert_cluster_location(
                cursor, project_id, coordinate_system_id, cluster
            )

        exploratory_hole_ids: dict[str, int] = {}
        warnings: list[str] = []
        touched_site_investigation_ids: set[int] = set()
        for hole in result.exploratory_holes:
            site_investigation_id = _resolve_site_investigation_id(
                cursor, project_id, hole.site_investigation_reference
            )
            touched_site_investigation_ids.add(site_investigation_id)

            layout_asset_id, cluster_location_id, design_easting, design_northing = (
                _resolve_asset_or_cluster(cursor, project_id, hole, cluster_location_ids)
            )

            # ACTUAL_POSITION_PRECEDENCE (2026-07-20 fix): the file's own
            # actual_easting_m/actual_northing_m WIN when both present --
            # they override both the resolved design position AND whatever
            # value the row already had in the DB (e.g. from an earlier EHS
            # load). Only fall back to the resolved design position when the
            # file leaves both blank (validate.pdtable.exploratory_hole
            # already enforces both-or-neither on the file's own columns).
            if hole.actual_easting_m is not None and hole.actual_northing_m is not None:
                actual_e, actual_n = hole.actual_easting_m, hole.actual_northing_m
            else:
                actual_e, actual_n = design_easting, design_northing
                if actual_e is None or actual_n is None:
                    if hole.asset_or_cluster_name is None:
                        raise LoadError(
                            f"hole {hole.contractor_hole_name!r}: no position "
                            "available -- actual_easting/actual_northing are blank "
                            "in the file and this is a STANDALONE hole (no "
                            "asset_or_cluster_name), so no design position can be "
                            "resolved either. geotech.exploratory_hole's CHECK "
                            "constraint requires at least one position pair to be "
                            "set; supply actual_easting/actual_northing for this "
                            "hole."
                        )
                    raise LoadError(
                        f"hole {hole.contractor_hole_name!r}: no position available -- "
                        "actual_easting/actual_northing are blank in the file and the "
                        f"resolved link target {hole.asset_or_cluster_name!r} has no "
                        "design position either. geotech.exploratory_hole's CHECK "
                        "constraint requires at least one position pair to be set; "
                        "supply actual_easting/actual_northing for this hole or link "
                        "it to a target with a known position."
                    )

            parent_exploratory_hole_id: int | None = None
            if hole.parent_hole_name is not None:
                parent_exploratory_hole_id = _resolve_parent_hole(
                    cursor, site_investigation_id, hole.parent_hole_name
                )
                if parent_exploratory_hole_id is None:
                    warnings.append(
                        f"hole {hole.contractor_hole_name!r} names "
                        f"bumpover_parent_hole {hole.parent_hole_name!r}, which does "
                        "not match any contractor_hole_name in this site "
                        "investigation -- loaded with parent_exploratory_hole_id = NULL."
                    )

            exploratory_hole_ids[hole.contractor_hole_name] = _upsert_exploratory_hole(
                cursor,
                site_investigation_id=site_investigation_id,
                hole=hole,
                layout_asset_id=layout_asset_id,
                asset_location_id=None,
                cluster_location_id=cluster_location_id,
                parent_exploratory_hole_id=parent_exploratory_hole_id,
                actual_easting_m=actual_e,
                actual_northing_m=actual_n,
                coordinate_system_id=coordinate_system_id,
            )

        for site_investigation_id in touched_site_investigation_ids:
            _mark_survey_complete(cursor, site_investigation_id)
    except Exception:
        connection.rollback()
        raise
    else:
        try:
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    finally:
        cursor.close()

    return PdtableExploratoryHoleLoadResult(
        project_id=project_id,
        cluster_location_ids=cluster_location_ids,
        exploratory_hole_ids=exploratory_hole_ids,
        warnings=warnings,
    )


def _resolve_project_id(cursor: Any, project_code: str) -> int:
    cursor.execute(
        "SELECT project_id FROM project.project WHERE project_code = %s",
        (project_code,),
    )
    row = cursor.fetchone()
    if row is None:
        raise LoadError(
            f"input_exploratory_holes.csv's project_code {project_code!r} does not "
            "match any project.project row -- this pipeline never creates a project, "
            "only loads into an existing one (input_project.csv must be loaded first)."
        )
    return row[0]


def _resolve_coordinate_system_id(cursor: Any, project_id: int) -> int:
    """See mappings.pdtable.exploratory_hole.COORDINATE_SYSTEM_RESOLUTION."""

    cursor.execute(
        """
        SELECT b.coordinate_system_id
        FROM location.project_boundary pb
        JOIN location.boundary b ON b.boundary_id = pb.boundary_id
        WHERE pb.project_id = %s AND b.boundary_type_code = 'ARRAY'
        """,
        (project_id,),
    )
    row = cursor.fetchone()
    if row is None:
        raise LoadError(
            f"project_id {project_id} has no 'ARRAY'-type location.boundary yet -- "
            "input_project.csv must be loaded for this project before "
            "input_exploratory_holes.csv can be."
        )
    return row[0]


def _upsert_cluster_location(
    cursor: Any,
    project_id: int,
    coordinate_system_id: int,
    record: ClusterLocationRecord,
) -> int:
    """Authoritative upsert on (project_id, cluster_name) -- full column update."""

    cursor.execute(
        """
        INSERT INTO geotech.cluster_location
            (project_id, cluster_name, survey_phase_code, eastings_m, northings_m,
             ground_level_m, water_level_m, coordinate_system_id, comments)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (project_id, cluster_name) DO UPDATE SET
            survey_phase_code = EXCLUDED.survey_phase_code,
            eastings_m = EXCLUDED.eastings_m,
            northings_m = EXCLUDED.northings_m,
            ground_level_m = EXCLUDED.ground_level_m,
            water_level_m = EXCLUDED.water_level_m,
            coordinate_system_id = EXCLUDED.coordinate_system_id,
            comments = EXCLUDED.comments
        RETURNING cluster_location_id
        """,
        (
            project_id,
            record.cluster_name,
            record.survey_phase_code,
            record.eastings_m,
            record.northings_m,
            record.ground_level_m,
            record.water_level_m,
            coordinate_system_id,
            record.comments,
        ),
    )
    return cursor.fetchone()[0]


def _resolve_site_investigation_id(
    cursor: Any, project_id: int, survey_phase_code: str
) -> int:
    """See mappings.pdtable.exploratory_hole.SITE_INVESTIGATION_RESOLUTION.

    Deliberately does NOT check survey_status_code here -- unlike
    load.xlsx.ehs's one-way lock, this pipeline is what SETS 'COMPLETE' (see
    _mark_survey_complete), so re-running it against an already-COMPLETE
    site_investigation is expected and allowed (idempotent authoritative
    upsert).
    """

    cursor.execute(
        """
        SELECT site_investigation_id FROM geotech.site_investigation
        WHERE project_id = %s AND survey_phase_code = %s
        """,
        (project_id, survey_phase_code),
    )
    rows = cursor.fetchall()
    if not rows:
        raise LoadError(
            f"no geotech.site_investigation row for project_id {project_id} with "
            f"survey_phase_code {survey_phase_code!r} -- the EHS xlsx pipeline "
            "(load.xlsx.ehs) must have loaded this campaign before "
            "input_exploratory_holes.csv can be."
        )
    if len(rows) > 1:
        raise LoadError(
            f"more than one geotech.site_investigation row for project_id {project_id} "
            f"with survey_phase_code {survey_phase_code!r} -- ambiguous resolution "
            "(this should not be possible with EHS's own upsert discipline)."
        )
    return rows[0][0]


def _resolve_current_layout_id(cursor: Any, project_id: int) -> int:
    cursor.execute(
        """
        SELECT layout_id FROM project.layout
        WHERE project_id = %s AND layout_status_code = %s
        """,
        (project_id, _CURRENT_LAYOUT_STATUS_CODE),
    )
    rows = cursor.fetchall()
    if not rows:
        raise LoadError(
            f"no project.layout row with layout_status_code 'CUR' for project_id "
            f"{project_id} -- an asset-purpose exploratory hole cannot be attached "
            "until at least one real (non-placeholder) layout is loaded via "
            "input_layout.csv and promoted to CUR by input_project.csv."
        )
    if len(rows) > 1:
        raise LoadError(
            f"more than one project.layout row with layout_status_code 'CUR' for "
            f"project_id {project_id} -- ambiguous current layout (this should not "
            "be possible with input_project.csv's promotion discipline)."
        )
    return rows[0][0]


def _resolve_asset_or_cluster(
    cursor: Any,
    project_id: int,
    hole: ExploratoryHoleRecord,
    cluster_location_ids: dict[str, int],
) -> tuple[int | None, int | None, float | None, float | None]:
    """Resolve ``asset_or_cluster_name`` per ASSET_OR_CLUSTER_RESOLUTION.

    **2026-07-20 revision (STANDALONE support):** ``asset_or_cluster_name``
    is now OPTIONAL. When ``hole.asset_or_cluster_name`` is ``None`` this
    function performs no lookups at all and returns all-``None`` --
    ``layout_asset_id``/``cluster_location_id`` both stay unset, and the
    caller already always passes ``asset_location_id=None`` for this
    pipeline, so the row loads as a genuinely STANDALONE hole (mirroring
    ``load.xlsx.ehs``'s own optional ``asset_or_cluster_name`` handling).
    This aligns pdtable's own business rule with what
    ``geotech.exploratory_hole``'s CHECK constraint has permitted since the
    2026-07-15 relaxation (see 120__geotech_site_investigation.sql).

    Returns:
        (layout_asset_id, cluster_location_id, design_easting_m, design_northing_m).
        At most one of layout_asset_id and cluster_location_id is non-None
        (both None for a STANDALONE hole). The last two are the resolved
        link target's DESIGN position -- used by the caller only as a
        FALLBACK when the hole's own file-supplied actual_easting_m/
        actual_northing_m are both blank (see ACTUAL_POSITION_PRECEDENCE /
        mappings.pdtable.exploratory_hole.ACTUAL_POSITION_PRECEDENCE). This
        function itself has no knowledge of the file's actual_* columns --
        it only ever resolves the design position.
    """

    name = hole.asset_or_cluster_name
    if name is None:
        return None, None, None, None

    # (a) Asset lookup first.
    cursor.execute(
        """
        SELECT asset_location_id FROM location.asset_location
        WHERE project_id = %s AND internal_reference = %s
        """,
        (project_id, name),
    )
    row = cursor.fetchone()
    if row is not None:
        asset_location_id = row[0]
        current_layout_id = _resolve_current_layout_id(cursor, project_id)
        cursor.execute(
            """
            SELECT layout_asset_id, eastings_m, northings_m
            FROM project.layout_asset
            WHERE asset_location_id = %s AND layout_id = %s
            """,
            (asset_location_id, current_layout_id),
        )
        layout_asset_row = cursor.fetchone()
        if layout_asset_row is None:
            raise LoadError(
                f"asset_or_cluster_name {name!r} matches location.asset_location "
                f"(asset_location_id {asset_location_id}) but no project.layout_asset "
                f"row exists for that asset in the CUR-status layout "
                f"(layout_id {current_layout_id}) -- data inconsistency: the asset "
                "exists but was never loaded into the current layout's "
                "layout_configuration block."
            )
        layout_asset_id, layout_asset_easting, layout_asset_northing = layout_asset_row
        design_e = float(layout_asset_easting) if layout_asset_easting is not None else None
        design_n = float(layout_asset_northing) if layout_asset_northing is not None else None
        # Note: no LoadError here even if design_e/design_n are None -- the
        # caller only needs a design position as a FALLBACK when the file's
        # own actual_easting/actual_northing are blank (see
        # ACTUAL_POSITION_PRECEDENCE). The caller raises LoadError itself if
        # it ends up with no position at all after applying precedence.
        return layout_asset_id, None, design_e, design_n

    # (b) Cluster lookup. Prefer the in-memory map built from same-file
    # upserts (avoids a redundant DB round-trip); fall back to a DB lookup
    # for a cluster that existed from an earlier run and isn't repeated in
    # this file.
    if name in cluster_location_ids:
        cluster_location_id = cluster_location_ids[name]
        cursor.execute(
            """
            SELECT eastings_m, northings_m FROM geotech.cluster_location
            WHERE cluster_location_id = %s
            """,
            (cluster_location_id,),
        )
        row = cursor.fetchone()
        if row is None:  # pragma: no cover - defensive
            raise LoadError(
                f"internal error: freshly-upserted cluster_location_id "
                f"{cluster_location_id} disappeared before hole resolution."
            )
        design_e = float(row[0]) if row[0] is not None else None
        design_n = float(row[1]) if row[1] is not None else None
        return None, cluster_location_id, design_e, design_n

    cursor.execute(
        """
        SELECT cluster_location_id, eastings_m, northings_m
        FROM geotech.cluster_location
        WHERE project_id = %s AND cluster_name = %s
        """,
        (project_id, name),
    )
    row = cursor.fetchone()
    if row is not None:
        design_e = float(row[1]) if row[1] is not None else None
        design_n = float(row[2]) if row[2] is not None else None
        return None, row[0], design_e, design_n

    # (c) Neither.
    raise LoadError(
        f"asset_or_cluster_name {name!r} does not match any "
        "location.asset_location.internal_reference or "
        f"geotech.cluster_location.cluster_name for project_id {project_id}."
    )


def _resolve_parent_hole(
    cursor: Any, site_investigation_id: int, parent_hole_name: str
) -> int | None:
    """Resolve a "bumpover_parent_hole" name to parent_exploratory_hole_id.

    Mirrors load.xlsx.ehs._resolve_parent_hole exactly (see
    mappings.pdtable.exploratory_hole.BUMPOVER_PARENT_HOLE_RESOLUTION):
    scoped to the same site_investigation_id, returns None (never raises) if
    unresolvable -- the caller emits a non-blocking warning for that case.
    Queries the live table, so a parent hole upserted earlier IN THIS SAME
    FILE (file order) is already visible here.
    """

    cursor.execute(
        "SELECT exploratory_hole_id FROM geotech.exploratory_hole "
        "WHERE site_investigation_id = %s AND contractor_hole_name = %s",
        (site_investigation_id, parent_hole_name),
    )
    row = cursor.fetchone()
    return row[0] if row is not None else None


def _upsert_exploratory_hole(
    cursor: Any,
    *,
    site_investigation_id: int,
    hole: ExploratoryHoleRecord,
    layout_asset_id: int | None,
    asset_location_id: int | None,
    cluster_location_id: int | None,
    parent_exploratory_hole_id: int | None,
    actual_easting_m: float | None,
    actual_northing_m: float | None,
    coordinate_system_id: int,
) -> int:
    """FULL-OVERWRITE upsert (see mappings.pdtable.exploratory_hole.
    FINAL_QAQC_AUTHORITY) -- mirrors load.xlsx.ehs._upsert_exploratory_hole's
    unconditional EXCLUDED.col assignment for every mapped column."""

    cursor.execute(
        """
        INSERT INTO geotech.exploratory_hole
            (site_investigation_id, layout_asset_id, asset_location_id,
             cluster_location_id, contractor_hole_name, hole_type_code,
             hole_number, bumpover_label, parent_exploratory_hole_id, leg_label,
             hole_status_code, target_depth_m, final_depth_m,
             termination_reason_code, start_date, end_date, comments,
             actual_easting_m, actual_northing_m, seabed_level_m, coordinate_system_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (site_investigation_id, contractor_hole_name) DO UPDATE SET
            layout_asset_id = EXCLUDED.layout_asset_id,
            asset_location_id = EXCLUDED.asset_location_id,
            cluster_location_id = EXCLUDED.cluster_location_id,
            hole_type_code = EXCLUDED.hole_type_code,
            hole_number = EXCLUDED.hole_number,
            bumpover_label = EXCLUDED.bumpover_label,
            parent_exploratory_hole_id = EXCLUDED.parent_exploratory_hole_id,
            leg_label = EXCLUDED.leg_label,
            hole_status_code = EXCLUDED.hole_status_code,
            target_depth_m = EXCLUDED.target_depth_m,
            final_depth_m = EXCLUDED.final_depth_m,
            termination_reason_code = EXCLUDED.termination_reason_code,
            start_date = EXCLUDED.start_date,
            end_date = EXCLUDED.end_date,
            comments = EXCLUDED.comments,
            actual_easting_m = EXCLUDED.actual_easting_m,
            actual_northing_m = EXCLUDED.actual_northing_m,
            seabed_level_m = EXCLUDED.seabed_level_m,
            coordinate_system_id = EXCLUDED.coordinate_system_id
        RETURNING exploratory_hole_id
        """,
        (
            site_investigation_id,
            layout_asset_id,
            asset_location_id,
            cluster_location_id,
            hole.contractor_hole_name,
            hole.hole_type_code,
            hole.hole_number,
            hole.bumpover_label,
            parent_exploratory_hole_id,
            hole.leg_label,
            hole.hole_status_code,
            hole.target_depth_m,
            hole.final_depth_m,
            hole.termination_reason_code,
            hole.start_date,
            hole.end_date,
            hole.comments,
            actual_easting_m,
            actual_northing_m,
            hole.seabed_level_m,
            coordinate_system_id,
        ),
    )
    return cursor.fetchone()[0]


def _mark_survey_complete(cursor: Any, site_investigation_id: int) -> None:
    """Set survey_status_code = 'COMPLETE' (see geodb/sql/
    138__geotech_site_investigation_survey_status.sql). This is the ONLY
    pipeline that ever sets 'COMPLETE' -- doing so locks the campaign
    against any further load.xlsx.ehs re-issue."""

    cursor.execute(
        "UPDATE geotech.site_investigation SET survey_status_code = 'COMPLETE' "
        "WHERE site_investigation_id = %s",
        (site_investigation_id,),
    )
