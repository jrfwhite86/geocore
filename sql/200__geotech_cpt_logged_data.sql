-- =============================================================================
-- Geotech: cpt_logged_data (variable-length traces, one row per push)
-- =============================================================================
-- Depends on: 190__geotech_cpt_push.sql

CREATE TABLE geotech.cpt_logged_data (
    cpt_logged_data_id BIGSERIAL PRIMARY KEY,
    cpt_push_id BIGINT NOT NULL UNIQUE REFERENCES geotech.cpt_push(cpt_push_id) ON DELETE RESTRICT,
    -- Required arrays per the silver schema
    depth_m NUMERIC[] NOT NULL,
    cone_resistance_pa NUMERIC[] NOT NULL,
    sleeve_friction_pa NUMERIC[] NOT NULL,
    -- Optional arrays
    record_index INTEGER[],
    penetration_length_m NUMERIC[],
    pore_pressure_u1_pa NUMERIC[],
    pore_pressure_u2_pa NUMERIC[],
    pore_pressure_u3_pa NUMERIC[],
    inclination_x_rad NUMERIC[],
    inclination_y_rad NUMERIC[],
    datetime TIMESTAMPTZ[],
    elapsed_time_s NUMERIC[],
    total_thrust_n NUMERIC[],
    soil_temperature_c NUMERIC[],
    tip_temperature_c NUMERIC[],
    sleeve_temperature_c NUMERIC[],
    pwp_temperature_c NUMERIC[],
    -- All present arrays must have the same length as depth
    CHECK (array_length(cone_resistance_pa, 1) = array_length(depth_m, 1)),
    CHECK (array_length(sleeve_friction_pa, 1) = array_length(depth_m, 1)),
    CHECK (record_index            IS NULL OR array_length(record_index, 1)            = array_length(depth_m, 1)),
    CHECK (penetration_length_m    IS NULL OR array_length(penetration_length_m, 1)    = array_length(depth_m, 1)),
    CHECK (pore_pressure_u1_pa     IS NULL OR array_length(pore_pressure_u1_pa, 1)     = array_length(depth_m, 1)),
    CHECK (pore_pressure_u2_pa     IS NULL OR array_length(pore_pressure_u2_pa, 1)     = array_length(depth_m, 1)),
    CHECK (pore_pressure_u3_pa     IS NULL OR array_length(pore_pressure_u3_pa, 1)     = array_length(depth_m, 1)),
    CHECK (inclination_x_rad       IS NULL OR array_length(inclination_x_rad, 1)       = array_length(depth_m, 1)),
    CHECK (inclination_y_rad       IS NULL OR array_length(inclination_y_rad, 1)       = array_length(depth_m, 1)),
    CHECK (datetime                IS NULL OR array_length(datetime, 1)                = array_length(depth_m, 1)),
    CHECK (elapsed_time_s          IS NULL OR array_length(elapsed_time_s, 1)          = array_length(depth_m, 1)),
    CHECK (total_thrust_n          IS NULL OR array_length(total_thrust_n, 1)          = array_length(depth_m, 1)),
    CHECK (soil_temperature_c      IS NULL OR array_length(soil_temperature_c, 1)      = array_length(depth_m, 1)),
    CHECK (tip_temperature_c       IS NULL OR array_length(tip_temperature_c, 1)       = array_length(depth_m, 1)),
    CHECK (sleeve_temperature_c    IS NULL OR array_length(sleeve_temperature_c, 1)    = array_length(depth_m, 1)),
    CHECK (pwp_temperature_c       IS NULL OR array_length(pwp_temperature_c, 1)       = array_length(depth_m, 1))
);

CREATE INDEX idx_cpt_logged_data_push ON geotech.cpt_logged_data(cpt_push_id);

COMMENT ON TABLE geotech.cpt_logged_data IS
'Logged measurement traces for a single CPT push. Arrays are parallel — index i across all arrays refers to the same measurement record. All physical quantities in SI base units (m, Pa, rad, s, N, °C). Required: depth, cone_resistance, sleeve_friction.';

