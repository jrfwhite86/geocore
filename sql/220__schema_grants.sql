-- =============================================================================
-- Schema and object grants for non-owner DB roles/users
-- =============================================================================
-- Depends on: 001__schemas.sql .. 210__geotech_cpt_seismic_data.sql (every table
-- and sequence created by the migration set so far — this must run last).
--
-- Fixes a gap identified while investigating a DBeaver
-- "SQL Error [42501]: ERROR: permission denied for schema project" report: none of
-- the migration files up to this point ever GRANTed schema/table/sequence access
-- to anyone. Whoever applied 001-210 (assumed to be the `superuser` IAM DB user,
-- which owns every object created here) is therefore the *only* role that can read
-- or write these tables — the `reader`/`dba` IAM roles and the `useringeodb` local
-- password-auth service account (see geodb/QUICK_START.md and
-- docs/infrastructure-reference.md) have no access at all until this file runs.
--
-- Must be applied by the object owner (the role that ran 001-210, i.e. `superuser`)
-- so that `GRANT` and `ALTER DEFAULT PRIVILEGES` below actually take effect and
-- cover privileges on tables/sequences that role owns.
--
-- Privilege model (per user decision, see docs/architecture-review.md /
-- infrastructure-reference.md for the IAM role -> DB user mapping):
--   reader        -- read-only: USAGE on schemas, SELECT on tables (existing + future)
--   dba           -- full admin: USAGE/CREATE on schemas, ALL PRIVILEGES on tables,
--                    sequences, and functions (existing + future)
--   useringeodb   -- full admin, same shape as `dba` above (app/service account)
--
-- Idempotent: GRANT statements in PostgreSQL are safe to re-run.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'reader') THEN
        RAISE EXCEPTION 'Role "reader" does not exist — create it (or the IAM DB user) before applying this migration';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dba') THEN
        RAISE EXCEPTION 'Role "dba" does not exist — create it (or the IAM DB user) before applying this migration';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'useringeodb') THEN
        RAISE EXCEPTION 'Role "useringeodb" does not exist — create it before applying this migration';
    END IF;
END
$$;

-- --------------------------------------------------------------------------
-- reader: read-only across all four application schemas
-- --------------------------------------------------------------------------
GRANT USAGE ON SCHEMA reference, location, project, geotech TO reader;

GRANT SELECT ON ALL TABLES IN SCHEMA reference TO reader;
GRANT SELECT ON ALL TABLES IN SCHEMA location  TO reader;
GRANT SELECT ON ALL TABLES IN SCHEMA project   TO reader;
GRANT SELECT ON ALL TABLES IN SCHEMA geotech   TO reader;

ALTER DEFAULT PRIVILEGES IN SCHEMA reference GRANT SELECT ON TABLES TO reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA location  GRANT SELECT ON TABLES TO reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA project   GRANT SELECT ON TABLES TO reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA geotech   GRANT SELECT ON TABLES TO reader;

-- --------------------------------------------------------------------------
-- dba: full admin — DML on all existing/future tables and sequences, plus
-- CREATE on the schemas themselves
-- --------------------------------------------------------------------------
GRANT USAGE, CREATE ON SCHEMA reference, location, project, geotech TO dba;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA reference TO dba;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA location  TO dba;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA project   TO dba;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA geotech   TO dba;

GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA reference TO dba;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA location  TO dba;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA project   TO dba;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA geotech   TO dba;

ALTER DEFAULT PRIVILEGES IN SCHEMA reference GRANT ALL PRIVILEGES ON TABLES TO dba;
ALTER DEFAULT PRIVILEGES IN SCHEMA location  GRANT ALL PRIVILEGES ON TABLES TO dba;
ALTER DEFAULT PRIVILEGES IN SCHEMA project   GRANT ALL PRIVILEGES ON TABLES TO dba;
ALTER DEFAULT PRIVILEGES IN SCHEMA geotech   GRANT ALL PRIVILEGES ON TABLES TO dba;

ALTER DEFAULT PRIVILEGES IN SCHEMA reference GRANT ALL PRIVILEGES ON SEQUENCES TO dba;
ALTER DEFAULT PRIVILEGES IN SCHEMA location  GRANT ALL PRIVILEGES ON SEQUENCES TO dba;
ALTER DEFAULT PRIVILEGES IN SCHEMA project   GRANT ALL PRIVILEGES ON SEQUENCES TO dba;
ALTER DEFAULT PRIVILEGES IN SCHEMA geotech   GRANT ALL PRIVILEGES ON SEQUENCES TO dba;

-- --------------------------------------------------------------------------
-- useringeodb: local password-auth application/service account — same full-admin
-- shape as `dba` above (per user decision), since it is the account backing the
-- application rather than a read-only consumer.
-- --------------------------------------------------------------------------
GRANT USAGE, CREATE ON SCHEMA reference, location, project, geotech TO useringeodb;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA reference TO useringeodb;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA location  TO useringeodb;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA project   TO useringeodb;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA geotech   TO useringeodb;

GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA reference TO useringeodb;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA location  TO useringeodb;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA project   TO useringeodb;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA geotech   TO useringeodb;

ALTER DEFAULT PRIVILEGES IN SCHEMA reference GRANT ALL PRIVILEGES ON TABLES TO useringeodb;
ALTER DEFAULT PRIVILEGES IN SCHEMA location  GRANT ALL PRIVILEGES ON TABLES TO useringeodb;
ALTER DEFAULT PRIVILEGES IN SCHEMA project   GRANT ALL PRIVILEGES ON TABLES TO useringeodb;
ALTER DEFAULT PRIVILEGES IN SCHEMA geotech   GRANT ALL PRIVILEGES ON TABLES TO useringeodb;

ALTER DEFAULT PRIVILEGES IN SCHEMA reference GRANT ALL PRIVILEGES ON SEQUENCES TO useringeodb;
ALTER DEFAULT PRIVILEGES IN SCHEMA location  GRANT ALL PRIVILEGES ON SEQUENCES TO useringeodb;
ALTER DEFAULT PRIVILEGES IN SCHEMA project   GRANT ALL PRIVILEGES ON SEQUENCES TO useringeodb;
ALTER DEFAULT PRIVILEGES IN SCHEMA geotech   GRANT ALL PRIVILEGES ON SEQUENCES TO useringeodb;

