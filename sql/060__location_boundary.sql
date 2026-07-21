-- =============================================================================
-- Location: boundary, project_boundary, boundary_vertex
-- =============================================================================
-- Depends on: 040__project_project.sql, 050__reference_boundary_enums.sql
-- Schema only — no seed/demo rows in this file. An illustrative example boundary
-- (with its vertices) lives in geodb/sample-data/sql/demo-boundary-how04.sql,
-- since the vertex coordinates there are placeholder/fictional, not real geometry.
-- Real production boundary seed rows (e.g. HEW01/HEW02) live in
-- 065__location_boundary_hew.sql.

CREATE TABLE location.boundary (
    boundary_id BIGSERIAL PRIMARY KEY,
    boundary_name TEXT NOT NULL UNIQUE,
    boundary_type_code VARCHAR(10) NOT NULL REFERENCES reference.boundary_type(boundary_type_code) ON DELETE RESTRICT,
    coordinate_system_id BIGINT NOT NULL REFERENCES reference.coordinate_system(coordinate_system_id) ON DELETE RESTRICT
);


CREATE TABLE location.project_boundary (
    project_id BIGINT NOT NULL REFERENCES project.project(project_id) ON DELETE CASCADE,
    boundary_id BIGINT NOT NULL REFERENCES location.boundary(boundary_id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, boundary_id)
);


CREATE TABLE location.boundary_vertex (
    boundary_id BIGINT NOT NULL REFERENCES location.boundary(boundary_id) ON DELETE CASCADE,
    vertex_no INTEGER NOT NULL CHECK (vertex_no > 0),
    easting_m NUMERIC NOT NULL,
    northing_m NUMERIC NOT NULL,
    PRIMARY KEY (boundary_id, vertex_no)
);


-- Polygon closure check: enforced as a deferrable constraint via a trigger,
-- because a CHECK constraint cannot reference other rows. This validates that
-- for each boundary, the highest-numbered vertex matches vertex 1 (closed ring),
-- there are at least 4 vertices, and vertex numbers are contiguous from 1.
CREATE OR REPLACE FUNCTION location.validate_boundary_closure()
RETURNS TRIGGER AS $$
DECLARE
    v_boundary_id BIGINT;
    v_count INTEGER;
    v_max_vertex INTEGER;
    v_first_easting NUMERIC;
    v_first_northing NUMERIC;
    v_last_easting NUMERIC;
    v_last_northing NUMERIC;
BEGIN
    -- Determine which boundary to validate
    IF TG_OP = 'DELETE' THEN
        v_boundary_id := OLD.boundary_id;
    ELSE
        v_boundary_id := NEW.boundary_id;
    END IF;

    SELECT COUNT(*), MAX(vertex_no)
      INTO v_count, v_max_vertex
      FROM location.boundary_vertex
     WHERE boundary_id = v_boundary_id;

    -- A closed polygon requires at least 4 vertices (including the repeated last=first vertex)
    IF v_count < 4 THEN
        RAISE EXCEPTION 'Boundary % must have at least 4 vertices (found %)', v_boundary_id, v_count;
    END IF;

    -- Vertex numbers must be contiguous from 1
    IF v_max_vertex <> v_count THEN
        RAISE EXCEPTION 'Boundary % has non-contiguous vertex numbers (count=%, max=%)',
            v_boundary_id, v_count, v_max_vertex;
    END IF;

    -- First and last vertex must coincide (closed polygon)
    SELECT easting_m, northing_m INTO v_first_easting, v_first_northing
      FROM location.boundary_vertex
     WHERE boundary_id = v_boundary_id AND vertex_no = 1;

    SELECT easting_m, northing_m INTO v_last_easting, v_last_northing
      FROM location.boundary_vertex
     WHERE boundary_id = v_boundary_id AND vertex_no = v_max_vertex;

    IF v_first_easting <> v_last_easting OR v_first_northing <> v_last_northing THEN
        RAISE EXCEPTION 'Boundary % is not closed: vertex 1 (%, %) does not match vertex % (%, %)',
            v_boundary_id, v_first_easting, v_first_northing,
            v_max_vertex, v_last_easting, v_last_northing;
    END IF;

    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER trg_boundary_vertex_closure
    AFTER INSERT OR UPDATE OR DELETE ON location.boundary_vertex
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW
    EXECUTE FUNCTION location.validate_boundary_closure();

