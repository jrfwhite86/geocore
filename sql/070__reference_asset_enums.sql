-- =============================================================================
-- Reference data: asset_type
-- =============================================================================
-- Production-safe reference data (see geodb/sql/README.md).
--
-- reference.location_purpose (ASSET/CLUSTER) and location.asset_location's
-- location_purpose_code FK to it were removed after the Phase 10 cluster/asset
-- schema split: location.asset_location is now populated exclusively from
-- physical-structure asset types, and cluster-purpose locations live in the
-- separate geotech.cluster_location table -- the ASSET/CLUSTER distinction is
-- structural (which table + FK a row lives under) rather than a column value.

CREATE TABLE reference.asset_type (
    asset_type_code VARCHAR(10) PRIMARY KEY,
    asset_type_name TEXT NOT NULL,
    description TEXT
);

INSERT INTO reference.asset_type (asset_type_code, asset_type_name, description)
VALUES
('ANS',   'Artificial nesting structure',    'Artificial nesting structure location'),
('WTG',   'Wind turbine generator',          'Wind turbine generator foundation location'),
('OSS',   'Offshore substation',             'Offshore substation foundation location'),
('OCS',   'Offshore converter station',      'Offshore converter station foundation location'),
('RCS',   'Reactive compensation station',      'Reactive compensation station foundation location'),
('MET',   'Meteorological mast',             'Met mast foundation location'),
('JLEG',  'Jacket leg',                      'Individual leg position on a jacket foundation'),
('REC',   'Geotechnical reconnaissance',     'Geotechnical reconnaissance location, not tied to a specific physical structure'),
('IAC',   'Inter-array cable',               'Inter-array cable location'),
('ECR',   'Export cable route',              'Export cable route location'),
('OTHER', 'Other',                           'Other asset type not otherwise classified');

