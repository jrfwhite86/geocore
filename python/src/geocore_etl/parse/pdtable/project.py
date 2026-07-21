"""pdtable CSV parse stage for project-input (Phase 6, Task 2; implemented in
Phase 6b, see tasks/plan/phase-6b-pdtable-cli-completion.md).

Reads the real fixture via `pdtable.io.csv.read_csv` (installed, `pdtable`
1.0.1) and reshapes its `(BlockType, obj)` stream into a flat
PdtableProjectDocument -- no validation, no transform, no database access
here (mirrors every other format's parse stage).

coordinate_reference_system_by_project / array_area_coordinates_by_project /
export_cable_route_coordinates_by_project are dicts KEYED BY PROJECT CODE
(the pdtable "destination" tag -- see mappings.pdtable.project's module
docstring), not flat row lists -- each of these three blocks repeats once
per project_code within the same file. development_area/project use the
literal {'all'} destination and are collected as flat row lists instead.

Every row dict carries a `_row_number` key (the row's 0-based position within
its own table block) -- required by validate.pdtable.project's row-
attribution contract (RejectedRow.row_number).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from pdtable.io.csv import read_csv
from pdtable.store import BlockType

from ...mappings.pdtable.project import (
    FILE_WIDE_DESTINATION,
    TABLE_ARRAY_AREA_COORDINATES,
    TABLE_COORDINATE_REFERENCE_SYSTEM,
    TABLE_DEVELOPMENT_AREA,
    TABLE_EXPORT_CABLE_ROUTE_COORDINATES,
    TABLE_PROJECT,
)


class PdtableParseError(Exception):
    """Raised when a pdtable CSV cannot be structurally parsed."""


@dataclass(frozen=True)
class PdtableProjectDocument:
    """The parsed, unvalidated contents of one input_project_{area_code}.csv."""

    source_path: Path
    development_area_rows: list[dict[str, object]] = field(default_factory=list)
    project_rows: list[dict[str, object]] = field(default_factory=list)
    coordinate_reference_system_by_project: dict[str, dict[str, object]] = field(
        default_factory=dict
    )
    array_area_coordinates_by_project: dict[str, list[dict[str, object]]] = field(
        default_factory=dict
    )
    export_cable_route_coordinates_by_project: dict[str, list[dict[str, object]]] = field(
        default_factory=dict
    )


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


def _project_destination(table: Any, path: Path) -> str:
    """The per-table `destinations` set (pdtable's own mechanism, repurposed by
    this template to carry a single project_code -- see mappings.pdtable.
    project's module docstring). Exactly one destination is expected for every
    project-scoped block this pipeline reads.
    """

    destinations = table.metadata.destinations
    if len(destinations) != 1:
        raise PdtableParseError(
            f"{path}: table {table.name!r} has an unexpected destinations set "
            f"{destinations!r} -- expected exactly one project_code."
        )
    destination = next(iter(destinations))
    if destination == FILE_WIDE_DESTINATION:
        raise PdtableParseError(
            f"{path}: table {table.name!r} is file-wide ({FILE_WIDE_DESTINATION!r}) "
            "but a per-project destination (project_code) was expected."
        )
    return destination


def parse_pdtable_project_file(path: Path) -> PdtableProjectDocument:
    """Parse one pdtable project-input CSV into a PdtableProjectDocument.

    Raises:
        PdtableParseError: the file doesn't exist, `pdtable` itself cannot
            structurally parse it, or one of the five required table blocks
            (development_area/project/coordinate_reference_system/
            array_area_coordinates/export_cable_route_coordinates) is absent.
    """

    if not path.is_file():
        raise PdtableParseError(f"pdtable CSV not found: {path}")

    try:
        blocks: Iterable[tuple[BlockType, Any]] = list(read_csv(str(path)))
    except Exception as exc:
        raise PdtableParseError(f"failed to parse pdtable CSV {path}: {exc}") from exc

    development_area_rows: list[dict[str, object]] = []
    project_rows: list[dict[str, object]] = []
    coordinate_reference_system_by_project: dict[str, dict[str, object]] = {}
    array_area_coordinates_by_project: dict[str, list[dict[str, object]]] = {}
    export_cable_route_coordinates_by_project: dict[str, list[dict[str, object]]] = {}

    for block_type, obj in blocks:
        if block_type != BlockType.TABLE:
            continue  # METADATA/DIRECTIVE/TEMPLATE_ROW/BLANK: documentation only.

        table = obj
        if table.name == TABLE_DEVELOPMENT_AREA:
            development_area_rows.extend(_rows_from_dataframe(table.df))
        elif table.name == TABLE_PROJECT:
            project_rows.extend(_rows_from_dataframe(table.df))
        elif table.name == TABLE_COORDINATE_REFERENCE_SYSTEM:
            project_code = _project_destination(table, path)
            rows = _rows_from_dataframe(table.df)
            if not rows:
                raise PdtableParseError(
                    f"{path}: {TABLE_COORDINATE_REFERENCE_SYSTEM} block for "
                    f"{project_code!r} has no rows."
                )
            coordinate_reference_system_by_project[project_code] = rows[0]
        elif table.name == TABLE_ARRAY_AREA_COORDINATES:
            project_code = _project_destination(table, path)
            array_area_coordinates_by_project[project_code] = _rows_from_dataframe(table.df)
        elif table.name == TABLE_EXPORT_CABLE_ROUTE_COORDINATES:
            project_code = _project_destination(table, path)
            export_cable_route_coordinates_by_project[project_code] = _rows_from_dataframe(
                table.df
            )
        # Any other table name is out of scope (mappings.pdtable.project.OUT_OF_SCOPE) -- ignored.

    missing = [
        name
        for name, rows in (
            (TABLE_DEVELOPMENT_AREA, development_area_rows),
            (TABLE_PROJECT, project_rows),
            (TABLE_COORDINATE_REFERENCE_SYSTEM, coordinate_reference_system_by_project),
            (TABLE_ARRAY_AREA_COORDINATES, array_area_coordinates_by_project),
            (TABLE_EXPORT_CABLE_ROUTE_COORDINATES, export_cable_route_coordinates_by_project),
        )
        if not rows
    ]
    if missing:
        raise PdtableParseError(f"{path}: missing required table block(s): {', '.join(missing)}")

    return PdtableProjectDocument(
        source_path=path,
        development_area_rows=development_area_rows,
        project_rows=project_rows,
        coordinate_reference_system_by_project=coordinate_reference_system_by_project,
        array_area_coordinates_by_project=array_area_coordinates_by_project,
        export_cable_route_coordinates_by_project=export_cable_route_coordinates_by_project,
    )

