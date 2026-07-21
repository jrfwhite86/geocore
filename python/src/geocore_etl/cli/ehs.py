"""Command-line entry point for loading an EHS workbook into geoCore.

Installed as the `geodb-etl-load-ehs` console script (see pyproject.toml), or
runnable via `python -m geodb_etl.cli.ehs`. One of two format-specific CLI
handlers under `geodb_etl.cli` (see `geodb_etl.cli.pdtable` for the pdtable
project-input equivalent) -- moved here from the top-level `geodb_etl/cli.py`
per `tasks/plan/codebase-structure-cleanup.md` Task 8's CLI-unification step.
Wires the four pipeline stages together end to end:

    parse.xlsx.parse_ehs_file
      -> validate.xlsx.validate_ehs_document
      -> transform.xlsx.transform_ehs_document
      -> load.load_ehs_transform_result

known_hole_type_codes / known_survey_phase_codes / known_hole_status_codes /
known_termination_reason_codes (see validate.xlsx's module docstring for why
these are caller-supplied rather than hardcoded) are read from
reference.hole_type / reference.survey_phase / reference.hole_status /
reference.termination_reason on the live connection before validation runs --
this is the one place in the whole pipeline that looks up reference data
purely for validation purposes, not for loading.

Connection handling is reused as-is from geodb_connect (IAM-authenticated
psycopg connection) -- this module adds no new connection logic of its own.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from geodb_connect.config import DbConfig
from geodb_connect.db import connect

from ..load import LoadError, load_ehs_transform_result
from ..parse.xlsx import EhsParseError, parse_ehs_file
from ..transform.xlsx import transform_ehs_document
from ..validate.xlsx import validate_ehs_document
from ._report import print_rejections, print_warning_messages

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geodb-etl-load-ehs",
        description=(
            "Parse, validate, and load an Exploratory Hole Schedule (EHS) .xlsx "
            "workbook into geotech.site_investigation / geotech.exploratory_hole."
        ),
    )
    parser.add_argument("workbook", type=Path, help="Path to the EHS .xlsx workbook.")
    parser.add_argument(
        "--project-code",
        required=True,
        help=(
            "project.project.project_code this campaign belongs to (never read from "
            "the workbook's own header -- see mappings.xlsx.ehs.PROJECT_FIELD_MAPPINGS)."
        ),
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
            "Connect through an already-running SSM tunnel (127.0.0.1:$GEODB_LOCAL_PORT, "
            "e.g. `bash geodb/shell/tunnel.sh`) instead of directly to the RDS endpoint -- "
            "required when running from a laptop without a direct network path to RDS "
            "(see geodb/QUICK_START.md). The IAM auth token is still signed for the real "
            "RDS host/port either way."
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
        cursor.execute(f"SELECT {column} FROM {table}")  # noqa: S608 -- table/column are literals below, never user input
        return {row[0] for row in cursor.fetchall()}
    finally:
        cursor.close()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s"
    )

    try:
        document = parse_ehs_file(args.workbook)
    except EhsParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    config = DbConfig.from_env(role=args.role, via_tunnel=args.via_tunnel)
    with connect(config) as connection:
        known_hole_type_codes = _fetch_known_codes(
            connection, "reference.hole_type", "hole_type_code"
        )
        known_survey_phase_codes = _fetch_known_codes(
            connection, "reference.survey_phase", "survey_phase_code"
        )
        known_hole_status_codes = _fetch_known_codes(
            connection, "reference.hole_status", "hole_status_code"
        )
        known_termination_reason_codes = _fetch_known_codes(
            connection, "reference.termination_reason", "termination_reason_code"
        )

        validated, rejections = validate_ehs_document(
            document,
            known_hole_type_codes=known_hole_type_codes,
            known_survey_phase_codes=known_survey_phase_codes,
            known_hole_status_codes=known_hole_status_codes,
            known_termination_reason_codes=known_termination_reason_codes,
        )
        if rejections:
            print_rejections(rejections)
        if validated is None:
            print("error: EHS header failed validation, nothing loaded.", file=sys.stderr)
            return 1

        transformed = transform_ehs_document(validated, project_code=args.project_code)

        if args.dry_run:
            si_name = transformed.site_investigation.si_name
            hole_count = len(transformed.exploratory_holes)
            print(
                f"[dry-run] would load site_investigation '{si_name}' and "
                f"{hole_count} exploratory_hole row(s); "
                f"{len(rejections)} row(s) rejected and skipped.",
            )
            return 0 if not rejections else 1

        try:
            result = load_ehs_transform_result(transformed, connection)
        except LoadError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    if result.warnings:
        print_warning_messages(result.warnings)

    print(
        f"Loaded site_investigation_id={result.site_investigation_id}, "
        f"{len(result.exploratory_hole_ids)} exploratory_hole row(s); "
        f"{len(rejections)} row(s) rejected and skipped."
    )
    return 0 if not rejections else 1


if __name__ == "__main__":
    raise SystemExit(main())






