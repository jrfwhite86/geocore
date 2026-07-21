-- =============================================================================
-- Location: development_area
-- =============================================================================
-- Depends on: 010__reference_geography.sql (region, sea_area, country)
-- Production-safe reference data (see geodb/sql/README.md).

CREATE TABLE location.development_area (
    area_id BIGSERIAL PRIMARY KEY,
    area_code VARCHAR(3) NOT NULL UNIQUE CHECK (area_code ~ '^[A-Z]{3}$'),
    area_name TEXT NOT NULL,
    region_code VARCHAR(10) NOT NULL REFERENCES reference.region(region_code) ON DELETE RESTRICT,
    sea_area_code VARCHAR(10) REFERENCES reference.sea_area(sea_area_code) ON DELETE RESTRICT,
    country_code CHAR(2) NOT NULL REFERENCES reference.country(country_code) ON DELETE RESTRICT
);

INSERT INTO location.development_area (area_code, area_name, region_code, sea_area_code, country_code)
VALUES
('ANH','Anholt','EUR','KAT','DK'),
('BAL','Baltica','EUR','BAL','PL'),
('BOW','Barrow','EUR','IRS','GB'),
('BBW','Burbo Bank','EUR','IRS','GB'),
('BKR','Borkum Riffgrund','EUR','NSE','DE'),
('BSW','Borssele','EUR','NSE','NL'),
('CHO','Choshi','APAC','NPO','JP'),
('CHW','Greater Changhua','APAC','SCS','TW'),
('GFS','Gunfleet Sands','EUR','NSE','GB'),
('GIP','Gippsland','APAC','TAS','AU'),
('GOW','Gode Wind','EUR','NSE','DE'),
('HEW','Hesselø','EUR','KAT','DK'),
('HOW','Hornsea','EUR','NSE','GB'),
('HRV','Horns Rev','EUR','NSE','DK'),
('IOW','Incheon','APAC','YEL','KR'),
('LAW','London Array','EUR','NSE','GB'),
('LIC','Lincs','EUR','NSE','GB'),
('NHP','Nysted','EUR','BAL','DK'),
('MVW','Mooir Vannin','EUR','IRS','GB'),
('OCW','Ocean Wind','NAM','NAO','US'),
('REV','Revolution Wind','NAM','NAO','US'),
('ROW','Race Bank','EUR','NSE','GB'),
('SBW','Starboard Wind','NAM','NAO','US'),
('SJW','Skipjack Wind','NAM','NAO','US'),
('SFW','South Fork','NAM','NAO','US'),
('SRW','Sunrise Wind','NAM','NAO','US'),
('VCW','Coastal Virginia Offshore Wind','NAM','NAO','US'),
('WDS','West of Duddon Sands','EUR','IRS','GB'),
('WON','Wo Neng','APAC','SCS','TW'),
('WOW','Walney','EUR','IRS','GB'),
('WMR','Westermost Rough','EUR','NSE','GB'),
('XUF','Xu Feng','APAC','SCS','TW');

