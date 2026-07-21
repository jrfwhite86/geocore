"""AGS4 -> geoCore mapping declarations (tasks/plan.md Phase 3, Task 4).

Each submodule declares the field mappings for one AGS4 group in v1 scope
(PROJ, LOCA, SCPG+SCPT) as data — see geodb/python/docs/ags-etl-mapping.md for
the narrative design doc these modules back.

Sibling to geodb_etl.mappings.json (the new CPT "silver" JSON format) — both
subpackages declare mappings using the shared, format-agnostic
geodb_etl.mappings.types shapes (FieldMapping.source_format distinguishes
which format each mapping belongs to).
"""

from __future__ import annotations

from .cpt import (
    CPT_TABLE_CHAIN,
    CPT_UNIT_CONVERSION_GAP,
    SCPG_FIELD_MAPPINGS,
    SCPG_FIELD_MAPPINGS_REVISION_E_EXTRAS,
    SCPT_DEPTH_CONSISTENCY,
    SCPT_FIELD_MAPPINGS,
    SCPT_RATE_REVISION_E_GAP,
)
from .loca import (
    COORDINATE_SANITY_NOTE,
    COORDINATE_SYSTEM_RESOLUTION,
    HOLE_TYPE_RESOLUTION,
    LOCA_FDEP_REQUIRED_IN_REVISION_E,
    LOCA_FIELD_MAPPINGS,
    LOCA_FIELD_MAPPINGS_REVISION_E_EXTRAS,
    LOCA_REVISION_E_UNMAPPED_HEADINGS,
    LOCA_VALIDATION_ONLY_HEADINGS,
    SITE_INVESTIGATION_RESOLUTION,
)
from .proj import (
    PROJ_FIELD_MAPPINGS,
    PROJ_INCONSISTENCY_POLICY,
    PROJ_UNMAPPED_HEADINGS,
    PROJECT_RESOLUTION,
)
from .version import (
    KNOWN_TRAN_AGS_VALUES,
    LOCA_EPSG_NOT_IN_EITHER_DICTIONARY,
    REVISION_E_GAP,
    REVISION_E_TRAN_REM_PATTERN,
    SUPPORTED_AGS_VERSIONS,
    AgsFileVersion,
    UnrecognisedAgsVersionError,
    is_revision_e_marker,
    resolve_ags_file_version,
    resolve_ags_version,
)

__all__ = [
    "PROJ_FIELD_MAPPINGS",
    "PROJECT_RESOLUTION",
    "PROJ_UNMAPPED_HEADINGS",
    "PROJ_INCONSISTENCY_POLICY",
    "LOCA_FIELD_MAPPINGS",
    "LOCA_FIELD_MAPPINGS_REVISION_E_EXTRAS",
    "LOCA_REVISION_E_UNMAPPED_HEADINGS",
    "LOCA_FDEP_REQUIRED_IN_REVISION_E",
    "LOCA_VALIDATION_ONLY_HEADINGS",
    "SITE_INVESTIGATION_RESOLUTION",
    "HOLE_TYPE_RESOLUTION",
    "COORDINATE_SYSTEM_RESOLUTION",
    "COORDINATE_SANITY_NOTE",
    "SCPG_FIELD_MAPPINGS",
    "SCPG_FIELD_MAPPINGS_REVISION_E_EXTRAS",
    "SCPT_FIELD_MAPPINGS",
    "SCPT_RATE_REVISION_E_GAP",
    "CPT_TABLE_CHAIN",
    "SCPT_DEPTH_CONSISTENCY",
    "CPT_UNIT_CONVERSION_GAP",
    "KNOWN_TRAN_AGS_VALUES",
    "SUPPORTED_AGS_VERSIONS",
    "UnrecognisedAgsVersionError",
    "AgsFileVersion",
    "resolve_ags_version",
    "resolve_ags_file_version",
    "is_revision_e_marker",
    "REVISION_E_TRAN_REM_PATTERN",
    "REVISION_E_GAP",
    "LOCA_EPSG_NOT_IN_EITHER_DICTIONARY",
]









