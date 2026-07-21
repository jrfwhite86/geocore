-- =============================================================================
-- Project: layout, layout_asset
-- =============================================================================
-- Depends on: 080__location_asset_location.sql, 090__reference_layout_status.sql,
-- 050__reference_boundary_enums.sql (coordinate_system), 020__reference_project_enums.sql (foundation_type)

CREATE TABLE project.layout (
    layout_id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES project.project(project_id) ON DELETE RESTRICT,
    layout_code VARCHAR(10) NOT NULL,
    layout_name TEXT,
    layout_status_code VARCHAR(10) NOT NULL REFERENCES reference.layout_status(layout_status_code) ON DELETE RESTRICT,
    effective_date DATE,
    description TEXT,
    UNIQUE (project_id, layout_code)
);

CREATE INDEX idx_layout_project ON project.layout(project_id);


-- For each (asset_location, layout) pair, the layout-specific name, RDS-PP code
-- (when assigned) and position. This is where the planned coordinate data lives.
-- See 080__location_asset_location.sql for the Task 2 decision on why this table
-- keeps its own easting/northing/coordinate_system_id rather than sharing a
-- coordinate shape with exploratory_hole/boundary_vertex.
--
-- Renamed from asset_layout_position → layout_asset (clearer name, better distinction
-- from location.asset_location). Column renames: easting_m → planned_eastings_m,
-- northing_m → planned_northings_m (clarifies these are planned/design positions,
-- which may differ from actual as-installed positions).
CREATE TABLE project.layout_asset (
    layout_asset_id BIGSERIAL PRIMARY KEY,
    asset_location_id BIGINT NOT NULL REFERENCES location.asset_location(asset_location_id) ON DELETE RESTRICT,
    layout_id BIGINT NOT NULL REFERENCES project.layout(layout_id) ON DELETE RESTRICT,
    rdspp_code TEXT,
    eastings_m NUMERIC NOT NULL,
    northings_m NUMERIC NOT NULL,
    seabed_level_m NUMERIC,
    water_level_m NUMERIC,
    foundation_type_code VARCHAR(10) REFERENCES reference.foundation_type(foundation_type_code) ON DELETE RESTRICT,
    coordinate_system_id BIGINT NOT NULL REFERENCES reference.coordinate_system(coordinate_system_id) ON DELETE RESTRICT,
    UNIQUE (asset_location_id, layout_id),
    UNIQUE (layout_id, rdspp_code)
);

CREATE INDEX idx_layout_asset_asset  ON project.layout_asset(asset_location_id);
CREATE INDEX idx_layout_asset_layout ON project.layout_asset(layout_id);

COMMENT ON TABLE project.layout_asset IS
'Per-asset layout-specific position data. Stores the planned (design) position for each asset in each layout, distinguishing from actual as-installed positions (which may differ during field deployment).';

COMMENT ON COLUMN project.layout_asset.eastings_m IS
'Easting coordinate in metres, in the project''s coordinate system.';

COMMENT ON COLUMN project.layout_asset.northings_m IS
'Northing coordinate in metres, in the project''s coordinate system.';

COMMENT ON COLUMN project.layout_asset.water_level_m IS
'Water level in metres at this asset location, relative to the project''s coordinate system vertical datum (works for both offshore and onshore assets, unlike a depth reference which would need to specify e.g. MSL/LAT/ground level). Populated from input_layout CSV''s water_level column.';

COMMENT ON COLUMN project.layout_asset.foundation_type_code IS
'Foundation type code for this specific asset. References reference.foundation_type. Populated from input_layout CSV''s foundation_type column.';

COMMENT ON COLUMN project.layout_asset.rdspp_code IS
'RDS-PP code as assigned for this asset in this layout (e.g. "WTG_A01"). Per IEC 81346 / VGB-S-823, intended as a stable lifecycle identifier, but in practice may be reassigned across layouts.';

