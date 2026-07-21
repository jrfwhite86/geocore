-- =============================================================================
-- Reference data: survey_phase, hole_type
-- =============================================================================
-- Production-safe reference data (see geodb/sql/README.md).

CREATE TABLE reference.survey_phase (
    survey_phase_code VARCHAR(10) PRIMARY KEY,
    survey_phase_name TEXT NOT NULL,
    description TEXT
);

INSERT INTO reference.survey_phase (survey_phase_code, survey_phase_name, description)
VALUES
('GTP', 'Geotechnical preliminary',    'Preliminary-stage geotechnical investigation, typically commissioned and executed by an external organisation, with the resulting data subsequently obtained by the project'),
('GTL', 'Geotechnical lite', 'Early-stage limited scope geotechnical investigation (e.g. seabed CPTs, grab samples, needle probes) to inform early-stage design and/or layout planning'),
('GTR', 'Geotechnical reconnaissance', 'Early-stage reconnaissance geotechnical investigation'),
('GTD', 'Geotechnical detailed design','Detailed-design-stage geotechnical investigation');


CREATE TABLE reference.hole_type (
    hole_type_code VARCHAR(10) PRIMARY KEY,
    hole_type_name TEXT NOT NULL,
    description TEXT
);

INSERT INTO reference.hole_type (hole_type_code, hole_type_name, description)
VALUES
('EH',   'Exploratory hole (composite)', 'Composite exploratory hole comprising both sampling and in situ testing'),
('BH',   'Borehole',                     'Sampling borehole'),
('GS',   'Grab sample',                  'Seabed grab sample'),
('NP',   'Needle probe',                 'Needle probe (thermal conductivity / shallow geophysical)'),
('CPT',  'Cone penetration test',        'Cone penetration test in seabed mode'),
('DCPT', 'Downhole CPT',                 'Cone penetration test in downhole mode'),
('SCPT',  'Seismic cone penetration test',        'Seismic cone penetration test in seabed mode'),
('SDCPT', 'Seismic downhole CPT',                 'Seismic cone penetration test in downhole mode'),
('VC',   'Vibrocore',                    'Vibrocore sample');

