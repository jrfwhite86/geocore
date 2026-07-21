-- =============================================================================
-- reference.survey_status + geotech.site_investigation.survey_status_code
-- =============================================================================
-- ALTER-based migration (see 102__project_layout_asset_rename.sql for the
-- established pattern; applied here because 120__geotech_site_investigation.sql
-- already has real data behind it in some environments).
-- Depends on: 001__schemas.sql, 120__geotech_site_investigation.sql.
--
-- Context (2026-07-17 confirmed workflow): a site investigation's exploratory
-- holes are recorded by TWO pipelines in sequence, not two concurrently
-- authoritative ones:
--   (i)   the EHS xlsx workbook is issued before mobilisation and RE-ISSUED
--         across the campaign to report live progress (load.xlsx.ehs) --
--         every hole_status_code starts SCHEDULED and moves through
--         INPROGRESS towards a terminal status as fieldwork proceeds;
--   (ii)  once the campaign concludes (every hole's hole_status_code is
--         terminal -- see reference.hole_status.is_terminal), a data
--         engineer performs QAQC on the final EHS revision and pushes it,
--         ONCE, as input_exploratory_holes_{area_code}.csv
--         (load.pdtable.exploratory_hole) -- the authoritative, final
--         snapshot of the campaign.
--
-- Without a gate, nothing stops (a) the pdtable file being pushed before the
-- campaign has genuinely finished (silently freezing live EHS progress data
-- into a stale "final" state) or (b) a further EHS re-issue running AFTER
-- the QAQC'd pdtable push and clobbering it. survey_status_code is that
-- gate: the pdtable load stage sets it to 'COMPLETE' after a successful
-- load, and the EHS load stage refuses (LoadError) to upsert any hole for a
-- site_investigation already marked 'COMPLETE'. There is no automatic
-- transition to 'COMPLETE' from within the EHS pipeline itself -- reaching
-- COMPLETE always requires the explicit, human-QAQC'd pdtable push,
-- deliberately not inferred from every hole_status_code happening to be
-- terminal (a data engineer's sign-off is a distinct event from the field
-- data merely reaching a terminal state).

CREATE TABLE reference.survey_status (
    survey_status_code VARCHAR(10) PRIMARY KEY,
    survey_status_name TEXT NOT NULL,
    is_locked BOOLEAN NOT NULL,
    description TEXT
);

INSERT INTO reference.survey_status (survey_status_code, survey_status_name, is_locked, description)
VALUES
('PLANNED',  'Planned',  false, 'EHS issued, campaign not yet mobilised -- no hole has started.'),
('ACTIVE',   'Active',   false, 'Campaign under way; EHS is re-issued to report live progress. Both EHS and pdtable pipelines may write here (pdtable only once, to close it out -- see COMPLETE).'),
('COMPLETE', 'Complete', true,  'Campaign concluded and QAQC''d final snapshot pushed via input_exploratory_holes_{area_code}.csv. Locked: the EHS pipeline refuses to upsert further holes for this site_investigation.');

COMMENT ON COLUMN reference.survey_status.is_locked IS
'TRUE only for COMPLETE. load.xlsx.ehs checks this before upserting a hole and
raises LoadError if true -- see this migration''s header comment.';

ALTER TABLE geotech.site_investigation
    ADD COLUMN survey_status_code VARCHAR(10) NOT NULL DEFAULT 'ACTIVE'
        REFERENCES reference.survey_status(survey_status_code) ON DELETE RESTRICT;

COMMENT ON COLUMN geotech.site_investigation.survey_status_code IS
'Lifecycle gate between the EHS (live progress) and pdtable (final QAQC''d
snapshot) pipelines -- see reference.survey_status and this migration''s
header comment. Defaults to ACTIVE (not PLANNED) since geotech.
site_investigation is only ever created by load.xlsx.ehs upon first receiving
an EHS workbook with at least one hole row, i.e. once a campaign already has
a schedule. Set to COMPLETE exclusively by load.pdtable.exploratory_hole
after a successful load; never set back to PLANNED/ACTIVE by any pipeline --
reopening a COMPLETE site investigation is a deliberate manual DBA action,
not an ETL-driven transition.';
