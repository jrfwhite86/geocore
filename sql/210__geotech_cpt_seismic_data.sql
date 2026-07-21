-- =============================================================================
-- Geotech: cpt_seismic_data (optional, one row per push with seismic results)
-- =============================================================================
-- Depends on: 190__geotech_cpt_push.sql
-- Note: seismic_receiver/hammer_direction/interval_method are stored as TEXT[]
-- referencing the 170__reference_cpt_enums.sql lookup codes rather than a real
-- foreign key, since per-element FK enforcement isn't possible against array
-- elements in Postgres — validation of these values happens at ETL/load time.

CREATE TABLE geotech.cpt_seismic_data (
    cpt_seismic_data_id BIGSERIAL PRIMARY KEY,
    cpt_push_id BIGINT NOT NULL UNIQUE REFERENCES geotech.cpt_push(cpt_push_id) ON DELETE RESTRICT,
    -- Required arrays per the silver schema
    depth_m NUMERIC[] NOT NULL,
    shear_wave_velocity_m_s NUMERIC[] NOT NULL,
    -- Optional arrays.
    seismic_receiver TEXT[],
    hammer_direction TEXT[],
    interval_method TEXT[],
    confidence_interval NUMERIC[],
    CHECK (array_length(shear_wave_velocity_m_s, 1) = array_length(depth_m, 1)),
    CHECK (seismic_receiver    IS NULL OR array_length(seismic_receiver, 1)    = array_length(depth_m, 1)),
    CHECK (hammer_direction    IS NULL OR array_length(hammer_direction, 1)    = array_length(depth_m, 1)),
    CHECK (interval_method     IS NULL OR array_length(interval_method, 1)     = array_length(depth_m, 1)),
    CHECK (confidence_interval IS NULL OR array_length(confidence_interval, 1) = array_length(depth_m, 1))
);

CREATE INDEX idx_cpt_seismic_data_push ON geotech.cpt_seismic_data(cpt_push_id);

COMMENT ON TABLE geotech.cpt_seismic_data IS
'Seismic measurement traces for a single CPT push (only for SCPT/SPCPT or other tests with seismic geophones). Sampled at sparser depths than logged_data, hence a separate table. Required: depth, shear_wave_velocity.';

