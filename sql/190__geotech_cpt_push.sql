-- =============================================================================
-- Geotech: cpt_push (one row per push within a CPT test)
-- =============================================================================
-- Depends on: 180__geotech_cpt_test.sql, 170__reference_cpt_enums.sql

CREATE TABLE geotech.cpt_push (
    cpt_push_id BIGSERIAL PRIMARY KEY,
    cpt_test_id BIGINT NOT NULL REFERENCES geotech.cpt_test(cpt_test_id) ON DELETE RESTRICT,
    push_reference TEXT NOT NULL,
    push_sequence INTEGER,
    test_date TIMESTAMPTZ,
    cone_type TEXT,                                  -- e.g. "EC", "PC", "PC+SC"
    pre_drilled_depth_m NUMERIC,
    nominal_penetration_rate_m_s NUMERIC,
    orientation_deg NUMERIC,
    zero_location_code VARCHAR(5) REFERENCES reference.cpt_zero_location(cpt_zero_location_code) ON DELETE RESTRICT,
    termination TEXT,                                -- termination reason(s)
    -- Cone identity & calibration
    cone_reference TEXT,
    cone_manufacturer TEXT,
    calibration_date DATE,
    -- Geometry (stored in SI base units: m^2)
    cross_sectional_area_m2 NUMERIC,
    nominal_cross_sectional_area_m2 NUMERIC,
    cone_area_ratio NUMERIC,                         -- alpha (dimensionless)
    sleeve_area_m2 NUMERIC,
    nominal_sleeve_area_m2 NUMERIC,
    sleeve_area_ratio NUMERIC,                       -- beta (dimensionless)
    shaft_area_m2 NUMERIC,                           -- ball / T-bar shaft
    -- Capacity (stored in Pa)
    cone_capacity_pa NUMERIC,
    sleeve_capacity_pa NUMERIC,
    pore_pressure_capacity_pa NUMERIC,
    -- Classification
    application_class TEXT,                          -- obsolete, ISO 22476-1:2012 ("1","2","3","4","OC")
    test_category_code VARCHAR(5) REFERENCES reference.cpt_test_category(cpt_test_category_code) ON DELETE RESTRICT,
    cone_penetrometer_class INTEGER CHECK (cone_penetrometer_class IS NULL OR cone_penetrometer_class BETWEEN 0 AND 3),
    load_cell_arrangement_code VARCHAR(5) REFERENCES reference.cpt_load_cell_arrangement(cpt_load_cell_arrangement_code) ON DELETE RESTRICT,
    -- Pore pressure system
    filter_material TEXT,
    saturation_method TEXT,
    u1_transducer BOOLEAN,
    u2_transducer BOOLEAN,
    u3_transducer BOOLEAN,
    -- Friction reducer
    friction_reducer BOOLEAN,
    friction_reducer_distance_m NUMERIC,
    friction_reducer_diameter_m NUMERIC,
    -- Other transducers
    temperature_transducer BOOLEAN,
    seismic_geophones BOOLEAN,
    -- Seismic CPT setup
    seismic_receiver_setup_code VARCHAR(10) REFERENCES reference.cpt_seismic_setup(cpt_seismic_setup_code) ON DELETE RESTRICT,
    seismic_hammer_setup TEXT,
    seismic_source_horizontal_offset_m NUMERIC,
    seismic_source_vertical_offset_m NUMERIC,
    seismic_top_receiver_vertical_offset_m NUMERIC,
    seismic_bottom_receiver_vertical_offset_m NUMERIC,
    UNIQUE (cpt_test_id, push_reference),
    CHECK (pre_drilled_depth_m IS NULL OR pre_drilled_depth_m >= 0)
);

CREATE INDEX idx_cpt_push_test ON geotech.cpt_push(cpt_test_id);

COMMENT ON TABLE geotech.cpt_push IS
'A single push within a CPT test. Seabed-mode CPTs typically have one push; downhole-mode CPTs have many. All physical quantities stored in SI base units (m, m^2, Pa, m/s).';
COMMENT ON COLUMN geotech.cpt_push.push_sequence IS
'Optional integer ordering of pushes within a test (1, 2, 3...) for cases where push_reference is not naturally orderable.';
COMMENT ON COLUMN geotech.cpt_push.cone_type IS
'Cone module composition. Single module (BALL, CC, CTP, CPTU, EC, FFD, GAM, MC, MG, PC, SC, T-BAR, TC) or multiple combined with "+" (e.g. "PC+SC"). Free text rather than enum because module combinations are open-ended.';

