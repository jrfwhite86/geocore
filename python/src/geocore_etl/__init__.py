"""geodb_etl: multi-format -> geoCore ETL pipeline.

Sibling package to geodb_connect inside the same geodb/python project/Pixi
environment (see tasks/plan/architecture-decisions.md) — reuses
geodb_connect.config/db for the actual database connection rather than
duplicating connection logic.

**See geodb/python/docs/geodb_etl-overview.md for the full package guide**,
including a per-format status table and run instructions — this docstring is
intentionally kept short so it doesn't drift out of sync with that doc.

geodb_etl is deliberately format-agnostic (the package was named geodb_etl,
not geodb_ags_etl, specifically for this reason — see
tasks/plan/architecture-decisions.md). Every source format declares its field
mappings as data under geodb_etl.mappings, keyed by
geodb_etl.mappings.types.SourceFormat, and (once implemented) wires
parse -> validate -> transform -> load stages under the matching
{ags,json,xlsx,pdtable} subpackage of each. As of this writing, only the
EHS_XLSX format (geodb_etl.mappings.xlsx.ehs) has all four stages implemented
and a runnable console script (geodb-etl-load-ehs); AGS4, CPT_JSON, and both
pdtable file types (project-input, layout-input) are mapping-design only, or
(pdtable project-input) mapping design plus an implemented load stage with
parse/validate/transform still stubbed — see the overview doc's status table
for the authoritative, current-as-of-last-edit picture, since this changes as
each format's pipeline is completed.
"""

from __future__ import annotations

