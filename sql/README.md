# geodb SQL schema

PostgreSQL DDL + reference/seed data for the `geodb` geotechnical database schema.
This schema is **AGS-agnostic by design** — see `docs/architecture-review.md` and
`tasks/pixi-plan.md`'s sibling planning doc `tasks/plan.md` for why: AGS4 is an
*ingestion format*, handled by a separate ETL/ELT pipeline (not yet implemented),
not a template for table/column names here.

This directory is a faithful, numbered-migration-file split of the prototype at
`tasks/geocore.sql`, produced by `tasks/plan.md` Phase 1 (Tasks 1–2) and
`tasks/todo.md`.

## Layout and numbering

Files are named `NNN__description.sql` and must be applied **in ascending
numeric order** — a lower-numbered file never depends on a higher-numbered one
(no forward references). Gaps in the numbering (e.g. 001, 010, 020, ...) are
deliberate, leaving room to insert a file later without renumbering everything.

| File | Schema(s) touched | Depends on |
|---|---|---|
| `001__schemas.sql` | `reference`, `location`, `project`, `geotech` (CREATE SCHEMA) | — |
| `010__reference_geography.sql` | `reference.{country,region,sea_area}` | 001 |
| `020__reference_project_enums.sql` | `reference.{foundation_type,project_status}` | 001 |
| `030__location_development_area.sql` | `location.development_area` | 010 |
| `040__project_project.sql` | `project.project` | 020, 030 |
| `050__reference_boundary_enums.sql` | `reference.{boundary_type,coordinate_system}` | 001 |
| `060__location_boundary.sql` | `location.{boundary,project_boundary,boundary_vertex}` + closure trigger | 040, 050 |
| `065__location_boundary_hew.sql` | Real seed rows in `location.{boundary,project_boundary,boundary_vertex}` for the Hesselø `HEW01`/`HEW02` array-area boundaries (public/open-source coordinates) | 040, 050, 060 |
| `070__reference_asset_enums.sql` | `reference.asset_type` | 001 |
| `080__location_asset_location.sql` | `location.asset_location` | 040, 070 |
| `090__reference_layout_status.sql` | `reference.layout_status` | 001 |
| `100__project_layout.sql` | `project.{layout,layout_asset}` | 080, 090, 050 |
| `102__project_layout_asset_rename.sql` | ALTER-based migration: renames `project.asset_layout_position` → `layout_asset`, `easting_m`/`northing_m` → `planned_eastings_m`/`planned_northings_m`, adds `water_level`/`foundation_type_code` (for databases created before this rename; not needed on a fresh apply of 100/120) | 100, 120, 020 (`foundation_type`) |
| `105__project_default_layout.sql` | `project.layout` (trigger + seed/backfill data; `project.create_default_layout()` function) | 040, 090, 100 |
| `106__project_default_layout_rename.sql` | ALTER/UPDATE-based migration: renames the placeholder `project.layout` row's `layout_code`/`layout_status_code` from `PENDING`/`PROP` to `L000`/`PLC` (for databases created before this rename; no-op on a fresh apply of the corrected 105) | 040, 090, 100, 105 |
| `110__reference_investigation_enums.sql` | `reference.{survey_phase,hole_type}` | 001 |
| `112__reference_position_context_enums.sql` | `reference.position_context` | 001 |
| `115__geotech_cluster_location.sql` | `geotech.cluster_location` | 040, 110, 050 |
| `120__geotech_site_investigation.sql` | `geotech.{site_investigation,exploratory_hole}` | 040, 100, 080, 110, 050, 112, 115 |
| `122__reference_hole_status_enums.sql` | `reference.{hole_status,termination_reason}` | 001 |
| `124__geotech_exploratory_hole_status.sql` | ALTER-based migration: adds `hole_status_code`/`target_depth_m`/`final_depth_m`/`termination_reason_code` to `geotech.exploratory_hole` | 120, 122 |
| `130__reference_test_and_sample_enums.sql` | `reference.{depth_reference,in_situ_test_type,sample_type,lab_test_type}` | 001 |
| `132__geotech_exploratory_hole_dates.sql` | ALTER-based migration: adds `start_date`/`end_date`/`comments` to `geotech.exploratory_hole` | 120 |
| `134__geotech_exploratory_hole_bumpover.sql` | ALTER-based migration: adds `parent_exploratory_hole_id` (self-referencing FK) to `geotech.exploratory_hole` | 120 |
| `136__geotech_cluster_location_nullable_coords.sql` | ALTER-based migration: relaxes `geotech.cluster_location.eastings_m`/`northings_m` from `NOT NULL` to nullable -- the EHS ETL's cluster get-or-create no longer derives a cluster's position from the referencing hole's planned position (that data comes from a separate, not-yet-defined input file) | 115 |
| `138__geotech_site_investigation_survey_status.sql` | `reference.survey_status` + ALTER-based migration adding `geotech.site_investigation.survey_status_code` (PLANNED/ACTIVE/COMPLETE lifecycle gate between the EHS live-progress pipeline and the pdtable final-QAQC'd-snapshot pipeline -- see the file's own header comment) | 001, 120 |
| `140__geotech_in_situ_test.sql` | `geotech.in_situ_test` | 120, 130 |
| `150__geotech_sample.sql` | `geotech.{sample,specimen}` | 120, 130 |
| `160__geotech_lab_test.sql` | `geotech.lab_test` | 130, 150 |
| `170__reference_cpt_enums.sql` | `reference.cpt_*` (9 enum tables) | 001 |
| `180__geotech_cpt_test.sql` | `geotech.cpt_test` | 140, 170 |
| `190__geotech_cpt_push.sql` | `geotech.cpt_push` | 180, 170 |
| `200__geotech_cpt_logged_data.sql` | `geotech.cpt_logged_data` | 190 |
| `210__geotech_cpt_seismic_data.sql` | `geotech.cpt_seismic_data` | 190 |
| `220__schema_grants.sql` | GRANTs on `reference`/`location`/`project`/`geotech` (schemas, tables, sequences, default privileges) to the `reader`, `dba` IAM DB users and the `useringeodb` local service account | 001–210 (everything — must run last) |

## Applying

`psql` is the recommended path — it's scriptable (a loop with `ON_ERROR_STOP`
catches a failure immediately, at the exact file that caused it) and can wrap
the *entire* migration set in one real transaction, which a GUI client like
DBeaver/pgAdmin can't easily do across many separately-opened files. No
`geodb_connect migrate` CLI command exists yet — see the open questions in
`tasks/plan.md`.

First, open the tunnel + get an IAM token (per `geodb/QUICK_START.md` Option A/B).
**Don't skip the "assume role" step** — generating a token with your default AWS
SSO identity instead of the `geodb-rds-pg-superuser-role` produces a token RDS's
IAM auth will reject with `FATAL: PAM authentication failed for user "superuser"`,
since that role is the only one currently permitted to authenticate as that DB
user (see `docs/architecture-review.md`). Reuse `geodb/shell/lib/common.sh`
rather than reimplementing this — it's the one place this logic is DRY'd up:

```bash
# Terminal A — leave running
bash geodb/shell/tunnel.sh

# Terminal B
source geodb/shell/lib/common.sh
load_geodb_env

ROLE_ARN="$(resolve_role_arn superuser)"
PGUSER="$(resolve_role_username superuser)"
assume_geodb_role "$ROLE_ARN" "$AWS_REGION" "pg-iam"   # <-- the step that was missing

export PGHOST=127.0.0.1 PGPORT="$GEODB_LOCAL_PORT" PGDATABASE="$GEODB_DB_NAME"
export PGUSER PGSSLMODE=require
export PGPASSWORD   # IAM tokens are valid 15 min regardless of STS session length — regenerate via
                     # generate_geodb_token if a run takes longer than that and psql starts failing
PGPASSWORD="$(generate_geodb_token "$GEODB_RDS_HOST" "$GEODB_RDS_PORT" "$AWS_REGION" "$PGUSER")"
```
To start fresh, drop the four schemas (if they exist) before applying the migration set:
```bash
psql <<EOF                      
DROP SCHEMA IF EXISTS geotech CASCADE;
DROP SCHEMA IF EXISTS project CASCADE;
DROP SCHEMA IF EXISTS location CASCADE;
DROP SCHEMA IF EXISTS reference CASCADE;
EOF
```

**Sanity-check the connection before looping over 22 files** — a `psql` command
that never returns (no output, no error, no prompt back) almost always means a
**stale tunnel**: the local port is still bound by a `session-manager` process
from an earlier `tunnel.sh`/`connect-db.sh` run, but its remote SSM session has
died, so it accepts new local connections and silently forwards them nowhere.
`psql` then hangs waiting for bytes that will never arrive — it looks like it's
stuck on auth, but it isn't actually talking to the server at all:

```bash
timeout 15 psql -v ON_ERROR_STOP=1 -c "select current_user, now();"
echo "exit code: $?"   # 124 == timed out == likely a stale tunnel, not a real auth failure
```

If that times out: kill the stale tunnel and start fresh —
`pkill -f session-manager` (or just close/re-open Terminal A), re-run
`bash geodb/shell/tunnel.sh`, then regenerate the token and retry.

**Option 1 — one file at a time (best for a first run / easiest to debug):**

```bash
for f in geodb/sql/*.sql; do
  echo "==> $f"
  psql -v ON_ERROR_STOP=1 -f "$f" || { echo "FAILED at $f"; break; }
done
```

**Option 2 — all files as a single atomic transaction** (once you trust the
set — if *any* statement in *any* file fails, everything rolls back
automatically, no half-applied schema):

```bash
cat geodb/sql/*.sql | psql -v ON_ERROR_STOP=1 --single-transaction
```

This relies on `geodb/sql/`'s zero-padded numeric filenames sorting correctly
in plain alphabetical glob order (`001`, `010`, ... `210` are all 3 digits, so
lexicographic order == numeric order) — don't add a 4-digit prefix without
re-padding the existing ones.

## Production-safe vs. dev-only files

**Everything directly under `geodb/sql/` is production-safe** — schema DDL plus
real, stable reference/lookup data (country codes, foundation types, the actual
catalog of real offshore wind projects, CPT enumerations, etc.). This is safe
and correct to apply to a real environment.

**Nothing under `geodb/sample-data/` is production-safe.** Those files contain
fictional/illustrative data (fabricated site investigations, boreholes, CPTs,
and one deliberately out-of-scale boundary) for development and testing only.
See `geodb/sample-data/README.md`.

## Task 2 design decisions

Written decisions required by `tasks/plan.md` Task 2, made during the Phase 1
refactor (`tasks/todo.md`). **Status: 1 and 2 confirmed by the user; 3 is
explicitly flagged as unresolved** — see below.

1. **Coordinate-column duplication** (`location.boundary_vertex`,
   `project.asset_layout_position`, `geotech.exploratory_hole` each have their
   own `easting_m`/`northing_m`(+ `coordinate_system_id`) columns, not a shared
   type/table): **confirmed — kept as intentional denormalization**, not
   refactored into a shared shape. Each is conceptually distinct — a boundary
   vertex, a layout-scoped design position, and an as-planned/as-installed
   hole position are different things that happen to share a column shape —
   and a shared abstraction isn't earning its complexity with only three call
   sites. Revisit if a fourth coordinate-bearing table appears.
2. **PostGIS**: **confirmed — deferred, not adopted, currently out of scope**.
   No spatial query need (e.g. "boreholes within 500 m of a cable route") has
   been demonstrated yet, and PostGIS availability on the real RDS instance is
   unconfirmed (see `tasks/plan.md` Open Questions). The schema continues with
   plain tabulated `easting_m`/`northing_m` + `reference.coordinate_system`
   (EPSG codes) until a concrete need and RDS confirmation both exist.
3. **`geotech.sample` / `geotech.specimen` / `geotech.lab_test`**: **NOT
   confirmed — flagged by the user as immature and requiring further
   development.** The `sample_id`-removal decision described in the previous
   version of this doc (specimen-only FK, no `sample_id` column on `lab_test`)
   is implemented in `160__geotech_lab_test.sql`, but the user has flagged the
   whole sample → specimen → lab_test chain — not just that one column — as
   not yet mature enough to treat as settled. **Treat
   `150__geotech_sample.sql` and `160__geotech_lab_test.sql` as provisional**:
   safe to apply (they're syntactically complete and internally consistent),
   but expect their shape to change before this schema is considered final.
   Open questions for the follow-up review include: is the specimen concept
   granular enough (or too granular) for the lab tests actually performed;
   should `test_conditions`/`raw_data`/`processed_data` JSONB columns be
   promoted to structured columns/tables the way CPT was (see
   `180`–`210__geotech_cpt_*.sql`); and whether `lab_test_type` should carry
   more structure than a flat code+name+description.



