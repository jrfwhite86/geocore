"""Command-line entry point for loading a pdtable layout-input CSV into geoCore.

Installed as the `geodb-etl-load-layout` console script (see pyproject.toml).
Wires the four pipeline stages together end to end:

    parse.pdtable.parse_pdtable_layout_file
      -> validate.pdtable.validate_pdtable_layout_document
      -> transform.pdtable.transform_pdtable_layout_document
      -> load.load_pdtable_layout_transform_result

known_asset_type_codes, known_foundation_type_codes, and
known_layout_status_codes (see validate.pdtable.layout's module docstring for
why these are caller-supplied) are read from reference.asset_type,
reference.foundation_type, and reference.layout_status on the live connection
before validation runs -- mirrors cli.pdtable.main's identical pattern. The
connection stays open for the whole run (even in --dry-run mode, never
committed) so validation always sees real, current reference data rather than
a hardcoded snapshot that can silently drift from the seeded tables.

Connection handling is reused as-is from geodb_connect (IAM-authenticated
psycopg connection).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from geodb_connect.config import DbConfig
from geodb_connect.db import connect

from ..load import LoadError, load_pdtable_layout_transform_result
from ..parse.pdtable import PdtableLayoutParseError, parse_pdtable_layout_file
from ..transform.pdtable import transform_pdtable_layout_document
from ..validate.pdtable import validate_pdtable_layout_document
from ._report import print_rejections, print_warning_messages

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geodb-etl-load-layout",
        description=(
            "Parse, validate, and load a pdtable ('StarTable') layout-input .csv "
            "into project.layout / location.asset_location / project.layout_asset."
        ),
    )
    parser.add_argument(
        "csv_file", type=Path, help="Path to the input_layout_{area_code}.csv file."
    )
    parser.add_argument(
        "--role",
        default="superuser",
        choices=["superuser", "dba", "reader"],
        help="Which geodb IAM role/database user to connect as (default: %(default)s).",
    )
    parser.add_argument(
        "--via-tunnel",
        action="store_true",
        help=(
            "Connect through an already-running SSM tunnel (127.0.0.1:$GEODB_LOCAL_PORT) "
            "instead of directly to the RDS endpoint."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse, validate, and transform only -- print what WOULD be loaded, don't write.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    return parser


def _fetch_known_codes(connection: object, table: str, column: str) -> set[str]:
    cursor = connection.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute(f"SELECT {column} FROM {table}")  # noqa: S608
        return {row[0] for row in cursor.fetchall()}
    finally:
        cursor.close()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s"
    )

    try:
        document = parse_pdtable_layout_file(args.csv_file)
    except PdtableLayoutParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if document.parse_warnings:
        print_warning_messages(document.parse_warnings)

    config = DbConfig.from_env(role=args.role, via_tunnel=args.via_tunnel)

    with connect(config) as connection:
        known_asset_type_codes = _fetch_known_codes(
            connection, "reference.asset_type", "asset_type_code"
        )
        known_foundation_type_codes = _fetch_known_codes(
            connection, "reference.foundation_type", "foundation_type_code"
        )
        known_layout_status_codes = _fetch_known_codes(
            connection, "reference.layout_status", "layout_status_code"
        )

        validated, rejections = validate_pdtable_layout_document(
            document,
            known_asset_type_codes=known_asset_type_codes,
            known_foundation_type_codes=known_foundation_type_codes,
            known_layout_status_codes=known_layout_status_codes,
        )
        if rejections:
            print_rejections(rejections)

        transformed = transform_pdtable_layout_document(validated)

        if args.dry_run:
            layout_count = len(transformed.layout_catalogue)
            asset_count = len(transformed.asset_details)
            print(
                f"[dry-run] would load {layout_count} layout_details row(s) and "
                f"{asset_count} layout_configuration row(s); "
                f"{len(rejections)} row(s) rejected and skipped."
            )
            return 0 if not rejections else 1

        try:
            load_result = load_pdtable_layout_transform_result(transformed, connection)
        except LoadError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        layout_count = len(load_result.layout_ids)
        asset_count = len(load_result.asset_location_ids)
        print(
            f"Loaded {layout_count} layout_details row(s) and "
            f"{asset_count} layout_configuration row(s); "
            f"{len(rejections)} row(s) rejected and skipped."
        )
        return 0 if not rejections else 1


if __name__ == "__main__":
    raise SystemExit(main())
