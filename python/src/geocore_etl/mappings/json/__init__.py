"""CPT "silver" JSON -> geoCore mapping declarations (new format, under development).

See geodb/python/docs/json-etl-mapping.md for narrative rationale, and
geodb_etl.mappings.ags for the sibling AGS4 mapping package this parallels.
"""

from __future__ import annotations

from .cpt import (
    COORDINATE_SYSTEM_GAP,
    CPT_JSON_OPTIONAL_TABLES,
    CPT_JSON_TABLE_CHAIN,
    INTERVAL_METHOD_CASE_QUIRK,
    LOCATION_FIELD_MAPPINGS,
    LOCATION_VALIDATION_ONLY_FIELDS,
    LOGGED_DATA_DEPTH_CONSISTENCY,
    LOGGED_DATA_FIELD_MAPPINGS,
    PUSH_FIELD_MAPPINGS,
    SEISMIC_DATA_FIELD_MAPPINGS,
    SITE_INVESTIGATION_RESOLUTION,
    TEST_FIELD_MAPPINGS,
)

__all__ = [
    "LOCATION_FIELD_MAPPINGS",
    "LOCATION_VALIDATION_ONLY_FIELDS",
    "COORDINATE_SYSTEM_GAP",
    "SITE_INVESTIGATION_RESOLUTION",
    "TEST_FIELD_MAPPINGS",
    "PUSH_FIELD_MAPPINGS",
    "LOGGED_DATA_FIELD_MAPPINGS",
    "SEISMIC_DATA_FIELD_MAPPINGS",
    "CPT_JSON_TABLE_CHAIN",
    "CPT_JSON_OPTIONAL_TABLES",
    "LOGGED_DATA_DEPTH_CONSISTENCY",
    "INTERVAL_METHOD_CASE_QUIRK",
]

