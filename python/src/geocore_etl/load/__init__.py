"""geodb_etl.load: the only geodb_etl package that touches the database.

Split into one module per source format (mirroring `parse/`, `validate/`,
`transform/`, and `cli/`'s `{xlsx,pdtable}/...` layout) per
`tasks/plan/codebase-structure-cleanup.md`. `LoadError` stays here, shared
across every format's load module, per `tasks/plan/phase-3b-pipeline-
implementation.md` Task 9's original intent that FK-resolution failures use
one common exception type regardless of source format.

`load_ehs_transform_result`/`EhsLoadResult` live in `load.xlsx.ehs`;
`load_pdtable_project_transform_result`/`PdtableProjectLoadResult` and
`load_pdtable_layout_transform_result`/`PdtableLayoutLoadResult` live in
`load.pdtable.project`/`load.pdtable.layout` -- all re-exported here so
existing callers (`from geodb_etl.load import load_ehs_transform_result`, etc.)
keep working unchanged.

Resolves FKs (project_id, coordinate_system_id) via lookup against already-
seeded reference/project data, with an explicit LoadError (never a raw
IntegrityError bubbling up unexplained) for an unresolvable one. One
transaction per file: a partially-failed load rolls back, never leaves
geotech/project half-populated.
"""

from __future__ import annotations


class LoadError(Exception):
    """Raised for a pre-flight or FK-resolution failure during load.

    Never raised for a row-level data-quality problem — those are caught
    earlier (geodb_etl.validate.xlsx) and never reach this stage.
    """


# Imported after LoadError is defined: load.xlsx.ehs / load.pdtable.project
# both do `from .. import LoadError` (a same-package circular import that
# only resolves if LoadError already exists on this module by the time
# those submodules are imported).
from .pdtable import (  # noqa: E402
    PdtableExploratoryHoleLoadResult,
    PdtableLayoutLoadResult,
    PdtableProjectLoadResult,
    load_pdtable_exploratory_hole_transform_result,
    load_pdtable_layout_transform_result,
    load_pdtable_project_transform_result,
)
from .xlsx import EhsLoadResult, load_ehs_transform_result  # noqa: E402

__all__ = [
    "LoadError",
    "EhsLoadResult",
    "load_ehs_transform_result",
    "PdtableProjectLoadResult",
    "load_pdtable_project_transform_result",
    "PdtableLayoutLoadResult",
    "load_pdtable_layout_transform_result",
    "PdtableExploratoryHoleLoadResult",
    "load_pdtable_exploratory_hole_transform_result",
]


