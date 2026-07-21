"""Command-line entry point for loading a pdtable exploratory-hole-input CSV
into geoCore.

Installed as the ``geodb-etl-load-exploratory-hole`` console script (see
pyproject.toml). Wires the four pipeline stages together end to end:

    parse.pdtable.parse_pdtable_exploratory_hole_file
      -> validate.pdtable.validate_pdtable_exploratory_hole_document
      -> transform.pdtable.transform_pdtable_exploratory_hole_document
      -> load.load_pdtable_exploratory_hole_transform_result

``known_survey_phase_codes``, ``known_hole_type_codes``,
``known_hole_status_codes``/``known_terminal_hole_status_codes``, and
``known_termination_reason_codes`` (see the validate module's docstring for
why these are caller-supplied) are read from ``reference.survey_phase`` /
``reference.hole_type`` / ``reference.hole_status`` / ``reference.hole_status
WHERE is_terminal`` / ``reference.termination_reason`` on the live connection
before validation runs -- mirrors ``cli.ehs``'s identical pattern.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from geodb_connect.config import DbConfig
from geodb_connect.db import connect

from ..load import LoadError, load_pdtable_exploratory_hole_transform_result
from ..parse.pdtable import (
    PdtableExploratoryHoleParseError,
    parse_pdtable_exploratory_hole_file,
)
from ..transform.pdtable import transform_pdtable_exploratory_hole_document
from ..validate.pdtable import validate_pdtable_exploratory_hole_document
from ._report import print_rejections, print_warning_messages

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geodb-etl-load-exploratory-hole",
        description=(
            "Parse, validate, and load a pdtable ('StarTable') exploratory-hole-input "
            ".csv (input_exploratory_holes_{area_code}.csv) into "
            "geotech.cluster_location / geotech.exploratory_hole."
        ),
    )
    parser.add_argument(
        "csv_file",
        type=Path,
        help="Path to the input_exploratory_holes_{area_code}.csv file.",
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


def _fetch_terminal_hole_status_codes(connection: object) -> set[str]:
    """See mappings.pdtable.exploratory_hole.HOLE_STATUS_MUST_BE_TERMINAL --
    every hole_status in this file must be one of these, not merely a known
    reference.hole_status code."""

    cursor = connection.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute(
            "SELECT hole_status_code FROM reference.hole_status WHERE is_terminal"
        )
        return {row[0] for row in cursor.fetchall()}
    finally:
        cursor.close()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s"
    )

    try:
        document = parse_pdtable_exploratory_hole_file(args.csv_file)
    except PdtableExploratoryHoleParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if document.parse_warnings:
        print_warning_messages(document.parse_warnings)

    config = DbConfig.from_env(role=args.role, via_tunnel=args.via_tunnel)

    with connect(config) as connection:
        known_survey_phase_codes = _fetch_known_codes(
            connection, "reference.survey_phase", "survey_phase_code"
        )
        known_hole_type_codes = _fetch_known_codes(
            connection, "reference.hole_type", "hole_type_code"
        )
        known_hole_status_codes = _fetch_known_codes(
            connection, "reference.hole_status", "hole_status_code"
        )
        known_terminal_hole_status_codes = _fetch_terminal_hole_status_codes(connection)
        known_termination_reason_codes = _fetch_known_codes(
            connection, "reference.termination_reason", "termination_reason_code"
        )

        validated, rejections = validate_pdtable_exploratory_hole_document(
            document,
            known_survey_phase_codes=known_survey_phase_codes,
            known_hole_type_codes=known_hole_type_codes,
            known_hole_status_codes=known_hole_status_codes,
            known_terminal_hole_status_codes=known_terminal_hole_status_codes,
            known_termination_reason_codes=known_termination_reason_codes,
        )
        if rejections:
            print_rejections(rejections)

        transformed = transform_pdtable_exploratory_hole_document(validated)

        if args.dry_run:
            cluster_count = len(transformed.cluster_details)
            hole_count = len(transformed.exploratory_holes)
            print(
                f"[dry-run] would load {cluster_count} cluster_details row(s) and "
                f"{hole_count} exploratory_hole_details row(s); "
                f"{len(rejections)} row(s) rejected and skipped."
            )
            return 0 if not rejections else 1

        try:
            load_result = load_pdtable_exploratory_hole_transform_result(
                transformed, connection
            )
        except LoadError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        if load_result.warnings:
            print_warning_messages(load_result.warnings)

        cluster_count = len(load_result.cluster_location_ids)
        hole_count = len(load_result.exploratory_hole_ids)
        print(
            f"Loaded {cluster_count} cluster_details row(s) and "
            f"{hole_count} exploratory_hole_details row(s); "
            f"{len(rejections)} row(s) rejected and skipped."
        )
        return 0 if not rejections else 1


if __name__ == "__main__":
    raise SystemExit(main())
