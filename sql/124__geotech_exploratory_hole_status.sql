-- =============================================================================
-- geotech.exploratory_hole: hole_status_code, target/final depth, termination_reason_code
-- =============================================================================
-- ALTER-based migration (see 102__project_layout_asset_rename.sql for the
-- established pattern of this repo's "DDL catalog, not migration history"
-- model, applied here because 120__geotech_site_investigation.sql already has
-- real data behind it in some environments).
-- Depends on: 120__geotech_site_investigation.sql (geotech.exploratory_hole),
-- 122__reference_hole_status_enums.sql (reference.hole_status,
-- reference.termination_reason).
--
-- Design note: hole_status_code (lifecycle: where is the hole in the SI
-- process?) and termination_reason_code (why did it stop, if it stopped?)
-- are deliberately separate columns -- see 122's header comment. Every hole
-- defaults to SCHEDULED with no termination reason and no final depth; a
-- hole is only ever moved to a terminal status by an explicit update.
--
-- Position-level rollup ("is CPT01 done?") is deliberately NOT stored here --
-- it's a question about the group of holes sharing (site_investigation_id,
-- hole_number, leg_label), not about any single row (a hole can be FAILED
-- forever while its bumpover succeeds). Derive it with a view over this
-- table if/when needed, rather than duplicating state.

ALTER TABLE geotech.exploratory_hole
    ADD COLUMN hole_status_code VARCHAR(10) NOT NULL DEFAULT 'SCHEDULED'
        REFERENCES reference.hole_status(hole_status_code) ON DELETE RESTRICT,
    ADD COLUMN target_depth_m NUMERIC CHECK (target_depth_m IS NULL OR target_depth_m >= 0),
    ADD COLUMN final_depth_m NUMERIC CHECK (final_depth_m IS NULL OR final_depth_m >= 0),
    ADD COLUMN termination_reason_code VARCHAR(10)
        REFERENCES reference.termination_reason(termination_reason_code) ON DELETE RESTRICT;

CREATE INDEX idx_exploratory_hole_status ON geotech.exploratory_hole(hole_status_code);
CREATE INDEX idx_exploratory_hole_termination_reason ON geotech.exploratory_hole(termination_reason_code);

COMMENT ON COLUMN geotech.exploratory_hole.hole_status_code IS
'Lifecycle status of the hole (SCHEDULED/INPROGRESS/COMPLETED/ACCEPTED/FAILED/
ABANDONED/CANCELLED) -- see reference.hole_status. Distinct from
termination_reason_code, which records WHY a hole stopped, not WHERE it is in
the lifecycle. Convention (not enforced by a CHECK, to avoid forcing strict
ETL ordering): once hole_status_code is one of the terminal statuses
(reference.hole_status.is_terminal = true) other than CANCELLED, actual
coordinates and final_depth_m should be populated.';
COMMENT ON COLUMN geotech.exploratory_hole.target_depth_m IS
'Planned/design target depth for this hole, in metres below seabed/ground
level (per the hole''s own depth reference). NULL if no target depth applies
or is not yet known.';
COMMENT ON COLUMN geotech.exploratory_hole.final_depth_m IS
'As-achieved final depth for this hole, in metres below seabed/ground level.
NULL until the hole has actually been attempted. May be less than
target_depth_m -- e.g. a hole ACCEPTED short of target, or FAILED before
reaching it.';
COMMENT ON COLUMN geotech.exploratory_hole.termination_reason_code IS
'Why the hole stopped (TARGET/REFUSAL/EQUIPMENT/WEATHER/PROJECT/OTHER) -- see
reference.termination_reason. NULL for holes not yet terminated
(hole_status_code SCHEDULED/INPROGRESS) and typically NULL for CANCELLED
holes (never attempted, so there is nothing to explain).';
