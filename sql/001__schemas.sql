-- =============================================================================
-- Schemas
-- =============================================================================
-- Faithful split of tasks/geocore.sql (prototype) into numbered migration files.
-- See geodb/sql/README.md for numbering convention, apply instructions, and the
-- Task 2 design decisions (coordinate-column duplication, PostGIS, sample/specimen
-- shape) referenced throughout these files.

CREATE SCHEMA IF NOT EXISTS reference;
CREATE SCHEMA IF NOT EXISTS location;
CREATE SCHEMA IF NOT EXISTS project;
CREATE SCHEMA IF NOT EXISTS geotech;

COMMENT ON SCHEMA reference IS 'Lookup and enumeration tables shared across the database';
COMMENT ON SCHEMA location  IS 'Geographic entities: development areas, boundaries, asset locations';
COMMENT ON SCHEMA project   IS 'Project-level entities: projects, foundations, assets';
COMMENT ON SCHEMA geotech   IS 'Geotechnical site investigation data: holes, tests, samples, profiles';

