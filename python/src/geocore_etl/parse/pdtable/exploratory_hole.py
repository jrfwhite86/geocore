"""pdtable CSV parse stage for exploratory-hole-input (Phase 10c).

Reads the real fixture via ``pdtable.io.csv.read_csv`` and reshapes its
``(BlockType, obj)`` stream into a flat ``PdtableExploratoryHoleDocument`` --
no validation, no transform, no database access here (mirrors
``parse.pdtable.project``'s single-destination shape rather than
``parse.pdtable.layout``'s per-block-destination shape).

**Structural shape:**

- Exactly one ``**cluster_details`` block. Its pdtable *destination* tag is
  the project_code (e.g. ``OWF01``).
- Exactly one ``**exploratory_hole_details`` block. Its destination tag is
  the SAME project_code -- both blocks are project-scoped, unlike
  ``input_layout.csv``'s per-``layout_code`` blocks.

The parser raises ``PdtableExploratoryHoleParseError`` for structural
problems (file missing, ``pdtable`` cannot parse it, either required block
absent, a block has a blank / file-wide destination, or the two blocks'
destinations disagree with each other).

Every row dict carries a ``_row_number`` key (the row's 0-based position
within its own table block) -- required by ``validate.pdtable.
exploratory_hole``'s row-attribution contract.

Non-structural, silently-repaired cell/row problems (e.g. an illegal cell
value ``pdtable`` coerced to NaN) do NOT raise -- they are instead collected
into ``PdtableExploratoryHoleDocument.parse_warnings`` (see
``parse.pdtable._fixer.SilentParseFixer``) so callers can report exactly what
was fixed, rather than just the aggregate count ``pdtable`` itself prints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

# pdtable 1.0.1's fixer.py references ``np.NaN``, removed in numpy 2.0.
# Restore the alias if it is missing so ``read_csv`` can handle blank
# cells in float columns (identical shim to parse.pdtable.layout's).
if not hasattr(np, "NaN"):
    np.NaN = np.nan  # type: ignore[attr-defined]

import pandas as pd  # noqa: E402
from pdtable.io.csv import read_csv  # noqa: E402
from pdtable.store import BlockType  # noqa: E402

from ...mappings.pdtable.exploratory_hole import (  # noqa: E402
    TABLE_CLUSTER_DETAILS,
    TABLE_EXPLORATORY_HOLE_DETAILS,
)
from ...mappings.pdtable.project import FILE_WIDE_DESTINATION  # noqa: E402
from ._fixer import SilentParseFixer  # noqa: E402


class PdtableExploratoryHoleParseError(Exception):
    """Raised when a pdtable exploratory-hole CSV cannot be structurally parsed."""


@dataclass(frozen=True)
class PdtableExploratoryHoleDocument:
    """The parsed, unvalidated contents of one input_exploratory_holes_{area_code}.csv."""

    source_path: Path
    project_code: str
    cluster_details_rows: list[dict[str, object]] = field(default_factory=list)
    exploratory_hole_details_rows: list[dict[str, object]] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)
    """Detailed messages for every cell/row ``pdtable``'s ``ParseFixer`` silently
    repaired (e.g. an illegal cell value coerced to NaN) -- see
    ``parse.pdtable._fixer.SilentParseFixer``'s docstring for why these must be
    captured here rather than relying on ``pdtable``'s own aggregate-count
    print."""


def _clean_value(value: Any) -> Any:
    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _rows_from_dataframe(df: pd.DataFrame) -> list[dict[str, object]]:
    return [
        {"_row_number": row_number, **{k: _clean_value(v) for k, v in record.items()}}
        for row_number, record in enumerate(df.to_dict(orient="records"))
    ]


def _table_project_code(table: Any, path: Path) -> str:
    """Read the single non-file-wide destination tag off a table block --
    both blocks in this file use it as the project_code."""

    destinations = table.metadata.destinations
    if len(destinations) != 1:
        raise PdtableExploratoryHoleParseError(
            f"{path}: table {table.name!r} has an unexpected destinations set "
            f"{destinations!r} -- expected exactly one non-file-wide destination."
        )
    destination = next(iter(destinations))
    if destination == FILE_WIDE_DESTINATION:
        raise PdtableExploratoryHoleParseError(
            f"{path}: table {table.name!r} is file-wide ({FILE_WIDE_DESTINATION!r}) "
            "but a per-project destination (the project_code) was expected."
        )
    return destination


def parse_pdtable_exploratory_hole_file(path: Path) -> PdtableExploratoryHoleDocument:
    """Parse one pdtable exploratory-hole-input CSV.

    Raises:
        PdtableExploratoryHoleParseError: the file doesn't exist,
            ``pdtable`` itself cannot structurally parse it, either
            required block is absent, a block has more than one or a
            file-wide destination, or the two blocks' destinations
            disagree with each other.
    """

    if not path.is_file():
        raise PdtableExploratoryHoleParseError(f"pdtable CSV not found: {path}")

    try:
        fixer = SilentParseFixer()
        fixer.stop_on_errors = 0
        fixer._dbg = False
        blocks: list[tuple[BlockType, Any]] = list(read_csv(str(path), fixer=fixer))
    except Exception as exc:
        raise PdtableExploratoryHoleParseError(
            f"failed to parse pdtable CSV {path}: {exc}"
        ) from exc

    cluster_rows: list[dict[str, object]] | None = None
    cluster_project_code: str | None = None
    hole_rows: list[dict[str, object]] | None = None
    hole_project_code: str | None = None

    for block_type, obj in blocks:
        if block_type != BlockType.TABLE:
            continue

        table = obj
        if table.name == TABLE_CLUSTER_DETAILS:
            if cluster_rows is not None:
                raise PdtableExploratoryHoleParseError(
                    f"{path}: more than one **{TABLE_CLUSTER_DETAILS} block found -- "
                    "exactly one is expected."
                )
            cluster_project_code = _table_project_code(table, path)
            cluster_rows = _rows_from_dataframe(table.df)
        elif table.name == TABLE_EXPLORATORY_HOLE_DETAILS:
            if hole_rows is not None:
                raise PdtableExploratoryHoleParseError(
                    f"{path}: more than one **{TABLE_EXPLORATORY_HOLE_DETAILS} block "
                    "found -- exactly one is expected."
                )
            hole_project_code = _table_project_code(table, path)
            hole_rows = _rows_from_dataframe(table.df)
        # Any other table name is out of scope -- ignored.

    if cluster_rows is None or cluster_project_code is None:
        raise PdtableExploratoryHoleParseError(
            f"{path}: missing required **{TABLE_CLUSTER_DETAILS} block."
        )
    if hole_rows is None or hole_project_code is None:
        raise PdtableExploratoryHoleParseError(
            f"{path}: missing required **{TABLE_EXPLORATORY_HOLE_DETAILS} block."
        )
    if cluster_project_code != hole_project_code:
        raise PdtableExploratoryHoleParseError(
            f"{path}: **{TABLE_CLUSTER_DETAILS} destination "
            f"{cluster_project_code!r} does not match "
            f"**{TABLE_EXPLORATORY_HOLE_DETAILS} destination "
            f"{hole_project_code!r} -- both blocks must be scoped to the "
            "same project_code."
        )

    return PdtableExploratoryHoleDocument(
        source_path=path,
        project_code=cluster_project_code,
        cluster_details_rows=cluster_rows,
        exploratory_hole_details_rows=hole_rows,
        parse_warnings=list(fixer.messages),
    )
