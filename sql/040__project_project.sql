-- =============================================================================
-- Project: project
-- =============================================================================
-- Depends on: 020__reference_project_enums.sql, 030__location_development_area.sql
-- Production-safe reference data: this is the real catalog of offshore wind
-- projects (not fictional) — see geodb/sql/README.md.

CREATE TABLE project.project (
    project_id BIGSERIAL PRIMARY KEY,
    area_id BIGINT NOT NULL REFERENCES location.development_area(area_id) ON DELETE RESTRICT,
    project_code VARCHAR(5) NOT NULL UNIQUE CHECK (project_code ~ '^[A-Z]{3}[0-9]{2}$'),
    project_name TEXT NOT NULL,
    capacity_mw NUMERIC(8,2) CHECK (capacity_mw IS NULL OR capacity_mw > 0),
    number_of_turbines INTEGER CHECK (number_of_turbines IS NULL OR number_of_turbines > 0),
    foundation_type_code VARCHAR(10) REFERENCES reference.foundation_type(foundation_type_code) ON DELETE RESTRICT,
    project_status_code VARCHAR(10) REFERENCES reference.project_status(project_status_code) ON DELETE RESTRICT
);

-- Project inserts look up area_id via area_code so they remain insert-order-independent.
INSERT INTO project.project (area_id, project_code, project_name, capacity_mw, number_of_turbines, foundation_type_code, project_status_code)
SELECT da.area_id, v.project_code, v.project_name, v.capacity_mw, v.number_of_turbines, v.foundation_type_code, v.project_status_code
FROM (VALUES
    ('ANH','ANH01','Anholt',                            400::numeric, 111, 'MP',   'FC'),
    ('BAL','BAL02','Baltica 2',                         1500::numeric, 107, 'MP',   'AF'),
    ('BAL','BAL03','Baltica 3',                         NULL::numeric, NULL, NULL,  'AF'),
    ('BOW','BOW01','Barrow',                            90::numeric,  30,  'MP',   'FC'),
    ('BBW','BBW01','Burbo Bank',                        90::numeric,  25,  'MP',   'FC'),
    ('BBW','BBW02','Burbo Bank Extension',              258::numeric, 32,  'MP',   'FC'),
    ('BKR','BKR01','Borkum Riffgrund 1',                312::numeric, 78,  'MULT', 'FC'),
    ('BKR','BKR02','Borkum Riffgrund 2',                450::numeric, 56,  'MULT', 'FC'),
    ('BKR','BKR03','Borkum Riffgrund 3',                913::numeric, 83,  'MP',   'UC'),
    ('BSW','BSW01','Borssele 1',                        376::numeric, 47,  'MP',   'FC'),
    ('BSW','BSW02','Borssele 2',                        376::numeric, 47,  'MP',   'FC'),
    ('BSW','BSW03','Borssele 3',                        351.5,        37,  'MP',   'FC'),
    ('BSW','BSW04','Borssele 4',                        380::numeric, 40,  'MP',   'FC'),
    ('CHO','CHO01','Choshi 1',                          NULL::numeric, NULL, NULL, NULL),
    ('CHW','CHW01','Greater Changhua 1',                600::numeric, 75,  'PJ',   'FC'),
    ('CHW','CHW02','Greater Changhua 2a',               288::numeric, 36,  'PJ',   'FC'),
    ('CHW','CHW22','Greater Changhua 2b',               336::numeric, 24,  'SBJ',  'UC'),
    ('CHW','CHW03','Greater Changhua 3',                NULL::numeric, NULL, NULL, 'AF'),
    ('CHW','CHW04','Greater Changhua 4',                588::numeric, 42,  'SBJ',  'UC'),
    ('GFS','GFS01','Gunfleet Sands 1',                  108::numeric, 30,  'MP',   'FC'),
    ('GFS','GFS02','Gunfleet Sands 2',                  65::numeric,  18,  'MP',   'FC'),
    ('GFS','GFS03','Gunfleet Sands 3',                  24::numeric,  2,   'MP',   'FC'),
    ('GIP','GIP01','Gippsland 1',                       NULL::numeric, NULL, NULL, 'AF'),
    ('GIP','GIP02','Gippsland 2',                       NULL::numeric, NULL, NULL, 'AF'),
    ('GOW','GOW01','Gode Wind 1',                       330::numeric, 55,  'MP',   'FC'),
    ('GOW','GOW02','Gode Wind 2',                       252::numeric, 42,  'MP',   'FC'),
    ('GOW','GOW03','Gode Wind 3',                       253::numeric, 23,  'MP',   'FC'),
    ('GOW','GOW04','Gode Wind 4',                       NULL::numeric, NULL, NULL, NULL),
    ('HEW','HEW01','Hesselø 1 (Nord)',                  1005::numeric, NULL, 'FIXED', 'CA'),
    ('HEW','HEW02','Hesselø 2 (Syd)',                  800::numeric, 44, 'MP', 'AF'),
    ('HOW','HOW01','Hornsea 1',                         1218::numeric, 174, 'MP',   'FC'),
    ('HOW','HOW02','Hornsea 2',                         1320::numeric, 165, 'MP',   'FC'),
    ('HOW','HOW03','Hornsea 3',                         2896::numeric, 197, 'MP',   'UC'),
    ('HOW','HOW04','Hornsea 4',                         NULL::numeric, NULL, NULL, 'AF'),
    ('HRV','HRV02','Horns Rev 2',                       209::numeric, 91,  'MP',   'FC'),
    ('HRV','HRV03','Horns Rev 3',                       404::numeric, 49,  'MP',   'FC'),
    ('IOW','IOW01','Incheon 1',                         NULL::numeric, NULL, NULL, 'AF'),
    ('IOW','IOW02','Incheon 2',                         NULL::numeric, NULL, NULL, 'AF'),
    ('LAW','LAW01','London Array 1',                    630::numeric, 175, 'MP',   'FC'),
    ('LIC','LIC01','Lincs 1',                           270::numeric, 75,  'MP',   'FC'),
    ('NHP','NHP01','Nysted 1',                          166::numeric, 72,  'GBS',  'FC'),
    ('MVW','MVW01','Mooir Vannin 1',                    NULL::numeric, NULL, NULL, 'AF'),
    ('OCW','OCW01','Ocean Wind 1',                      NULL::numeric, NULL, NULL, 'CA'),
    ('OCW','OCW02','Ocean Wind 2',                      NULL::numeric, NULL, NULL, 'CA'),
    ('REV','REV01','Revolution Wind 1',                 715::numeric, 65,  'MP',   'UC'),
    ('ROW','ROW01','Race Bank 1',                       546::numeric, 91,  'MP',   'FC'),
    ('SBW','SBW01','Starboard Wind 1',                  NULL::numeric, NULL, NULL, 'AF'),
    ('SFW','SFW01','South Fork 1',                      NULL::numeric, NULL, NULL, 'AF'),
    ('SJW','SJW01','Skipjack Wind 1',                   NULL::numeric, NULL, NULL, 'AF'),
    ('SJW','SJW02','Skipjack Wind 2',                   NULL::numeric, NULL, NULL, 'AF'),
    ('SRW','SRW01','Sunrise Wind 1',                    924::numeric, 84,  'MP',   'UC'),
    ('VCW','VCW01','Coastal Virginia Offshore Wind 1',  NULL::numeric, NULL, NULL, NULL),
    ('WDS','WDS01','West of Duddon Sands 1',            389::numeric, 108, 'MP',   'FC'),
    ('WON','WON01','Wo Neng 1',                         NULL::numeric, NULL, NULL, NULL),
    ('WON','WON02','Wo Neng 2',                         NULL::numeric, NULL, NULL, NULL),
    ('WOW','WOW01','Walney 1',                          184::numeric, 51,  'MP',   'FC'),
    ('WOW','WOW02','Walney 2',                          184::numeric, 51,  'MP',   'FC'),
    ('WOW','WOW03','Walney 3 Extension',                296::numeric, 39,  'MP',   'FC'),
    ('WOW','WOW04','Walney 4 Extension',                363::numeric, 48,  'MP',   'FC'),
    ('WMR','WMR01','Westermost Rough 1',                210::numeric, 35,  'MP',   'FC'),
    ('XUF','XUF01','Xu Feng 1',                         NULL::numeric, NULL, NULL, 'AF'),
    ('XUF','XUF02','Xu Feng 2',                         NULL::numeric, NULL, NULL, 'AF'),
    ('XUF','XUF03','Xu Feng 3',                         NULL::numeric, NULL, NULL, 'AF')
) AS v(area_code, project_code, project_name, capacity_mw, number_of_turbines, foundation_type_code, project_status_code)
JOIN location.development_area da ON da.area_code = v.area_code;

