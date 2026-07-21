-- =============================================================================
-- Reference data: position_context
-- =============================================================================
-- Depends on: 001__schemas.sql
-- Production-safe reference data (see geodb/sql/README.md).
--
-- Classifies the kind of position a geotech.exploratory_hole (120__) occupies,
-- derived from which of its three mutually-exclusive linkage columns
-- (layout_asset_id / asset_location_id / cluster_location_id) is populated:
--   ASSET      -- sited at a physical OWF asset (layout_asset or asset_location)
--   CLUSTER    -- belongs to a geotechnical cluster location (geotech.cluster_location)
--   STANDALONE -- tied to neither (e.g. a one-off seabed CPT in a GTL/GTP campaign)
-- geotech.exploratory_hole.position_context_code (120__) is a generated column
-- derived from that linkage, so this table exists purely to describe the three
-- values and give them an FK-able, indexable home — it is never written to
-- directly by ETL.
CREATE TABLE reference.position_context (
    position_context_code VARCHAR(10) PRIMARY KEY,
    position_context_name TEXT NOT NULL,
    description TEXT
);

INSERT INTO reference.position_context (position_context_code, position_context_name, description)
VALUES
('ASSET',      'Asset position',      'Hole sited at a physical OWF asset (via layout_asset or asset_location)'),
('CLUSTER',    'Cluster position',    'Hole belonging to a geotechnical cluster location (geotech.cluster_location)'),
('STANDALONE', 'Standalone position', 'Hole not tied to any asset or cluster (e.g. a single seabed CPT in a GTL/GTP campaign)');
