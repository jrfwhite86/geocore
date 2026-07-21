-- =============================================================================
-- Location: boundary, project_boundary, boundary_vertex — Hesselø (HEW) array areas
-- =============================================================================
-- Depends on: 040__project_project.sql (projects 'HEW01', 'HEW02'),
--             050__reference_boundary_enums.sql (coordinate_system EPSG 25832/10549)
--             060__location_boundary.sql (table shapes + closure trigger)
-- Production-safe reference data (see geodb/sql/README.md): real, publicly
-- published array-area boundary coordinates for the Hesselø offshore wind
-- development area (ETRS89 / UTM zone 32N, EPSG:25832 horizontal), not
-- fictional/illustrative data (unlike geodb/sample-data/sql/demo-boundary-how04.sql).

INSERT INTO location.boundary (boundary_name, boundary_type_code, coordinate_system_id)
SELECT v.boundary_name, 'ARRAY', cs.coordinate_system_id
FROM reference.coordinate_system cs
CROSS JOIN (VALUES
    ('HEW01 array area'),
    ('HEW02 array area')
) AS v(boundary_name)
WHERE cs.epsg_code_horizontal = 25832
  AND cs.horizontal_unit = 'm'
  AND cs.epsg_code_vertical = 10549
  AND cs.vertical_unit = 'm'
ON CONFLICT (boundary_name) DO NOTHING;

INSERT INTO location.project_boundary (project_id, boundary_id)
SELECT p.project_id, b.boundary_id
FROM (VALUES
    ('HEW01', 'HEW01 array area'),
    ('HEW02', 'HEW02 array area')
) AS v(project_code, boundary_name)
JOIN project.project p ON p.project_code = v.project_code
JOIN location.boundary b ON b.boundary_name = v.boundary_name
ON CONFLICT DO NOTHING;

-- HEW01 (Nord) array area vertices — ETRS89 UTM32N (m), per points OWF 1..7 (closed ring).
INSERT INTO location.boundary_vertex (boundary_id, vertex_no, easting_m, northing_m)
SELECT b.boundary_id, v.vertex_no, v.easting_m, v.northing_m
FROM location.boundary b
CROSS JOIN (VALUES
    (1, 680433, 6247210),
    (2, 664326, 6256983),
    (3, 675002, 6274480),
    (4, 677460, 6278554),
    (5, 679510, 6254602),
    (6, 683606, 6249200),
    (7, 680433, 6247210)
) AS v(vertex_no, easting_m, northing_m)
WHERE b.boundary_name = 'HEW01 array area'
ON CONFLICT (boundary_id, vertex_no) DO UPDATE
SET easting_m = EXCLUDED.easting_m,
    northing_m = EXCLUDED.northing_m;

-- HEW02 (Syd) array area vertices — EUREF89 UTM32N (m), per points 1..7 (closed ring).
INSERT INTO location.boundary_vertex (boundary_id, vertex_no, easting_m, northing_m)
SELECT b.boundary_id, v.vertex_no, v.easting_m, v.northing_m
FROM location.boundary b
CROSS JOIN (VALUES
    (1, 685000, 6249100),
    (2, 684000, 6243500),
    (3, 668400, 6241300),
    (4, 662500, 6237500),
    (5, 653000, 6237300),
    (6, 650600, 6241900),
    (7, 662800, 6262600),
    (8, 685000, 6249100)
) AS v(vertex_no, easting_m, northing_m)
WHERE b.boundary_name = 'HEW02 array area'
ON CONFLICT (boundary_id, vertex_no) DO UPDATE
SET easting_m = EXCLUDED.easting_m,
    northing_m = EXCLUDED.northing_m;


