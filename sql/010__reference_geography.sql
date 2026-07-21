-- =============================================================================
-- Reference data: country, region, sea_area
-- =============================================================================
-- Real, stable lookup data — safe to run against every environment, including
-- production (see geodb/sql/README.md "production-safe vs dev-only" section).

CREATE TABLE reference.country (
    country_code CHAR(2) PRIMARY KEY,
    country_name TEXT NOT NULL
);

INSERT INTO reference.country (country_code, country_name)
VALUES
('AF','Afghanistan'),('AL','Albania'),('DZ','Algeria'),('AD','Andorra'),('AO','Angola'),
('AR','Argentina'),('AM','Armenia'),('AU','Australia'),('AT','Austria'),('AZ','Azerbaijan'),
('BS','Bahamas'),('BH','Bahrain'),('BD','Bangladesh'),('BY','Belarus'),('BE','Belgium'),
('BZ','Belize'),('BJ','Benin'),('BT','Bhutan'),('BO','Bolivia'),('BA','Bosnia and Herzegovina'),
('BW','Botswana'),('BR','Brazil'),('BN','Brunei'),('BG','Bulgaria'),('BF','Burkina Faso'),
('BI','Burundi'),('KH','Cambodia'),('CM','Cameroon'),('CA','Canada'),('CL','Chile'),
('CN','China'),('CO','Colombia'),('CR','Costa Rica'),('HR','Croatia'),('CU','Cuba'),
('CY','Cyprus'),('CZ','Czechia'),('DK','Denmark'),('DO','Dominican Republic'),('EC','Ecuador'),
('EG','Egypt'),('EE','Estonia'),('FI','Finland'),('FR','France'),('DE','Germany'),
('GR','Greece'),('HU','Hungary'),('IS','Iceland'),('IN','India'),('ID','Indonesia'),
('IR','Iran'),('IQ','Iraq'),('IE','Ireland'),('IL','Israel'),('IT','Italy'),
('JP','Japan'),('JO','Jordan'),('KZ','Kazakhstan'),('KE','Kenya'),('KW','Kuwait'),
('LV','Latvia'),('LB','Lebanon'),('LT','Lithuania'),('LU','Luxembourg'),('MY','Malaysia'),
('MX','Mexico'),('MA','Morocco'),('NL','Netherlands'),('NZ','New Zealand'),('NG','Nigeria'),
('NO','Norway'),('PK','Pakistan'),('PE','Peru'),('PH','Philippines'),('PL','Poland'),
('PT','Portugal'),('QA','Qatar'),('RO','Romania'),('RU','Russia'),('SA','Saudi Arabia'),
('RS','Serbia'),('SG','Singapore'),('SK','Slovakia'),('SI','Slovenia'),('ZA','South Africa'),
('KR','South Korea'),('ES','Spain'),('SE','Sweden'),('CH','Switzerland'),('TH','Thailand'),
('TR','Turkey'),('TW','Taiwan'),('UA','Ukraine'),('AE','United Arab Emirates'),
('GB','United Kingdom'),('US','United States'),('VN','Vietnam');


CREATE TABLE reference.region (
    region_code VARCHAR(10) PRIMARY KEY,
    region_name TEXT NOT NULL UNIQUE
);

INSERT INTO reference.region (region_code, region_name)
VALUES
('EUR','Europe'),
('APAC','Asia-Pacific'),
('NAM','North America'),
('SAM','South America'),
('AFR','Africa');


-- Sea area names follow IHO Publication S-23 'Limits of Oceans and Seas'.
-- Codes are an internal convention (no IHO short-code standard exists).
CREATE TABLE reference.sea_area (
    sea_area_code VARCHAR(10) PRIMARY KEY,
    sea_area_name TEXT NOT NULL UNIQUE
);

INSERT INTO reference.sea_area (sea_area_code, sea_area_name)
VALUES
('NSE','North Sea'),
('BAL','Baltic Sea'),
('IRS','Irish Sea'),
('KAT','Kattegat'),
('SKA','Skagerrak'),
('CEL','Celtic Sea'),
('ENG','English Channel'),
('NAO','North Atlantic Ocean'),
('SAO','South Atlantic Ocean'),
('NPO','North Pacific Ocean'),
('SPO','South Pacific Ocean'),
('IND','Indian Ocean'),
('MED','Mediterranean Sea'),
('YEL','Yellow Sea'),
('ECS','East China Sea'),
('SCS','South China Sea'),
('PHS','Philippine Sea'),
('JPS','Sea of Japan'),
('TAS','Tasman Sea'),
('ARA','Arabian Sea'),
('BEN','Bay of Bengal'),
('GME','Gulf of Mexico'),
('GSL','Gulf of St. Lawrence'),
('PER','Persian Gulf');

