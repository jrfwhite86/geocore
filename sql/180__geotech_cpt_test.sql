-- =============================================================================
-- Geotech: cpt_test (location-level CPT metadata, extends in_situ_test 1:1)
-- =============================================================================
-- Depends on: 140__geotech_in_situ_test.sql, 170__reference_cpt_enums.sql

CREATE TABLE geotech.cpt_test (
    cpt_test_id BIGSERIAL PRIMARY KEY,
    in_situ_test_id BIGINT NOT NULL UNIQUE REFERENCES geotech.in_situ_test(in_situ_test_id) ON DELETE RESTRICT,
    cpt_test_mode_code VARCHAR(10) NOT NULL REFERENCES reference.cpt_test_mode(cpt_test_mode_code) ON DELETE RESTRICT,
    cpt_test_status_code VARCHAR(20) REFERENCES reference.cpt_test_status(cpt_test_status_code) ON DELETE RESTRICT,
    test_method TEXT,                  -- e.g. "ISO 22476-1:2022", "ASTM D5778-12"
    test_accreditation TEXT,           -- accrediting body and reference
    test_contractor TEXT,
    test_conditions TEXT,              -- environmental conditions narrative (weather, sea state)
    test_deviations TEXT,              -- description of any deviations from standard procedure
    vessel TEXT,
    -- Schema/ETL provenance, mirroring the silver schema's metadata block
    schema_id TEXT,
    compiled_at TIMESTAMPTZ,
    compiled_by TEXT,
    validation_status TEXT,
    notes TEXT
);

CREATE INDEX idx_cpt_test_in_situ ON geotech.cpt_test(in_situ_test_id);

COMMENT ON TABLE geotech.cpt_test IS
'Location-level CPT metadata. Extends in_situ_test 1:1 for tests of type CPT, CPTU, SCPT or SPCPT. Push-level data lives in cpt_push.';

