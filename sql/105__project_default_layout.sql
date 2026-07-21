-- =============================================================================
-- Project: default layout placeholder
-- =============================================================================
-- Depends on:
--   040__project_project.sql
--   090__reference_layout_status.sql
--   100__project_layout.sql
--
-- Creates a single placeholder layout record for a project when no real
-- layout configuration data is available yet. Also backfills the placeholder
-- for projects that already exist.
--
-- No explicit BEGIN/COMMIT here: geodb/sql/README.md documents two supported
-- apply modes, one of which (`cat geodb/sql/*.sql | psql --single-transaction`)
-- wraps the *entire* migration set in one transaction already. A COMMIT inside
-- this file would end that outer transaction early and leave every later file
-- running outside it, defeating the documented all-or-nothing rollback
-- guarantee. Individual statements below don't need their own local
-- transaction boundary.

-- --------------------------------------------------------------------------
-- Trigger function
-- --------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION project.create_default_layout()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO project.layout (
        project_id,
        layout_code,
        layout_name,
        layout_status_code,
        effective_date,
        description
    )
    VALUES (
        NEW.project_id,
        'L000',
        'Placeholder layout',
        'PLC',
        NULL,
        'Placeholder layout — actual layout configuration data is not yet available for this project'
    )
    ON CONFLICT (project_id, layout_code) DO NOTHING;

    RETURN NEW;
END;
$$;

-- --------------------------------------------------------------------------
-- Trigger
-- --------------------------------------------------------------------------

DROP TRIGGER IF EXISTS trg_project_create_default_layout
ON project.project;

CREATE TRIGGER trg_project_create_default_layout
AFTER INSERT ON project.project
FOR EACH ROW
EXECUTE FUNCTION project.create_default_layout();

-- --------------------------------------------------------------------------
-- Backfill existing projects
-- --------------------------------------------------------------------------

INSERT INTO project.layout (
    project_id,
    layout_code,
    layout_name,
    layout_status_code,
    effective_date,
    description
)
SELECT
    p.project_id,
    'L000',
    'Placeholder layout',
    'PLC',
    NULL::date,
    'Placeholder layout — actual layout configuration data is not yet available for this project'
FROM project.project p
ON CONFLICT (project_id, layout_code) DO NOTHING;
