"""geodb_etl validation stage entry points.

Syntactic validation (format-native conformance) and semantic validation
(business rules, quarantine on failure) — see
tasks/plan/phase-3b-pipeline-implementation.md Tasks 7/8 for the AGS4/
CPT-JSON design this mirrors. geodb_etl.validate.xlsx and
geodb_etl.validate.pdtable exist so far (EHS xlsx has no separate
syntactic-conformance concept the way AGS4/JSON-Schema do — openpyxl's own
load already proves the file is a readable .xlsx, and geodb_etl.parse.xlsx's
table-header check proves it is structurally an EHS workbook).
"""

from __future__ import annotations

