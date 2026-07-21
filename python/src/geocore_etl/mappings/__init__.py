"""geoCore ETL mapping declarations (tasks/plan.md Phase 3, Task 4).

geodb_etl ingests more than one source format (see geodb_etl.mappings.types.
SourceFormat): .types (this package's only direct submodule export) holds the
shared, format-agnostic contract; format-specific mappings live in their own
subpackages:

- geodb_etl.mappings.ags  — AGS4 (established; geodb/python/docs/ags-etl-mapping.md)
- geodb_etl.mappings.json — CPT "silver" JSON (new, under development;
  geodb/python/docs/json-etl-mapping.md)

Deliberately no re-export of format-specific names here (an earlier version of
this module flattened AGS's mappings to the top level; now that a second
format exists, "import from geodb_etl.mappings" would be ambiguous about
which format a name belongs to) — import from the specific subpackage
instead, e.g. `from geodb_etl.mappings.ags.loca import LOCA_FIELD_MAPPINGS` or
`from geodb_etl.mappings.json.cpt import LOCATION_FIELD_MAPPINGS`.
"""

from __future__ import annotations

from .types import FieldMapping, RejectedRow, SourceFormat, UnitConversion, ValidationWarning

__all__ = [
    "FieldMapping",
    "RejectedRow",
    "SourceFormat",
    "UnitConversion",
    "ValidationWarning",
]






