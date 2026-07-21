-- =============================================================================
-- Geotech: site_investigation, exploratory_hole
-- =============================================================================
-- Depends on: 040__project_project.sql, 100__project_layout.sql (layout_asset),
-- 080__location_asset_location.sql, 110__reference_investigation_enums.sql,
-- 050__reference_boundary_enums.sql (coordinate_system),
-- 112__reference_position_context_enums.sql (position_context),
-- 115__geotech_cluster_location.sql (cluster_location)
-- Schema only — the CHW22 example site investigations/holes live in
-- geodb/sample-data/sql/demo-chw22.sql.

CREATE TABLE geotech.site_investigation (
    site_investigation_id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES project.project(project_id) ON DELETE RESTRICT,
    si_name TEXT NOT NULL,
    survey_phase_code VARCHAR(10) NOT NULL REFERENCES reference.survey_phase(survey_phase_code) ON DELETE RESTRICT,
    contractor TEXT,
    start_date DATE,
    end_date DATE,
    report_reference TEXT,
    description TEXT,
    UNIQUE (project_id, si_name),
    CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);

CREATE INDEX idx_site_investigation_project ON geotech.site_investigation(project_id);


-- An exploratory hole links to AT MOST one of:
--   (a) a specific layout_asset (when the hole was planned against
--       a particular layout's position),
--   (b) an asset_location directly (typically reconnaissance, before any
--       layout exists), or
--   (c) a cluster_location (a geotechnical cluster not tied to any physical
--       asset — see geotech.cluster_location, 115__).
-- A hole with NONE of the three set is a genuinely standalone exploratory
-- hole (e.g. a one-off geotechnical location never tied to an asset or
-- grouped into a cluster).
--
-- History: Phase 10 tightened this from "at most one, or neither" to
-- "exactly one" on the (then-true) assumption that every hole loaded via
-- input_exploratory_hole_{area_code}.csv always supplies an
-- asset_or_cluster_name. 2026-07-15: loosened back to "at most one" --
-- the EHS xlsx pipeline (load.xlsx.ehs) is the FIRST document to reach
-- geoCore for a campaign and must support (a) auto-creating a
-- geotech.cluster_location for a not-yet-declared cluster name (get-or-
-- create, not a hard failure) and (b) a genuinely standalone hole with no
-- cluster/asset name at all. 2026-07-20: the pdtable exploratory-hole
-- pipeline (load.pdtable.exploratory_hole) was ALSO updated to make its
-- own asset_or_cluster_name field optional at validation, for the same
-- reason -- a real campaign can legitimately contain holes with no
-- asset/cluster link at all (e.g. one-off reconnaissance locations), and
-- the file's per-block destination tag (e.g. "HEW02" under
-- **exploratory_hole_details) is a project_code destination, never a
-- per-row fallback asset/cluster name. Both pipelines now share this
-- constraint's "at most one" semantics.
--
-- Task 2 design decision (coordinate-column duplication): see
-- 080__location_asset_location.sql — this table keeps its own
-- easting/northing/coordinate_system_id rather than sharing a shape with
-- layout_asset/boundary_vertex.
CREATE TABLE geotech.exploratory_hole (
    exploratory_hole_id BIGSERIAL PRIMARY KEY,
    site_investigation_id BIGINT NOT NULL REFERENCES geotech.site_investigation(site_investigation_id) ON DELETE RESTRICT,
    layout_asset_id BIGINT REFERENCES project.layout_asset(layout_asset_id) ON DELETE RESTRICT,
    asset_location_id BIGINT REFERENCES location.asset_location(asset_location_id) ON DELETE RESTRICT,
    cluster_location_id BIGINT REFERENCES geotech.cluster_location(cluster_location_id) ON DELETE RESTRICT,
    contractor_hole_name TEXT NOT NULL,
    hole_type_code VARCHAR(10) NOT NULL REFERENCES reference.hole_type(hole_type_code) ON DELETE RESTRICT,
    hole_number VARCHAR(10),
    bumpover_label CHAR(1) CHECK (bumpover_label IS NULL OR bumpover_label ~ '^[a-z]$'),
    leg_label VARCHAR(2) CHECK (leg_label IS NULL OR leg_label ~ '^[A-Za-z0-9]+$'),
    planned_easting_m NUMERIC,
    planned_northing_m NUMERIC,
    actual_easting_m NUMERIC,
    actual_northing_m NUMERIC,
    seabed_level_m NUMERIC,
    coordinate_system_id BIGINT NOT NULL REFERENCES reference.coordinate_system(coordinate_system_id) ON DELETE RESTRICT,
    -- Derived, never hand-maintained: which of the three linkage columns (if
    -- any) is populated tells us unambiguously whether this hole is an
    -- ASSET/CLUSTER/STANDALONE position. A generated column means the
    -- classification can never drift out of sync with the FKs it's derived
    -- from. See reference.position_context (112__) for the code descriptions.
    position_context_code VARCHAR(10) GENERATED ALWAYS AS (
        CASE
            WHEN layout_asset_id   IS NOT NULL
              OR asset_location_id IS NOT NULL THEN 'ASSET'
            WHEN cluster_location_id IS NOT NULL THEN 'CLUSTER'
            ELSE 'STANDALONE'
        END
    ) STORED
        REFERENCES reference.position_context(position_context_code) ON DELETE RESTRICT,
    UNIQUE (site_investigation_id, contractor_hole_name),
    -- At most one of the three asset/cluster linkages may be set (see note above)
    CHECK (
        (CASE WHEN layout_asset_id IS NOT NULL THEN 1 ELSE 0 END)
      + (CASE WHEN asset_location_id IS NOT NULL THEN 1 ELSE 0 END)
      + (CASE WHEN cluster_location_id IS NOT NULL THEN 1 ELSE 0 END)
      <= 1
    ),
    -- Coordinate pairs must be both-or-neither
    CHECK ((planned_easting_m IS NULL) = (planned_northing_m IS NULL)),
    CHECK ((actual_easting_m IS NULL)  = (actual_northing_m IS NULL)),
    -- At least one position must be specified
    CHECK (planned_easting_m IS NOT NULL OR actual_easting_m IS NOT NULL)
);

CREATE INDEX idx_exploratory_hole_si       ON geotech.exploratory_hole(site_investigation_id);
CREATE INDEX idx_exploratory_hole_layout_asset ON geotech.exploratory_hole(layout_asset_id);
CREATE INDEX idx_exploratory_hole_asset    ON geotech.exploratory_hole(asset_location_id);
CREATE INDEX idx_exploratory_hole_cluster  ON geotech.exploratory_hole(cluster_location_id);
CREATE INDEX idx_exploratory_hole_type     ON geotech.exploratory_hole(hole_type_code);
CREATE INDEX idx_exploratory_hole_position_context ON geotech.exploratory_hole(position_context_code);

COMMENT ON COLUMN geotech.exploratory_hole.position_context_code IS
'Generated column: ASSET/CLUSTER/STANDALONE, derived from which of layout_asset_id/asset_location_id/cluster_location_id (if any) is populated. See reference.position_context.';

COMMENT ON COLUMN geotech.exploratory_hole.contractor_hole_name IS
'The hole name as recorded by the contractor on the field log. Often inconsistent
or ambiguous (e.g. "CPT-001a" vs "CPT-001A"); use the structured fields hole_number,
bumpover_label and leg_label for unambiguous identification.';
COMMENT ON COLUMN geotech.exploratory_hole.hole_number IS
'Free-text hole number as it appears in the contractor naming (e.g. "001", "1",
"A01"). Kept as text to preserve leading zeros and alphanumeric prefixes.';
COMMENT ON COLUMN geotech.site_investigation.description IS
'Free-text campaign narrative, authored by the Data Manager/Steward at or after
campaign close-out — not populated by ETL. Intended content: scope summary and
rationale (what was investigated and why), execution context (vessel, spread,
drilling/testing modes), campaign-level data-quality caveats (weather windows,
equipment issues, sections of the factual report a reader should consult), and
relationships to other campaigns (infill of, supplement to). Convention:
anything routinely filtered, joined, or aggregated on must NOT live only here —
recurring structured facts (e.g. vessel) should be promoted to their own column.
Prose for human readers only; never load-bearing for queries. Formal report
traceability belongs in report_reference, not here.';
COMMENT ON COLUMN geotech.exploratory_hole.seabed_level_m IS
'Seabed elevation at the hole position, referenced to the vertical datum of
coordinate_system_id. Records the level AS OBSERVED AT TIME OF WORKS (per AGS
LOCA_GL), not the charted or geophysical-survey value — in mobile-sediment
areas these can differ materially. This column bridges the two depth frames:
absolute elevation of a measurement = seabed_level_m − depth_BSF. Negative
values denote seabed below datum.';
