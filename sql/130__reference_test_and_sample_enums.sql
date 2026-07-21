-- =============================================================================
-- Reference data: depth_reference, in_situ_test_type, sample_type, lab_test_type
-- =============================================================================
-- Production-safe reference data (see geodb/sql/README.md).
--
-- lab_test_type is named directly in its final form here (the prototype
-- created it as "sample_test_type" and renamed it later via ALTER TABLE —
-- Task 1 folds that rename into this file so the migration set reflects the
-- final shape directly, per the plan's "no design changes bundled in, but no
-- create-then-rename either" instruction).

CREATE TABLE reference.depth_reference (
    depth_reference_code VARCHAR(10) PRIMARY KEY,
    depth_reference_name TEXT NOT NULL,
    description TEXT
);

INSERT INTO reference.depth_reference (depth_reference_code, depth_reference_name, description)
VALUES
('BSF',  'Below seafloor',       'Depth measured downwards from the seafloor (mudline). Most common offshore convention.'),
('BGL',  'Below ground level',   'Depth measured downwards from ground surface (onshore).'),
('LAT',  'Lowest astronomical tide', 'Elevation referenced to LAT, positive upwards.'),
('MSL',  'Mean sea level',       'Elevation referenced to MSL, positive upwards.'),
('CD',   'Chart datum',          'Elevation referenced to local chart datum, positive upwards.');


CREATE TABLE reference.in_situ_test_type (
    in_situ_test_type_code VARCHAR(10) PRIMARY KEY,
    in_situ_test_type_name TEXT NOT NULL,
    description TEXT
);

INSERT INTO reference.in_situ_test_type (in_situ_test_type_code, in_situ_test_type_name, description)
VALUES
('CPT',   'Cone penetration test',           'Standard CPT with cone tip resistance, sleeve friction'),
('CPTU',  'Piezocone penetration test',      'CPT with pore pressure measurement (u2)'),
('SCPT',  'Seismic CPT',                     'CPT with seismic geophone for shear wave velocity'),
('SPCPT', 'Seismic piezocone penetration test', 'CPTU with seismic geophone'),
('FVT',   'Field vane test',                 'In-situ vane shear test for undrained shear strength'),
('PMT',   'Pressuremeter test',              'Pressuremeter test (Menard, self-boring or push-in)'),
('DMT',   'Flat dilatometer test',           'Marchetti flat dilatometer test'),
('SPT',   'Standard penetration test',       'Standard penetration test (blow count)'),
('TCS',   'Thermal conductivity sounding',   'In-situ thermal conductivity measurement');


CREATE TABLE reference.sample_type (
    sample_type_code VARCHAR(10) PRIMARY KEY,
    sample_type_name TEXT NOT NULL,
    description TEXT
);

INSERT INTO reference.sample_type (sample_type_code, sample_type_name, description)
VALUES
('PUSH',  'Push sample',     'Thin-walled tube sample pushed into the soil (e.g. Shelby tube)'),
('PIST',  'Piston sample',   'Fixed-piston thin-walled sample, typically high quality'),
('HAM',   'Hammer sample',   'Driven thick-walled sample (lower quality, disturbed)'),
('SPT',   'SPT sample',      'Split-spoon sample recovered during SPT'),
('GRAB',  'Grab sample',     'Seabed grab sample'),
('VC',    'Vibrocore sample','Sample recovered by vibrocoring'),
('BAG',   'Bag sample',      'Bulk disturbed bag sample'),
('JAR',   'Jar sample',      'Small jar sample for index testing');


CREATE TABLE reference.lab_test_type (
    lab_test_type_code VARCHAR(10) PRIMARY KEY,
    lab_test_type_name TEXT NOT NULL,
    description TEXT
);

INSERT INTO reference.lab_test_type (lab_test_type_code, lab_test_type_name, description)
VALUES
('MC',    'Moisture content',                  'Water/moisture content determination'),
('ATT',   'Atterberg limits',                  'Liquid limit, plastic limit, plasticity index'),
('PSD',   'Particle size distribution',        'Sieve and/or hydrometer analysis'),
('BD',    'Bulk density',                      'Bulk density determination'),
('UU',    'Unconsolidated undrained triaxial', 'UU triaxial compression test'),
('CU',    'Consolidated undrained triaxial',   'CU triaxial compression test'),
('CD',    'Consolidated drained triaxial',     'CD triaxial compression test'),
('OED',   'Oedometer test',                    'One-dimensional consolidation test'),
('DSS',   'Direct simple shear',               'Direct simple shear test'),
('BE',    'Bender element',                    'Bender element test for small-strain shear modulus'),
('RC',    'Resonant column',                   'Resonant column test'),
('CHEM',  'Chemical analysis',                 'Geochemical analysis (sulphate, chloride, pH, organic content)'),
('CARB',  'Carbonate content',                 'Carbonate content determination'),
('SG',    'Specific gravity',                  'Specific gravity of solids');

