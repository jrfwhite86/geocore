-- =============================================================================
-- geotech.exploratory_hole: start_date, end_date, comments
-- =============================================================================
-- ALTER-based migration (see 102__project_layout_asset_rename.sql for the
-- established pattern; applied here because 120__geotech_site_investigation.sql
-- already has real data behind it in some environments).
-- Depends on: 120__geotech_site_investigation.sql (geotech.exploratory_hole).
--
-- Context: the EHS (Exploratory Hole Schedule) workbook is no longer a
-- planned-only, pre-mobilization document -- it is now re-issued across the
-- campaign to report actual progress (start/end dates, as-installed
-- coordinates, final depth, hole status, termination reason -- see
-- 122__reference_hole_status_enums.sql and 124__geotech_exploratory_hole_status.sql
-- for the status/reason columns). start_date/end_date/comments complete that
-- picture at the individual-hole level, mirroring the existing
-- geotech.site_investigation.start_date/end_date columns and CHECK pattern.

ALTER TABLE geotech.exploratory_hole
    ADD COLUMN start_date DATE,
    ADD COLUMN end_date DATE,
    ADD COLUMN comments TEXT,
    ADD CONSTRAINT exploratory_hole_end_date_check
        CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date);

COMMENT ON COLUMN geotech.exploratory_hole.start_date IS
'Date operations began at this hole (rig/vessel on position). NULL until the
hole has actually been attempted (hole_status_code SCHEDULED).';
COMMENT ON COLUMN geotech.exploratory_hole.end_date IS
'Date operations concluded at this hole (rig/vessel demobilised from
position), whether the hole reached target depth or was terminated early.
NULL until the hole has actually concluded.';
COMMENT ON COLUMN geotech.exploratory_hole.comments IS
'Free-text remarks carried over from the EHS workbook''s "Remarks" column
(e.g. operational notes, justification for an ACCEPTED/ABANDONED status).
Not validated or interpreted by the ETL beyond full-overwrite-on-reload.';
