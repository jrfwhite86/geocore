-- =============================================================================
-- Geotech: lab_test
-- =============================================================================
-- ** PROVISIONAL — flagged by the user for further review/development, not a
-- ** finalized design. Do not treat this table's shape as settled. See
-- ** geodb/sql/README.md "Task 2 design decisions" #3 for open questions
-- ** (specimen granularity, whether JSONB columns should be promoted to
-- ** structured columns/tables the way CPT was, lab_test_type structure).
--
-- Depends on: 130__reference_test_and_sample_enums.sql (lab_test_type, depth_reference),
-- 150__geotech_sample.sql (specimen)
--
-- Task 2 design decision (resolves the prototype's commented-out
-- "DROP COLUMN sample_id" TODO): lab_test references specimen ONLY —
-- specimen_id is NOT NULL and there is no sample_id column at all. The
-- prototype went through an intermediate state (sample_test.geotechnical_
-- sample_id -> lab_test.sample_id, then later ADD COLUMN specimen_id
-- alongside the old sample_id, with the drop left as a commented-out TODO)
-- because it had to migrate data already keyed by sample_id. This migration
-- set has no existing data to migrate (see geodb/sql/README.md), so the
-- clean final shape is used directly instead of re-creating that transition.

CREATE TABLE geotech.lab_test (
    lab_test_id BIGSERIAL PRIMARY KEY,
    specimen_id BIGINT NOT NULL REFERENCES geotech.specimen(specimen_id) ON DELETE RESTRICT,
    lab_test_type_code VARCHAR(10) NOT NULL REFERENCES reference.lab_test_type(lab_test_type_code) ON DELETE RESTRICT,
    test_reference TEXT NOT NULL,
    test_date DATE,
    test_depth_m NUMERIC,
    depth_reference_code VARCHAR(10) DEFAULT 'BSF' REFERENCES reference.depth_reference(depth_reference_code) ON DELETE RESTRICT,
    laboratory TEXT,
    test_conditions JSONB,
    raw_data JSONB,
    processed_data JSONB,
    description TEXT,
    UNIQUE (specimen_id, lab_test_type_code, test_reference),
    CHECK (test_depth_m IS NULL OR test_depth_m >= 0)
);

CREATE INDEX idx_lab_test_specimen ON geotech.lab_test(specimen_id);
CREATE INDEX idx_lab_test_type     ON geotech.lab_test(lab_test_type_code);
CREATE INDEX idx_lab_test_processed_gin ON geotech.lab_test USING GIN (processed_data);

COMMENT ON COLUMN geotech.lab_test.specimen_id IS
'The specimen this lab test was performed on. Each lab test is performed on exactly one specimen; one specimen may have multiple lab tests of different types.';
COMMENT ON COLUMN geotech.lab_test.test_depth_m IS
'Depth at which the sub-sample was taken from the parent sample interval for testing. Often the midpoint of the parent sample interval.';
COMMENT ON COLUMN geotech.lab_test.laboratory IS
'Name of the laboratory that performed the test.';

