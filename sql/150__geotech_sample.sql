-- =============================================================================
-- Geotech: sample, specimen
-- =============================================================================
-- ** PROVISIONAL — flagged by the user for further review/development, not a
-- ** finalized design (see geodb/sql/README.md "Task 2 design decisions" #3).
-- ** The specimen concept in particular (its granularity, and whether it's
-- ** the right level of indirection between sample and lab_test) is called
-- ** out as needing more thought before this is treated as settled.
--
-- Depends on: 120__geotech_site_investigation.sql (exploratory_hole),
-- 130__reference_test_and_sample_enums.sql (sample_type, depth_reference)
--
-- Named "sample" directly (the prototype created "geotechnical_sample" and
-- renamed it later via ALTER TABLE — folded into final form here, per Task 1).
--
-- specimen is the AGS SPEC_REF-equivalent concept, sitting between sample and
-- lab_test: one sample can yield multiple specimens (e.g. specimens PSD3, AL3,
-- OED3, CIUC3 all from sample 3WaxA), and one specimen can be subjected to one
-- or more lab tests. See 160__geotech_lab_test.sql for the Task 2 decision to
-- have lab_test reference specimen only (no direct sample_id column).

CREATE TABLE geotech.sample (
    sample_id BIGSERIAL PRIMARY KEY,
    exploratory_hole_id BIGINT NOT NULL REFERENCES geotech.exploratory_hole(exploratory_hole_id) ON DELETE RESTRICT,
    sample_type_code VARCHAR(10) NOT NULL REFERENCES reference.sample_type(sample_type_code) ON DELETE RESTRICT,
    sample_reference TEXT NOT NULL,
    sample_date DATE,
    top_depth_m NUMERIC NOT NULL,
    bottom_depth_m NUMERIC NOT NULL,
    depth_reference_code VARCHAR(10) NOT NULL DEFAULT 'BSF' REFERENCES reference.depth_reference(depth_reference_code) ON DELETE RESTRICT,
    recovery_m NUMERIC CHECK (recovery_m IS NULL OR recovery_m >= 0),
    sample_data JSONB,
    description TEXT,
    UNIQUE (exploratory_hole_id, sample_reference),
    CHECK (bottom_depth_m >= top_depth_m),
    CHECK (top_depth_m >= 0)
);

CREATE INDEX idx_sample_hole ON geotech.sample(exploratory_hole_id);
CREATE INDEX idx_sample_type ON geotech.sample(sample_type_code);
CREATE INDEX idx_sample_data_gin ON geotech.sample USING GIN (sample_data);

COMMENT ON COLUMN geotech.sample.sample_reference IS
'Contractor or internal reference for the sample (e.g. "S1", "Push-3", "JS01"). Unique within an exploratory hole.';
COMMENT ON COLUMN geotech.sample.recovery_m IS
'Length of soil actually recovered (may be less than bottom_depth - top_depth if recovery was incomplete).';
COMMENT ON COLUMN geotech.sample.sample_data IS
'JSONB for sample-specific data not covered by structured fields (e.g. SPT blow counts split N1/N2/N3, sample quality designation, visual description, photos).';


CREATE TABLE geotech.specimen (
    specimen_id BIGSERIAL PRIMARY KEY,
    sample_id BIGINT NOT NULL REFERENCES geotech.sample(sample_id) ON DELETE RESTRICT,
    specimen_reference TEXT NOT NULL,
    specimen_depth_m NUMERIC,
    depth_reference_code VARCHAR(10) DEFAULT 'BSF' REFERENCES reference.depth_reference(depth_reference_code) ON DELETE RESTRICT,
    description TEXT,
    UNIQUE (sample_id, specimen_reference),
    CHECK (specimen_depth_m IS NULL OR specimen_depth_m >= 0)
);

CREATE INDEX idx_specimen_sample ON geotech.specimen(sample_id);

COMMENT ON TABLE geotech.specimen IS
'A test specimen prepared from a parent sample. Equivalent to the AGS SPEC_REF concept: one sample can yield multiple specimens (e.g. specimens PSD3, AL3, OED3, CIUC3 all from sample 3WaxA), and one specimen can be subjected to one or more lab tests.';

COMMENT ON COLUMN geotech.specimen.specimen_reference IS
'Specimen reference as labelled by the laboratory (AGS SPEC_REF equivalent). Unique within a parent sample.';
COMMENT ON COLUMN geotech.specimen.specimen_depth_m IS
'Depth at which the specimen was taken from the parent sample interval. Often the midpoint, but can be specific where the sample is heterogeneous.';

