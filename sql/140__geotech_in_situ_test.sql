-- =============================================================================
-- Geotech: in_situ_test
-- =============================================================================
-- Depends on: 120__geotech_site_investigation.sql (exploratory_hole),
-- 130__reference_test_and_sample_enums.sql (in_situ_test_type, depth_reference)

CREATE TABLE geotech.in_situ_test (
    in_situ_test_id BIGSERIAL PRIMARY KEY,
    exploratory_hole_id BIGINT NOT NULL REFERENCES geotech.exploratory_hole(exploratory_hole_id) ON DELETE RESTRICT,
    in_situ_test_type_code VARCHAR(10) NOT NULL REFERENCES reference.in_situ_test_type(in_situ_test_type_code) ON DELETE RESTRICT,
    test_reference TEXT NOT NULL,
    test_date DATE,
    start_depth_m NUMERIC NOT NULL,
    end_depth_m NUMERIC NOT NULL,
    depth_reference_code VARCHAR(10) NOT NULL DEFAULT 'BSF' REFERENCES reference.depth_reference(depth_reference_code) ON DELETE RESTRICT,
    test_conditions JSONB,
    raw_data JSONB,
    processed_data JSONB,
    description TEXT,
    UNIQUE (exploratory_hole_id, test_reference),
    CHECK (end_depth_m >= start_depth_m),
    CHECK (start_depth_m >= 0)
);

CREATE INDEX idx_in_situ_test_hole ON geotech.in_situ_test(exploratory_hole_id);
CREATE INDEX idx_in_situ_test_type ON geotech.in_situ_test(in_situ_test_type_code);
-- GIN indexes on JSONB allow efficient containment/key queries
CREATE INDEX idx_in_situ_test_conditions_gin ON geotech.in_situ_test USING GIN (test_conditions);
CREATE INDEX idx_in_situ_test_processed_gin  ON geotech.in_situ_test USING GIN (processed_data);

COMMENT ON COLUMN geotech.in_situ_test.test_reference IS
'Contractor or internal reference for this specific test (e.g. "Push 1", "DCPT-1", "FVT@12m"). Unique within an exploratory hole.';
COMMENT ON COLUMN geotech.in_situ_test.test_conditions IS
'JSONB describing the test conditions (equipment, calibration, operator, weather, cone serial number, area ratio, etc.). Schema is test-type dependent.';
COMMENT ON COLUMN geotech.in_situ_test.raw_data IS
'JSONB containing the as-acquired measurements. For CPT/CPTU, expected keys include "z_m" (array of depths), "qc_MPa", "fs_MPa", "u2_MPa". For other test types, see test-type-specific documentation.';
COMMENT ON COLUMN geotech.in_situ_test.processed_data IS
'JSONB containing derived/interpreted quantities (e.g. corrected qt, Bq, Ic, soil behaviour type index). Always re-derivable from raw_data.';

