"""PROJ -> project.project mapping (tasks/plan.md Phase 3, Task 4).

See geodb/python/docs/ags-etl-mapping.md for narrative rationale. This module
is the structured source of truth the semantic-validation stage (Task 8)
consumes.

**REVISED 2026-07-09** (user review at the Task 4 checkpoint, second pass):
PROJ is NEVER used to resolve, select, or insert a project.project row. The
project.project catalog is real, seeded, deliberately curated data
(geodb/sql/040__project_project.sql) — the data engineer running a load
already knows which project a delivery belongs to as part of the normal
intake process: a new project's key metadata is created directly in geoCore
by a data engineer when the project starts, and *which* project an incoming
.ags/.json file belongs to is something the data engineer specifies during
the ETL run, not something the pipeline infers from the file's own PROJ
group. See PROJECT_RESOLUTION below.

PROJ's own heading values are read only so the semantic-validation stage
(Task 8) can cross-check them against the already-resolved project's real
column values and flag any inconsistency — geoCore's own data is always
treated as the "true" value. See PROJ_INCONSISTENCY_POLICY.

This retires the earlier PROJ_ID/PROJ_NAME match-and-insert-on-miss design
(previously PROJ_MATCH_STRATEGY / PROJ_UNRESOLVED_POLICY), which inferred the
project FROM the file — the correct model is the reverse: a file is loaded
INTO an already-known project.
"""

from __future__ import annotations

from ..types import FieldMapping

# How project_id is resolved for a load run. Metadata about *behaviour*, not a
# field mapping, so it isn't a FieldMapping — declared as plain data here, the
# same shape as loca.py's SITE_INVESTIGATION_RESOLUTION, which this
# deliberately mirrors: both project identity and site_investigation identity
# are things the pipeline is TOLD by the operator, never things it discovers
# by parsing AGS data.
PROJECT_RESOLUTION = (
    "project_code is a REQUIRED CLI argument to the load command (Task 11: "
    "`geodb-etl load file.ags --project-code ANH01 --si-name ... "
    "--survey-phase ...`), supplied by the data engineer running the load. "
    "It is never inferred, matched, or fuzzy-matched from the incoming PROJ "
    "group — there is no code path anywhere in this pipeline that creates, "
    "updates, or selects a project.project row from PROJ data. Creating a new "
    "project.project row (when a genuinely new project starts) is a separate, "
    "out-of-band data-engineer workflow entirely outside this ETL pipeline's "
    "scope — this pipeline only ever loads data INTO a project.project row "
    "that already exists, identified by the --project-code the operator "
    "supplies. An unrecognised --project-code (no matching project_code in "
    "project.project) is a hard CLI/pre-flight error, failing the run before "
    "any file parsing starts — not a manual-review case, since it is an "
    "operator input mistake, not a property of the AGS data itself."
)

# Field-by-field mapping, PROJ (see the reference AGS fixture's HEADING row) ->
# project.project. NOT a load/insert/update target — see PROJECT_RESOLUTION
# above. These mappings exist purely so the semantic-validation stage (Task 8)
# knows which geoCore column each PROJ heading is cross-checked against, once
# project_code has already been resolved via the --project-code CLI argument.
PROJ_FIELD_MAPPINGS: list[FieldMapping] = [
    FieldMapping(
        source_field="PROJ_ID",
        target_table="project.project",
        target_column="project_code",
        notes=(
            "Cross-checked (semantic validation, Task 8) against the "
            "project_code of the project resolved via --project-code (see "
            "PROJECT_RESOLUTION). A mismatch is flagged per "
            "PROJ_INCONSISTENCY_POLICY — never used to select, override, or "
            "insert a project."
        ),
    ),
    FieldMapping(
        source_field="PROJ_NAME",
        target_table="project.project",
        target_column="project_name",
        notes=(
            "Cross-checked (case-insensitive, whitespace-normalized) against "
            "the project_name of the already-resolved project — same "
            "flag-don't-select rule as PROJ_ID above."
        ),
    ),
]

# PROJ headings with no direct geoCore column. project.project has no
# free-text location field (location is modelled via
# location.development_area, resolved separately) — these are retained on the
# manual-review record for human context but are never loaded or cross-checked
# (there is no project.project column to compare them against).
PROJ_UNMAPPED_HEADINGS: list[str] = [
    "PROJ_LOC",
    "PROJ_CLNT",
    "PROJ_CONT",
    "PROJ_ENG",
    "PROJ_MEMO",
]

PROJ_INCONSISTENCY_POLICY = (
    "A mismatch between an incoming PROJ heading value (PROJ_ID/PROJ_NAME) and "
    "the corresponding column on the project already resolved via "
    "--project-code is a semantic-validation FLAG, not a RejectedRow and not a "
    "load-blocking error. geoCore's own project.project data is always treated "
    "as the 'true' value (it is real, seeded, deliberately curated data — see "
    "geodb/sql/040__project_project.sql); a stale or incorrect PROJ heading in "
    "a contractor file does not by itself mean the file is unusable or belongs "
    "to the wrong project — the data engineer already made that determination "
    "via --project-code. The mismatch is recorded on the load's "
    "manual-review/validation report (source_file, PROJ_ID/PROJ_NAME, expected "
    "vs actual value) so a human can confirm whether the contractor's own "
    "metadata is simply out of date, but LOCA/SCPG/SCPT rows in the same file "
    "are NOT held up waiting on that confirmation — this is a softer, "
    "informational flag, distinct from the retired PROJ_MATCH_STRATEGY model's "
    "unresolved-project manual-review record, which used to block loading "
    "entirely."
)

