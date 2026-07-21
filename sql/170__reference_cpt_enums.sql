-- =============================================================================
-- Reference data: CPT-specific enumerations
-- =============================================================================
-- Production-safe reference data (see geodb/sql/README.md).

CREATE TABLE reference.cpt_test_mode (
    cpt_test_mode_code VARCHAR(10) PRIMARY KEY,
    description TEXT NOT NULL
);
INSERT INTO reference.cpt_test_mode VALUES
('seabed',   'Test performed in seabed mode (single push from seafloor)'),
('downhole', 'Test performed in downhole mode (multiple pushes from the bottom of a borehole)');

CREATE TABLE reference.cpt_test_status (
    cpt_test_status_code VARCHAR(20) PRIMARY KEY,
    description TEXT NOT NULL
);
INSERT INTO reference.cpt_test_status VALUES
('PRELIMINARY', 'Preliminary results, subject to change'),
('APPROVED',    'Approved final results');

CREATE TABLE reference.cpt_zero_location (
    cpt_zero_location_code VARCHAR(5) PRIMARY KEY,
    description TEXT NOT NULL
);
INSERT INTO reference.cpt_zero_location VALUES
('BB', 'Before push, on bottom (at start depth)'),
('S',  'On surface (above water/seabed)'),
('SB', 'Surface and bottom (averaged)');

CREATE TABLE reference.cpt_load_cell_arrangement (
    cpt_load_cell_arrangement_code VARCHAR(5) PRIMARY KEY,
    description TEXT NOT NULL
);
INSERT INTO reference.cpt_load_cell_arrangement VALUES
('CC', 'Compression cell (combined tip + sleeve)'),
('SC', 'Subtraction cell (separate tip and sleeve channels)'),
('TC', 'Tension compensated cell');

CREATE TABLE reference.cpt_test_category (
    cpt_test_category_code VARCHAR(5) PRIMARY KEY,
    description TEXT NOT NULL
);
INSERT INTO reference.cpt_test_category VALUES
('A',  'ISO 22476-1:2022 category A'),
('B',  'ISO 22476-1:2022 category B'),
('C',  'ISO 22476-1:2022 category C'),
('D',  'ISO 22476-1:2022 category D'),
('OC', 'Out of category');

CREATE TABLE reference.cpt_seismic_setup (
    cpt_seismic_setup_code VARCHAR(10) PRIMARY KEY,
    description TEXT NOT NULL
);
INSERT INTO reference.cpt_seismic_setup VALUES
('SINGLE', 'Single seismic receiver'),
('DUAL',   'Dual seismic receiver setup');

CREATE TABLE reference.cpt_seismic_receiver (
    cpt_seismic_receiver_code VARCHAR(2) PRIMARY KEY,
    description TEXT NOT NULL
);
INSERT INTO reference.cpt_seismic_receiver VALUES
('X', 'Receiver X component'),
('Y', 'Receiver Y component'),
('A', 'Averaged / combined component');

CREATE TABLE reference.cpt_hammer_direction (
    cpt_hammer_direction_code VARCHAR(10) PRIMARY KEY,
    description TEXT NOT NULL
);
INSERT INTO reference.cpt_hammer_direction VALUES
('LEFT',    'Hammer strike from left'),
('RIGHT',   'Hammer strike from right'),
('AVERAGE', 'Average of left and right strikes'),
('SINGLE',  'Single hammer direction (no left/right convention)');

CREATE TABLE reference.cpt_seismic_interval_method (
    cpt_seismic_interval_method_code VARCHAR(10) PRIMARY KEY,
    description TEXT NOT NULL
);
INSERT INTO reference.cpt_seismic_interval_method VALUES
('PSEUDO',  'Pseudo-interval method'),
('TRUE',    'True interval method'),
('AVERAGE', 'Averaged interval method');

