-- =============================================================================
-- Reference data: foundation_type, project_status
-- =============================================================================
-- Production-safe reference data (see geodb/sql/README.md).

CREATE TABLE reference.foundation_type (
    foundation_type_code VARCHAR(10) PRIMARY KEY,
    foundation_type_name TEXT NOT NULL,
    description TEXT
);

INSERT INTO reference.foundation_type (foundation_type_code, foundation_type_name, description)
VALUES
('GBS','gravity based structure','Gravity based structure foundation'),
('MP','monopile','Monopile'),
('MULT','multiple','Multiple foundation types installed'),
('PJ','piled jacket','Piled jacket'),
('SBJ','suction bucket jacket','Suction bucket jacket'),
('MB','monobucket','Mono suction caisson'),
('FIXED','Fixed-undefined','Multiple fixed-bottom foundation types under consideration'),
('FLOAT','Floating-undefined','Multiple floating anchor foundation types under consideration');


CREATE TABLE reference.project_status (
    project_status_code VARCHAR(10) PRIMARY KEY,
    project_status_name TEXT NOT NULL,
    description TEXT
);

INSERT INTO reference.project_status (project_status_code, project_status_name, description)
VALUES
('AF','Assessment and feasibility','Initial analysis and business case (pre-FID)'),
('DEV','In active development','Scope and baseline defined, contracting and procurement activities underway (post-FID)'),
('UC','Under construction','Physical build or installation underway'),
('FC','Fully commissioned','Testing and verifications complete; asset handed over to operations'),
('CA','Cancelled','Project stopped and not continuing'),
('OH','On hold','Paused due to external/strategic reasons');

