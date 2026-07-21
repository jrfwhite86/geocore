-- =============================================================================
-- Geotech: cluster_location -- relax eastings_m/northings_m to nullable
-- =============================================================================
-- Depends on: 115__geotech_cluster_location.sql
--
-- geodb_etl.load.xlsx.ehs (the EHS ETL) previously get-or-created a
-- geotech.cluster_location row using the referencing exploratory hole's own
-- planned position for eastings_m/northings_m. That was wrong: a cluster's
-- home position is not something the EHS workbook is authoritative for -- it
-- is intended to come from a separate input file (not yet defined). This
-- migration relaxes eastings_m/northings_m from NOT NULL to nullable so the
-- EHS ETL can create a cluster_location row (get-or-create, keyed on
-- (project_id, cluster_name)) without supplying a position, leaving it for
-- the future authoritative loader to populate.

ALTER TABLE geotech.cluster_location
    ALTER COLUMN eastings_m DROP NOT NULL,
    ALTER COLUMN northings_m DROP NOT NULL;

COMMENT ON COLUMN geotech.cluster_location.eastings_m IS
'Easting in metres, in the CRS given by coordinate_system_id. Nullable: a cluster row may be created (e.g. by the EHS ETL''s get-or-create path) before its authoritative home position is known -- see geodb_etl.load.xlsx.ehs module docstring''s "Cluster position removed from this mapping" section.';

COMMENT ON COLUMN geotech.cluster_location.northings_m IS
'Northing in metres, in the CRS given by coordinate_system_id. Nullable: a cluster row may be created (e.g. by the EHS ETL''s get-or-create path) before its authoritative home position is known -- see geodb_etl.load.xlsx.ehs module docstring''s "Cluster position removed from this mapping" section.';
