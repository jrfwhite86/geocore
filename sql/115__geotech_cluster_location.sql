-- =============================================================================
-- Geotech: cluster_location (geotechnical cluster identity, layout-independent)
-- =============================================================================
-- Depends on: 040__project_project.sql, 110__reference_investigation_enums.sql
-- (survey_phase), 050__reference_boundary_enums.sql (coordinate_system)
--
-- Phase 10: input_layout_{area_code}.csv now carries only layout configuration
-- and the physical assets each layout includes; input_exploratory_hole_{area_code}.csv
-- carries a new **cluster_details table block for geotechnical cluster
-- locations, kept separate from location.asset_location (which is now
-- populated exclusively from input_layout.csv's physical assets). This table
-- is that cluster's home: a stable project-scoped identifier for a cluster of
-- exploratory holes, independent of any layout revision. See
-- geotech.exploratory_hole (120__) for how individual holes attach to either
-- a project.layout_asset, a location.asset_location, or a
-- geotech.cluster_location.
--
-- Task 2 design decision (coordinate-column duplication): see
-- 080__location_asset_location.sql — this table keeps its own
-- eastings_m/northings_m/coordinate_system_id rather than sharing a shape
-- with layout_asset/exploratory_hole.

CREATE TABLE geotech.cluster_location (
    cluster_location_id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES project.project(project_id) ON DELETE RESTRICT,
    cluster_name TEXT NOT NULL,
    survey_phase_code VARCHAR(10) REFERENCES reference.survey_phase(survey_phase_code) ON DELETE RESTRICT,
    eastings_m NUMERIC NOT NULL,
    northings_m NUMERIC NOT NULL,
    ground_level_m NUMERIC,
    water_level_m NUMERIC,
    coordinate_system_id BIGINT NOT NULL REFERENCES reference.coordinate_system(coordinate_system_id) ON DELETE RESTRICT,
    comments TEXT,
    UNIQUE (project_id, cluster_name)
);

CREATE INDEX idx_cluster_location_project ON geotech.cluster_location(project_id);

COMMENT ON TABLE geotech.cluster_location IS
'Stores the layout-independent identity of a geotechnical cluster location within a project. A cluster groups exploratory holes at a reconnaissance/IAC/ECR position or SI target not (yet) tied to a specific physical structure. Kept separate from location.asset_location, which is now populated exclusively from input_layout.csv''s physical assets.';

COMMENT ON COLUMN geotech.cluster_location.cluster_name IS
'A stable project-scoped internal identifier for the cluster location which must remain independent of layout revisions.';

COMMENT ON COLUMN geotech.cluster_location.survey_phase_code IS
'The survey phase during which this cluster location was established. References reference.survey_phase.';

COMMENT ON COLUMN geotech.cluster_location.ground_level_m IS
'Ground/seabed level in metres at the cluster location, relative to the vertical datum of coordinate_system_id.';

COMMENT ON COLUMN geotech.cluster_location.water_level_m IS
'Water level in metres at the cluster location, relative to the vertical datum of coordinate_system_id.';
