-- =============================================================================
-- Reference data: boundary_type, coordinate_system
-- =============================================================================
-- Production-safe reference data (see geodb/sql/README.md).

CREATE TABLE reference.boundary_type (
    boundary_type_code VARCHAR(10) PRIMARY KEY,
    description TEXT NOT NULL
);

INSERT INTO reference.boundary_type (boundary_type_code, description)
VALUES
('ECR',   'export cable route corridor'),
('ARRAY', 'array area');


CREATE TABLE reference.coordinate_system (
    coordinate_system_id BIGSERIAL PRIMARY KEY,
    epsg_code_horizontal INTEGER NOT NULL,
    horizontal_unit TEXT NOT NULL,
    epsg_code_vertical INTEGER,
    vertical_unit TEXT,
    CHECK ((epsg_code_vertical IS NULL) = (vertical_unit IS NULL))
);

-- Postgres <15 compatibility: emulate "UNIQUE NULLS NOT DISTINCT" for the optional vertical component.
CREATE UNIQUE INDEX uq_coordinate_system_no_vertical
    ON reference.coordinate_system (epsg_code_horizontal, horizontal_unit)
    WHERE epsg_code_vertical IS NULL AND vertical_unit IS NULL;

CREATE UNIQUE INDEX uq_coordinate_system_with_vertical
    ON reference.coordinate_system (epsg_code_horizontal, horizontal_unit, epsg_code_vertical, vertical_unit)
    WHERE epsg_code_vertical IS NOT NULL AND vertical_unit IS NOT NULL;

INSERT INTO reference.coordinate_system (epsg_code_horizontal, horizontal_unit, epsg_code_vertical, vertical_unit)
VALUES
(25831, 'm', 5621, 'm'),
(25832, 'm', 10549, 'm');

