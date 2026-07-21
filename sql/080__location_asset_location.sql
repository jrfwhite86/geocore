-- =============================================================================
-- Location: asset_location (layout-independent asset identity)
-- =============================================================================
-- Depends on: 040__project_project.sql, 070__reference_asset_enums.sql
--
-- Task 2 design decision (coordinate-column duplication): this table does NOT
-- carry coordinates itself — see project.asset_layout_position (100__) for why
-- position is layout-scoped, not identity-scoped. asset_layout_position and
-- geotech.exploratory_hole (120__) each keep their own easting_m/northing_m/
-- coordinate_system_id columns rather than sharing one composite type/table.
-- Decision: kept as intentional denormalization (not refactored into a shared
-- shape) for this pass — each table's coordinate is conceptually distinct
-- (a layout-scoped design position vs. an as-installed/as-surveyed hole
-- position), and a shared abstraction isn't earning its complexity yet with
-- only three call sites. Revisit if a fourth coordinate-bearing table appears
-- or cross-table spatial queries become common (see PostGIS decision below).

CREATE TABLE location.asset_location (
    asset_location_id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES project.project(project_id) ON DELETE RESTRICT,
    parent_location_id BIGINT REFERENCES location.asset_location(asset_location_id) ON DELETE RESTRICT,
    internal_reference TEXT NOT NULL,
    asset_type_code VARCHAR(10) NOT NULL REFERENCES reference.asset_type(asset_type_code) ON DELETE RESTRICT,
    leg_label VARCHAR(2) CHECK (leg_label IS NULL OR leg_label ~ '^[A-Z]+$'),
    description TEXT,
    UNIQUE (project_id, internal_reference),
    CHECK (asset_type_code <> 'JLEG' OR parent_location_id IS NOT NULL),
    CHECK (asset_type_code <> 'JLEG' OR leg_label IS NOT NULL)
);

CREATE INDEX idx_asset_location_project ON location.asset_location(project_id);
CREATE INDEX idx_asset_location_parent  ON location.asset_location(parent_location_id);

-- =============================================================================
-- Documentation
-- =============================================================================

COMMENT ON TABLE location.asset_location IS
'Stores the layout-independent identity and classification of an asset location or geotechnical target within a project. Layout-specific names, codes and coordinates are stored in project.asset_layout_position.';

COMMENT ON COLUMN location.asset_location.asset_location_id IS
'System-generated primary key for the asset location record.';

COMMENT ON COLUMN location.asset_location.project_id IS
'Project to which the asset location belongs. References project.project.';

COMMENT ON COLUMN location.asset_location.parent_location_id IS
'Optional parent asset location. Used for subordinate locations such as individual jacket legs, which reference the main jacket asset location.';

COMMENT ON COLUMN location.asset_location.internal_reference IS
'Stable project-scoped internal identifier for the asset location. The value must remain independent of layout revisions; layout-specific asset numbers and RDS-PP codes are stored in project.asset_layout_position.';

COMMENT ON COLUMN location.asset_location.asset_type_code IS
'Classifies the asset or target type: ANS, WTG, OSS, OCS, RCS, MET, JLEG (physical structures), REC, IAC, ECR (not yet tied to a physical structure), or OTHER. References reference.asset_type. Since the Phase 10 cluster/asset schema split, location.asset_location is populated exclusively from physical-structure asset types; REC/IAC/ECR cluster-purpose locations live in geotech.cluster_location instead.';

COMMENT ON COLUMN location.asset_location.leg_label IS
'Optional uppercase label identifying an individual jacket leg, for example A, B, C or D. Required when asset_type_code is JLEG and otherwise normally NULL.';

COMMENT ON COLUMN location.asset_location.description IS
'Optional free-text description providing additional context about the asset location or geotechnical target.';