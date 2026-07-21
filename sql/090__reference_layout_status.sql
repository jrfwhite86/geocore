-- =============================================================================
-- Reference data: layout_status
-- =============================================================================
-- Production-safe reference data (see geodb/sql/README.md).

CREATE TABLE reference.layout_status (
    layout_status_code VARCHAR(10) PRIMARY KEY,
    layout_status_name TEXT NOT NULL,
    description TEXT
);

INSERT INTO reference.layout_status (layout_status_code, layout_status_name, description)
VALUES
('PLC', 'Placeholder',   'Placeholder layout - layout configuration data is not yet available for this project'),
('CUR',  'Current',    'Currently active layout for the project'),
('PROP', 'Proposed',   'Proposed layout under consideration'),
('SUP',  'Superseded', 'Layout replaced by a later version'),
('ASB',  'As-built',   'Layout reflecting actual installed positions');

