"""pdtable CSV parse stage for layout-input (Phase 10b rewrite; multi-project
support added -- see mappings.pdtable.layout.MULTI_PROJECT_DESTINATION_CONVENTION).

Reads the real fixture via ``pdtable.io.csv.read_csv`` and reshapes its
``(BlockType, obj)`` stream into a flat ``PdtableLayoutDocument`` -- no
validation, no transform, no database access here (mirrors
``parse.pdtable.project``'s shape).

**Structural shape:**

- N ``**layout_details`` blocks -- one per project sharing this file's
  area_code (e.g. ``input_layout_HEW.csv`` has both ``HEW01`` and
  ``HEW02``). Each block's pdtable *destination* tag is that project's
  project_code, captured as the key of
  ``PdtableLayoutDocument.layout_details_rows_by_project`` so
  ``load.pdtable.layout`` can resolve every referenced ``project_id``
  without a separate CLI flag (same convention as
  ``parse.pdtable.project``'s per-project blocks). A project_code may not
  repeat across blocks in the same file.
- N ``**layout_configuration`` blocks -- one per (project, layout revision)
  that has positions defined. Each block's *destination* is TWO
  space-separated tags -- the owning project_code AND the layout_code (e.g.
  a destination cell reading ``HEW02 L001``) -- resolved against the
  project_codes already seen from this file's own ``**layout_details``
  blocks (collected in a first pass so declaration order doesn't matter).
  Rows collected into ``layout_configuration_rows_by_project``, a
  dict-of-dicts keyed first by project_code then by that block's own
  layout_code. See mappings.pdtable.layout.MULTI_PROJECT_DESTINATION_CONVENTION
  for the full rationale.

Why the dict-of-dicts-of-lists shape? Every asset row's owning
(project_code, layout_code) is fixed by the block it lives in. Keeping the
block-per-layout structure at parse time is the cheapest way to preserve
that attribution unchanged all the way down to load, where it is needed to
resolve the correct ``project.layout_asset.layout_id`` (scoped to the right
project). Flattening the rows here would either throw the attribution away
or force every row to carry extra synthetic project_code/layout_code
columns.

The parser raises ``PdtableLayoutParseError`` for structural problems (file
missing, ``pdtable`` cannot parse it, no ``**layout_details`` block present,
a duplicate project_code across ``**layout_details`` blocks, a
``**layout_configuration`` block whose destination isn't exactly two
non-file-wide tags with one resolving to a known project_code, or a
duplicate (project_code, layout_code) pair). It does NOT cross-check
layout_configuration destinations' layout_code against layout_details'
``layout_code`` column -- that is a validate/load stage concern once the
layout_details rows have themselves been validated.

Every row dict carries a ``_row_number`` key (the row's 0-based position
within its own table block) -- required by ``validate.pdtable.layout``'s
row-attribution contract (``RejectedRow.row_number``).

Non-structural, silently-repaired cell/row problems (e.g. a blank cell in a
float column coerced to NaN) do NOT raise -- they are instead collected into
``PdtableLayoutDocument.parse_warnings`` (see
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
# cells in float columns (e.g. blank optional cells in
# input_layout_OWF.csv). Upstream fix pending.
if not hasattr(np, "NaN"):
    np.NaN = np.nan  # type: ignore[attr-defined]

import pandas as pd  # noqa: E402
from pdtable.io.csv import read_csv  # noqa: E402
from pdtable.store import BlockType  # noqa: E402

from ...mappings.pdtable.layout import (  # noqa: E402
    TABLE_LAYOUT_CONFIGURATION,
    TABLE_LAYOUT_DETAILS,
)
from ...mappings.pdtable.project import FILE_WIDE_DESTINATION  # noqa: E402
from ._fixer import SilentParseFixer  # noqa: E402


class PdtableLayoutParseError(Exception):
    """Raised when a pdtable layout CSV cannot be structurally parsed."""


@dataclass(frozen=True)
class PdtableLayoutDocument:
    """The parsed, unvalidated contents of one input_layout_{area_code}.csv.

    May cover multiple projects sharing the same area_code -- see this
    module's docstring and mappings.pdtable.layout.MULTI_PROJECT_DESTINATION_CONVENTION.
    """

    source_path: Path
    layout_details_rows_by_project: dict[str, list[dict[str, object]]] = field(
        default_factory=dict
    )
    layout_configuration_rows_by_project: dict[str, dict[str, list[dict[str, object]]]] = field(
        default_factory=dict
    )
    parse_warnings: list[str] = field(default_factory=list)
    """Detailed messages for every cell/row ``pdtable``'s ``ParseFixer`` silently
    repaired -- see ``parse.pdtable._fixer.SilentParseFixer``'s docstring for why
    these must be captured here rather than relying on ``pdtable``'s own
    aggregate-count print."""


def _clean_value(value: Any) -> Any:
    """pdtable/pandas represent a blank numeric cell as float NaN -- normalise
    that to None so downstream stages never need to special-case NaN.
    """

    if isinstance(value, float) and pd.isna(value):
        return None
    return value


def _rows_from_dataframe(df: pd.DataFrame) -> list[dict[str, object]]:
    return [
        {"_row_number": row_number, **{k: _clean_value(v) for k, v in record.items()}}
        for row_number, record in enumerate(df.to_dict(orient="records"))
    ]


def _non_file_wide_destinations(table: Any, path: Path) -> set[str]:
    """The per-table pdtable ``destinations`` set, with the file-wide
    ``{'all'}`` tag rejected -- every table this parser reads must carry at
    least one real (non-file-wide) destination tag.
    """

    destinations = set(table.metadata.destinations)
    if destinations == {FILE_WIDE_DESTINATION}:
        raise PdtableLayoutParseError(
            f"{path}: table {table.name!r} is file-wide ({FILE_WIDE_DESTINATION!r}) "
            "but a per-block destination was expected."
        )
    destinations.discard(FILE_WIDE_DESTINATION)
    return destinations


def _layout_details_project_code(table: Any, path: Path) -> str:
    """A **layout_details block's destination is exactly one tag: the
    project_code it belongs to.
    """

    destinations = _non_file_wide_destinations(table, path)
    if len(destinations) != 1:
        raise PdtableLayoutParseError(
            f"{path}: table {table.name!r} has an unexpected destinations set "
            f"{destinations!r} -- expected exactly one project_code."
        )
    return next(iter(destinations))


def _layout_configuration_destination_tags(table: Any, path: Path) -> set[str]:
    """A **layout_configuration block's destination is exactly two tags:
    the owning project_code and the layout_code (in either order) -- see
    mappings.pdtable.layout.MULTI_PROJECT_DESTINATION_CONVENTION.
    """

    destinations = _non_file_wide_destinations(table, path)
    if len(destinations) != 2:
        raise PdtableLayoutParseError(
            f"{path}: table {table.name!r} has an unexpected destinations set "
            f"{destinations!r} -- expected exactly two tags (project_code and "
            "layout_code), e.g. a destination cell reading 'HEW02 L001'."
        )
    return destinations


def parse_pdtable_layout_file(path: Path) -> PdtableLayoutDocument:
    """Parse one pdtable layout-input CSV into a ``PdtableLayoutDocument``.

    Raises:
        PdtableLayoutParseError: the file doesn't exist, ``pdtable`` itself
            cannot structurally parse it, no ``**layout_details`` block is
            present, a project_code repeats across ``**layout_details``
            blocks, no ``**layout_configuration`` block is present anywhere
            in the file, a ``**layout_configuration`` block's destination
            isn't exactly two non-file-wide tags with exactly one of them
            resolving to a project_code already seen from this file's own
            ``**layout_details`` blocks, or a (project_code, layout_code)
            pair repeats across ``**layout_configuration`` blocks.
    """

    if not path.is_file():
        raise PdtableLayoutParseError(f"pdtable CSV not found: {path}")

    try:
        fixer = SilentParseFixer()
        # Blank cells in float columns (e.g. blank optional cells in the
        # OWF fixture) are semantically "no value" -- treat them as NaN /
        # None and continue parsing, rather than stopping after the pdtable
        # default fixer's stop_on_errors threshold.
        fixer.stop_on_errors = 0
        fixer._dbg = False
        blocks: list[tuple[BlockType, Any]] = list(read_csv(str(path), fixer=fixer))
    except Exception as exc:
        raise PdtableLayoutParseError(f"failed to parse pdtable CSV {path}: {exc}") from exc

    layout_details_rows_by_project: dict[str, list[dict[str, object]]] = {}

    # Pass 1: every **layout_details block, across all projects -- must be
    # collected before **layout_configuration blocks are resolved (below),
    # so declaration order within the file doesn't matter.
    for block_type, obj in blocks:
        if block_type != BlockType.TABLE or obj.name != TABLE_LAYOUT_DETAILS:
            continue
        table = obj
        project_code = _layout_details_project_code(table, path)
        if project_code in layout_details_rows_by_project:
            raise PdtableLayoutParseError(
                f"{path}: more than one **{TABLE_LAYOUT_DETAILS} block found for "
                f"project_code {project_code!r} -- exactly one is expected per project."
            )
        layout_details_rows_by_project[project_code] = _rows_from_dataframe(table.df)

    if not layout_details_rows_by_project:
        raise PdtableLayoutParseError(
            f"{path}: missing required **{TABLE_LAYOUT_DETAILS} block."
        )

    known_project_codes = set(layout_details_rows_by_project)

    # Pass 2: every **layout_configuration block, resolved against the
    # project_codes collected above.
    layout_configuration_rows_by_project: dict[str, dict[str, list[dict[str, object]]]] = {}
    for block_type, obj in blocks:
        if block_type != BlockType.TABLE or obj.name != TABLE_LAYOUT_CONFIGURATION:
            continue
        table = obj
        tags = _layout_configuration_destination_tags(table, path)
        matched_projects = tags & known_project_codes
        if len(matched_projects) != 1:
            raise PdtableLayoutParseError(
                f"{path}: table {table.name!r}'s destination tags {tags!r} must "
                "contain exactly one project_code matching a **"
                f"{TABLE_LAYOUT_DETAILS} block in this file (known project_codes: "
                f"{sorted(known_project_codes)}) -- got {sorted(matched_projects)}."
            )
        project_code = next(iter(matched_projects))
        layout_code = next(iter(tags - {project_code}))

        project_configs = layout_configuration_rows_by_project.setdefault(project_code, {})
        if layout_code in project_configs:
            raise PdtableLayoutParseError(
                f"{path}: more than one **{TABLE_LAYOUT_CONFIGURATION} block "
                f"has destination ({project_code!r}, {layout_code!r}) -- each "
                "(project_code, layout_code) pair may have at most one "
                "layout_configuration block per file."
            )
        project_configs[layout_code] = _rows_from_dataframe(table.df)

    if not layout_configuration_rows_by_project:
        raise PdtableLayoutParseError(
            f"{path}: no **{TABLE_LAYOUT_CONFIGURATION} block found -- at "
            "least one is required."
        )
    # Any other table name is out of scope (mappings.pdtable.layout.OUT_OF_SCOPE) -- ignored.

    return PdtableLayoutDocument(
        source_path=path,
        layout_details_rows_by_project=layout_details_rows_by_project,
        layout_configuration_rows_by_project=layout_configuration_rows_by_project,
        parse_warnings=list(fixer.messages),
    )
