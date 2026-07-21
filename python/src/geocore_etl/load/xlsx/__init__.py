"""geodb_etl.load.xlsx: load-stage modules for .xlsx source formats.

Currently only EHS (`geodb_etl.load.xlsx.ehs`); a future non-EHS .xlsx format
would get its own sibling module here, following the same pattern already
used by `parse.xlsx`, `validate.xlsx`, and `transform.xlsx`.
"""

from __future__ import annotations

from .ehs import EhsLoadResult, load_ehs_transform_result

__all__ = ["EhsLoadResult", "load_ehs_transform_result"]

