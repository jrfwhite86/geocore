"""Load stage for the EHS .xlsx source format.

Moved here from the top-level `geodb_etl/load.py` per
`tasks/plan/codebase-structure-cleanup.md` -- the load stage now follows the
same `{xlsx,pdtable}/...` format-subdirectory pattern already used by
`parse/`, `validate/`, `transform/`, and `cli/`. Only the file's *location*
changed in this increment, not its behaviour.

**2026-07-15 update:** an exploratory hole's asset_or_cluster_name is now
resolved to at most one of layout_asset_id/asset_location_id/
cluster_location_id (see geotech.exploratory_hole's CHECK constraint, loosened
from "exactly one" to "at most one" to support this). Asset resolution
(layout_asset/asset_location) is lookup-only -- those rows are expected to
already exist from input_layout.csv. Cluster resolution is get-or-create: EHS
is the first document to reach geoCore for a campaign, so a referenced
cluster_name will typically not exist yet, and this pipeline creates it
rather than rejecting the row. See the "Cluster position removed" section
below for why the new row's eastings_m/northings_m are left NULL. A
blank/missing "Cluster / asset name" cell means a
genuinely standalone hole (no cluster/asset at all): all three ID columns are
left NULL, with no database lookups performed for that hole.

**2026-07-16 progress-tracking revision -- FULL-OVERWRITE upsert semantics
(confirmed user decision):** the EHS workbook is no longer a planned-only,
pre-mobilisation document -- it is re-issued across the campaign
(revision control r01, r02, ...) to report progress. Per the confirmed
decision, the most recently loaded EHS revision is the SOLE SOURCE OF TRUTH
for every mapped column on that hole: `_upsert_exploratory_hole`'s
`ON CONFLICT ... DO UPDATE SET` clause is a uniform, unconditional
`EXCLUDED.col` assignment for EVERY mapped column -- no `COALESCE`/
preserve-on-blank branching. A blank progress cell on a later revision
genuinely CLEARS a previously-recorded value, including
actual_easting_m/actual_northing_m even if originally populated by an AGS
delivery -- this reverses the format's original "never clobber actual_*"
rule (see the retired "Coordinates: planned-only" design). This raises the
correctness bar on the upstream parse/validate/transform stages: they must
never spuriously turn a genuinely populated cell into None, since there is
no safety net here.

**`survey_status_code` lock (2026-07-17 confirmed workflow):** a
`geotech.site_investigation` reaches `survey_status_code = 'COMPLETE'` only
via a successful `load.pdtable.exploratory_hole` run (the QAQC'd final
snapshot -- see `geodb/sql/138__geotech_site_investigation_survey_status.sql`
for the full rationale). This pipeline checks that status immediately after
resolving/creating the `site_investigation` row and raises `LoadError`
before upserting anything if it is already `COMPLETE` -- a live EHS re-issue
must never silently overwrite a already-finalised campaign. A freshly
created `site_investigation` row is always `ACTIVE` (the column's own
default), so this only ever rejects a re-issue against an
already-closed-out campaign.

**"Position context" soft cross-check (Task 14a, 2026-07-16):** after
resolving asset_or_cluster_name to at most one of layout_asset_id/
asset_location_id/cluster_location_id, this module computes what
position_context_code the DB's own GENERATED ALWAYS column would produce
(see geodb/sql/120__geotech_site_investigation.sql) and compares it against
the workbook's own "Position context" cell (read through unvalidated by the
validate stage -- see mappings.xlsx.ehs.POSITION_CONTEXT_CROSS_CHECK_ONLY).
A mismatch produces a WARNING (EhsLoadResult.warnings), never a rejection --
the hole still loads normally either way, since the resolved association is
always authoritative, not the human-entered column.

**Bumpover parent hole resolution (2026-07-16 second revision):** a row's
"Bumpover parent hole" (validated to a raw contractor_hole_name string,
ExploratoryHoleRecord.parent_hole_name) is resolved here to
parent_exploratory_hole_id via a lookup scoped to the same
site_investigation_id (see geodb/sql/134__geotech_exploratory_hole_bumpover.sql).
Because rows are upserted in file order and the lookup queries the live
table (not an in-file cache), a parent hole listed EARLIER in the same file
resolves correctly even on a first load. Per the confirmed 2026-07-16
decision, an UNRESOLVABLE name (typo, wrong load order -- parent listed
later in the file or not loaded at all, parent not yet loaded in an earlier
file) does NOT fail the row: it loads with parent_exploratory_hole_id = NULL
and a WARNING (EhsLoadResult.warnings), reusing the exact flag-don't-block
mechanism built for the Position-context cross-check above.

**Cluster position removed from this mapping (2026-07-16 third revision):**
this pipeline previously populated a newly-created geotech.cluster_location
row's eastings_m/northings_m from the referencing hole's own planned
position. That was wrong -- a cluster's home position is not something EHS
is authoritative for, and is instead supplied by a separate input file that
does not yet exist. `_get_or_create_cluster_location` no longer inserts
eastings_m/northings_m at all (both left NULL); see
geodb/sql/136__geotech_cluster_location_nullable_coords.sql, which relaxes
those columns from NOT NULL to support this.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...transform.xlsx import EhsTransformResult, ExploratoryHoleRecord, SiteInvestigationRecord
from .. import LoadError


@dataclass(frozen=True)
class EhsLoadResult:
    site_investigation_id: int
    exploratory_hole_ids: list[int]
    warnings: list[str] = field(default_factory=list)


def load_ehs_transform_result(
    result: EhsTransformResult, connection: Any
) -> EhsLoadResult:
    """Load an EhsTransformResult into geoCore within one transaction.

    Args:
        result: The output of geodb_etl.transform.xlsx.transform_ehs_document.
        connection: A psycopg.Connection (or, in tests, anything satisfying
            the same cursor()/commit()/rollback() protocol — this repo's
            "local DB deferred" decision means unit tests use a mock here,
            never a live database).

    Returns:
        The resolved/created site_investigation_id, one exploratory_hole_id
        per loaded hole (in the same order as result.exploratory_holes), and
        any non-blocking "Position context" mismatch warnings (see the
        module docstring's Task 14a section) -- every hole still loads
        regardless of whether it produced a warning.

    Raises:
        LoadError: --project-code doesn't match any project.project row, an
            EHS header's EPSG code doesn't match any
            reference.coordinate_system row, or the resolved
            site_investigation's survey_status_code is already 'COMPLETE'
            (see the module docstring's "survey_status_code lock" section).
            Any other failure (e.g. a genuine constraint violation this
            pipeline didn't anticipate) rolls back the transaction and
            re-raises unchanged — this is a deliberate transaction-boundary
            exception handler (rollback, then re-raise), not a swallowed
            error.
    """

    cursor = connection.cursor()
    try:
        project_id = _resolve_project_id(cursor, result.site_investigation.project_code)
        site_investigation_id = _get_or_create_site_investigation(
            cursor, project_id, result.site_investigation
        )
        _check_survey_status_not_locked(cursor, site_investigation_id)

        coordinate_system_id_by_epsg: dict[int, int] = {}
        cluster_location_ids: dict[str, int] = {}
        exploratory_hole_ids: list[int] = []
        warnings: list[str] = []
        for hole in result.exploratory_holes:
            if hole.coordinate_system_epsg not in coordinate_system_id_by_epsg:
                coordinate_system_id_by_epsg[hole.coordinate_system_epsg] = (
                    _resolve_coordinate_system_id(cursor, hole.coordinate_system_epsg)
                )
            hole_id, hole_warnings = _upsert_exploratory_hole(
                cursor,
                project_id,
                site_investigation_id,
                result.site_investigation.survey_phase_code,
                hole,
                coordinate_system_id_by_epsg[hole.coordinate_system_epsg],
                cluster_location_ids,
            )
            exploratory_hole_ids.append(hole_id)
            warnings.extend(hole_warnings)
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

    return EhsLoadResult(
        site_investigation_id=site_investigation_id,
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
            f"--project-code {project_code!r} does not match any project.project row -- "
            "this pipeline never creates a project, only loads into an existing one "
            "(see geodb_etl.mappings.ags.proj.PROJECT_RESOLUTION)."
        )
    return row[0]


def _resolve_coordinate_system_id(cursor: Any, epsg_code: int) -> int:
    cursor.execute(
        "SELECT coordinate_system_id FROM reference.coordinate_system "
        "WHERE epsg_code_horizontal = %s",
        (epsg_code,),
    )
    row = cursor.fetchone()
    if row is None:
        raise LoadError(
            f"EHS header's 'Horizontal CRS (EPSG)' resolved to EPSG:{epsg_code}, which "
            "does not match any reference.coordinate_system.epsg_code_horizontal row."
        )
    return row[0]


def _get_or_create_site_investigation(
    cursor: Any, project_id: int, record: SiteInvestigationRecord
) -> int:
    """Get-or-create, never update — see mappings.xlsx.ehs.SITE_INVESTIGATION_AUTHORITY:
    once created from EHS data, si_name/survey_phase_code/contractor are not
    silently overwritten by a re-run of the same (or a revised) EHS file.
    """

    cursor.execute(
        "SELECT site_investigation_id FROM geotech.site_investigation "
        "WHERE project_id = %s AND si_name = %s",
        (project_id, record.si_name),
    )
    row = cursor.fetchone()
    if row is not None:
        return row[0]

    cursor.execute(
        "INSERT INTO geotech.site_investigation "
        "(project_id, si_name, survey_phase_code, contractor) "
        "VALUES (%s, %s, %s, %s) RETURNING site_investigation_id",
        (project_id, record.si_name, record.survey_phase_code, record.contractor),
    )
    return cursor.fetchone()[0]


def _check_survey_status_not_locked(cursor: Any, site_investigation_id: int) -> None:
    """Refuse to load any hole for an already-'COMPLETE' site_investigation.

    See geodb/sql/138__geotech_site_investigation_survey_status.sql and this
    module's docstring's "survey_status_code lock" section: 'COMPLETE' is set
    exclusively by load.pdtable.exploratory_hole's QAQC'd final push, and once
    set, a further EHS re-issue for the same campaign must be rejected outright
    rather than silently un-finalising it.
    """

    cursor.execute(
        "SELECT survey_status_code FROM geotech.site_investigation "
        "WHERE site_investigation_id = %s",
        (site_investigation_id,),
    )
    row = cursor.fetchone()
    if row is not None and row[0] == "COMPLETE":
        raise LoadError(
            f"site_investigation_id {site_investigation_id} is already "
            "survey_status_code 'COMPLETE' -- the final, QAQC'd snapshot has "
            "already been pushed via input_exploratory_holes_{area_code}.csv. "
            "A further EHS re-issue is refused to avoid silently un-finalising "
            "that campaign; reopening it is a deliberate manual DBA action."
        )


def _resolve_asset_or_cluster(
    cursor: Any,
    project_id: int,
    survey_phase_code: str,
    hole: ExploratoryHoleRecord,
    coordinate_system_id: int,
    cluster_location_ids: dict[str, int],
) -> tuple[int | None, int | None, int | None]:
    """Resolve asset_or_cluster_name to at most one of the three location IDs.

    A None asset_or_cluster_name means a genuinely standalone hole (no
    cluster/asset association at all -- see geotech.exploratory_hole's CHECK
    constraint, loosened 2026-07-15 from "exactly one" to "at most one" of
    layout_asset_id/asset_location_id/cluster_location_id specifically to
    support this case): all three IDs are returned as None, with no
    database lookups performed.

    EHS is (by definition) the FIRST document to reach geoCore for a
    campaign — unlike the pdtable exploratory-hole path (which requires
    clusters to be pre-declared via a **cluster_details block), no
    geotech.cluster_location row can be assumed to already exist. If a
    non-None name matches neither an existing asset nor an existing
    cluster, this function CREATES a new geotech.cluster_location row
    (get-or-create, keyed on (project_id, cluster_name)) with its
    eastings_m/northings_m left NULL -- a cluster's home position is NOT
    derived from the referencing hole's planned position (see
    _get_or_create_cluster_location's docstring); it is supplied by a
    separate, not-yet-defined input file. Asset (layout_asset/
    asset_location) resolution never creates anything: those are expected
    to pre-exist from input_layout.csv.

    Returns:
        (layout_asset_id, asset_location_id, cluster_location_id).
        At most one is non-None; all three are None for a standalone hole.
    """

    name = hole.asset_or_cluster_name
    if name is None:
        return None, None, None

    # (a) Check layout_asset in the project's current (CUR) layout first.
    cursor.execute(
        """
        SELECT la.layout_asset_id
        FROM location.asset_location al
        JOIN project.layout_asset la ON la.asset_location_id = al.asset_location_id
        JOIN project.layout l ON l.layout_id = la.layout_id
        WHERE al.project_id = %s
          AND al.internal_reference = %s
          AND l.layout_status_code = 'CUR'
        """,
        (project_id, name),
    )
    row = cursor.fetchone()
    if row is not None:
        return row[0], None, None

    # (b) Check asset_location directly.
    cursor.execute(
        """
        SELECT asset_location_id FROM location.asset_location
        WHERE project_id = %s AND internal_reference = %s
        """,
        (project_id, name),
    )
    row = cursor.fetchone()
    if row is not None:
        return None, row[0], None

    # (c) Cluster: get-or-create -- see docstring above for why EHS creates
    # (rather than merely resolves) cluster_location rows.
    cluster_location_id = _get_or_create_cluster_location(
        cursor,
        project_id,
        name,
        survey_phase_code,
        coordinate_system_id,
        cluster_location_ids,
    )
    return None, None, cluster_location_id


def _get_or_create_cluster_location(
    cursor: Any,
    project_id: int,
    cluster_name: str,
    survey_phase_code: str,
    coordinate_system_id: int,
    cluster_location_ids: dict[str, int],
) -> int:
    """Get-or-create a geotech.cluster_location row, keyed on (project_id, cluster_name).

    Checks the in-memory cache first (avoids a redundant DB round-trip for
    a cluster name repeated across multiple holes within the same file),
    then the database (a cluster from an earlier run), before creating a
    new row.

    **2026-07-16 revision:** this no longer populates eastings_m/northings_m
    from the referencing hole's planned position. A cluster's home position
    is out of scope for EHS -- it is supplied by a not-yet-defined separate
    input file, so eastings_m/northings_m are left NULL here (see
    115__geotech_cluster_location.sql / 136__geotech_cluster_location_nullable_coords.sql,
    which relaxed those columns from NOT NULL to support this). Never
    updates an already-existing row at all -- same "get-or-create, never
    update" discipline as _get_or_create_site_investigation.
    """

    if cluster_name in cluster_location_ids:
        return cluster_location_ids[cluster_name]

    cursor.execute(
        """
        SELECT cluster_location_id FROM geotech.cluster_location
        WHERE project_id = %s AND cluster_name = %s
        """,
        (project_id, cluster_name),
    )
    row = cursor.fetchone()
    if row is not None:
        cluster_location_ids[cluster_name] = row[0]
        return row[0]

    cursor.execute(
        """
        INSERT INTO geotech.cluster_location
            (project_id, cluster_name, survey_phase_code, coordinate_system_id)
        VALUES (%s, %s, %s, %s)
        RETURNING cluster_location_id
        """,
        (project_id, cluster_name, survey_phase_code, coordinate_system_id),
    )
    cluster_location_id = cursor.fetchone()[0]
    cluster_location_ids[cluster_name] = cluster_location_id
    return cluster_location_id



def _resolve_parent_hole(
    cursor: Any, site_investigation_id: int, parent_hole_name: str
) -> int | None:
    """Resolve a "Bumpover parent hole" name to parent_exploratory_hole_id.

    Scoped to the same site_investigation_id, mirroring
    _resolve_asset_or_cluster's lookup style. Returns None (never raises) if
    no matching contractor_hole_name exists yet -- per the confirmed
    2026-07-16 decision, an unresolvable name is a load-time WARNING, not a
    RejectedRow or LoadError; the caller is responsible for emitting that
    warning. Queries the live table (not an in-file cache), so a parent hole
    upserted earlier IN THIS SAME FILE (file order) is already visible here.
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
    project_id: int,
    site_investigation_id: int,
    survey_phase_code: str,
    hole: ExploratoryHoleRecord,
    coordinate_system_id: int,
    cluster_location_ids: dict[str, int],
) -> tuple[int, list[str]]:
    """Upsert matched on (site_investigation_id, contractor_hole_name).

    Resolves asset_or_cluster_name to at most one of layout_asset_id,
    asset_location_id, or cluster_location_id (per the table's CHECK
    constraint), creating a new geotech.cluster_location row if the name
    doesn't match an existing asset or cluster (see
    _resolve_asset_or_cluster's docstring); all three are left NULL for a
    standalone hole (asset_or_cluster_name is None).

    Also resolves hole.parent_hole_name (the raw "Bumpover parent hole"
    string) to parent_exploratory_hole_id via _resolve_parent_hole; an
    unresolvable name leaves the column NULL and adds a warning (see this
    module's docstring's "Bumpover parent hole resolution" section).

    **FULL-OVERWRITE upsert (2026-07-16 confirmed decision):** the UPDATE SET
    clause is a uniform, unconditional EXCLUDED.col assignment for EVERY
    mapped column -- hole_type_code, planned_easting_m/planned_northing_m,
    coordinate_system_id, the resolved asset/cluster IDs, hole_status_code,
    target_depth_m, final_depth_m, termination_reason_code,
    actual_easting_m/actual_northing_m, start_date, end_date, comments,
    bumpover_label, parent_exploratory_hole_id. No COALESCE/preserve-on-blank
    branching -- see this module's docstring for why. leg_label/
    seabed_level_m/hole_number remain untouched (never referenced here),
    since this format doesn't supply them at all -- a value in one of those
    columns from another source (e.g. an AGS delivery) is unaffected by this
    upsert.

    Returns:
        (exploratory_hole_id, warnings). warnings is a list of zero or more
        non-blocking messages -- a "Position context" mismatch (Task 14a)
        and/or an unresolvable "Bumpover parent hole" name -- the hole is
        upserted identically regardless of either warning.
    """

    layout_asset_id, asset_location_id, cluster_location_id = _resolve_asset_or_cluster(
        cursor, project_id, survey_phase_code, hole, coordinate_system_id, cluster_location_ids
    )

    parent_exploratory_hole_id: int | None = None
    warnings: list[str] = []
    if hole.parent_hole_name is not None:
        parent_exploratory_hole_id = _resolve_parent_hole(
            cursor, site_investigation_id, hole.parent_hole_name
        )
        if parent_exploratory_hole_id is None:
            warnings.append(
                f"hole '{hole.contractor_hole_name}' names 'Bumpover parent hole' "
                f"{hole.parent_hole_name!r}, which does not match any "
                "contractor_hole_name in this site investigation -- loaded with "
                "parent_exploratory_hole_id = NULL."
            )

    cursor.execute(
        """
        INSERT INTO geotech.exploratory_hole (
            site_investigation_id, layout_asset_id, asset_location_id,
            cluster_location_id, contractor_hole_name, hole_type_code,
            planned_easting_m, planned_northing_m, coordinate_system_id,
            hole_status_code, target_depth_m, final_depth_m,
            termination_reason_code, actual_easting_m, actual_northing_m,
            start_date, end_date, comments, bumpover_label,
            parent_exploratory_hole_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (site_investigation_id, contractor_hole_name) DO UPDATE SET
            layout_asset_id = EXCLUDED.layout_asset_id,
            asset_location_id = EXCLUDED.asset_location_id,
            cluster_location_id = EXCLUDED.cluster_location_id,
            hole_type_code = EXCLUDED.hole_type_code,
            planned_easting_m = EXCLUDED.planned_easting_m,
            planned_northing_m = EXCLUDED.planned_northing_m,
            coordinate_system_id = EXCLUDED.coordinate_system_id,
            hole_status_code = EXCLUDED.hole_status_code,
            target_depth_m = EXCLUDED.target_depth_m,
            final_depth_m = EXCLUDED.final_depth_m,
            termination_reason_code = EXCLUDED.termination_reason_code,
            actual_easting_m = EXCLUDED.actual_easting_m,
            actual_northing_m = EXCLUDED.actual_northing_m,
            start_date = EXCLUDED.start_date,
            end_date = EXCLUDED.end_date,
            comments = EXCLUDED.comments,
            bumpover_label = EXCLUDED.bumpover_label,
            parent_exploratory_hole_id = EXCLUDED.parent_exploratory_hole_id
        RETURNING exploratory_hole_id
        """,
        (
            site_investigation_id,
            layout_asset_id,
            asset_location_id,
            cluster_location_id,
            hole.contractor_hole_name,
            hole.hole_type_code,
            hole.planned_easting_m,
            hole.planned_northing_m,
            coordinate_system_id,
            hole.hole_status_code,
            hole.target_depth_m,
            hole.final_depth_m,
            hole.termination_reason_code,
            hole.actual_easting_m,
            hole.actual_northing_m,
            hole.start_date,
            hole.end_date,
            hole.comments,
            hole.bumpover_label,
            parent_exploratory_hole_id,
        ),
    )
    exploratory_hole_id = cursor.fetchone()[0]

    position_context_warning = _check_position_context(
        hole, layout_asset_id, asset_location_id, cluster_location_id
    )
    if position_context_warning is not None:
        warnings.append(position_context_warning)

    return exploratory_hole_id, warnings


def _resolved_position_context(
    layout_asset_id: int | None, asset_location_id: int | None, cluster_location_id: int | None
) -> str:
    """Mirrors geotech.exploratory_hole.position_context_code's own
    GENERATED ALWAYS expression exactly (see
    geodb/sql/120__geotech_site_investigation.sql) -- do not let this drift
    from that CASE expression.
    """

    if layout_asset_id is not None or asset_location_id is not None:
        return "ASSET"
    if cluster_location_id is not None:
        return "CLUSTER"
    return "STANDALONE"


def _check_position_context(
    hole: ExploratoryHoleRecord,
    layout_asset_id: int | None,
    asset_location_id: int | None,
    cluster_location_id: int | None,
) -> str | None:
    """Task 14a's soft cross-check: compare the workbook's own "Position
    context" cell against what this load actually resolved. Returns a
    warning string on a mismatch, or None if they agree (or the workbook
    cell was blank -- nothing to cross-check).
    """

    if hole.position_context is None:
        return None

    resolved = _resolved_position_context(
        layout_asset_id, asset_location_id, cluster_location_id
    )
    if hole.position_context == resolved:
        return None

    return (
        f"hole '{hole.contractor_hole_name}' resolved to position_context "
        f"{resolved!r} but workbook states {hole.position_context!r}"
    )

