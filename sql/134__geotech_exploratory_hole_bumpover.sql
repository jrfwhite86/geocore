-- =============================================================================
-- geotech.exploratory_hole: parent_exploratory_hole_id (bumpover provenance)
-- =============================================================================
-- ALTER-based migration (see 102__project_layout_asset_rename.sql for the
-- established pattern; applied here because 120__geotech_site_investigation.sql
-- already has real data behind it in some environments).
-- Depends on: 120__geotech_site_investigation.sql (geotech.exploratory_hole,
-- bumpover_label already exists there).
--
-- Context: the EHS workbook was revised (2026-07-16) to add a "Bumpover
-- parent hole" column alongside its existing "Bumpover label" column,
-- specifically so a bumpover location (e.g. "CPT01a") unambiguously records
-- WHICH prior hole it superseded (e.g. "CPT01"), rather than leaving that
-- relationship to be inferred from naming convention alone. bumpover_label
-- (added in 120, CHECK '^[a-z]$') already records THAT a hole is a bumpover;
-- this column records FROM WHAT.
--
-- Self-referencing FK, nullable (most holes are not bumpovers). Resolved by
-- the EHS load stage via a lookup on (site_investigation_id,
-- contractor_hole_name = <the workbook's own "Bumpover parent hole" text>) --
-- mirrors the asset_or_cluster_name resolution pattern in
-- geodb_etl.load.xlsx.ehs. Per the confirmed 2026-07-16 decision, a name that
-- fails to resolve (typo, wrong load order, parent not yet loaded) does NOT
-- fail the row or the file -- it loads with parent_exploratory_hole_id NULL
-- and a warning, the same flag-don't-block discipline as the "Position
-- context" soft cross-check (Task 14a).
--
-- Deliberately NOT a CHECK-enforced pair with bumpover_label: the
-- flag-don't-block resolution above can legitimately leave
-- parent_exploratory_hole_id NULL even when bumpover_label is set (an
-- unresolved parent reference), so a strict "both or neither" CHECK would be
-- wrong here -- see the column comment below for the intended convention
-- instead.

ALTER TABLE geotech.exploratory_hole
    ADD COLUMN parent_exploratory_hole_id BIGINT
        REFERENCES geotech.exploratory_hole(exploratory_hole_id) ON DELETE RESTRICT,
    ADD CONSTRAINT exploratory_hole_parent_not_self
        CHECK (parent_exploratory_hole_id IS NULL OR parent_exploratory_hole_id <> exploratory_hole_id);

CREATE INDEX idx_exploratory_hole_parent ON geotech.exploratory_hole(parent_exploratory_hole_id);

COMMENT ON COLUMN geotech.exploratory_hole.parent_exploratory_hole_id IS
'Self-reference to the exploratory_hole this row bumped over FROM (e.g.
"CPT01a" -> "CPT01"). Convention (not enforced by a CHECK, to accommodate the
load stage''s flag-don''t-block resolution -- see this column''s migration
file): a non-NULL bumpover_label SHOULD have a corresponding non-NULL
parent_exploratory_hole_id, and vice versa, but a resolution failure (unknown
parent hole name) intentionally leaves this column NULL with only a load-time
warning, not a rejection.';
