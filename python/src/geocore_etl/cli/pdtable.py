"""Command-line entry point for loading a pdtable project-input CSV into geoCore.

Installed as the `geodb-etl-load-project` console script (see pyproject.toml), or
runnable via `python -m geodb_etl.cli.pdtable`. One of two format-specific CLI
handlers under `geodb_etl.cli` (see `geodb_etl.cli.ehs` for the EHS .xlsx
equivalent) -- moved here from the top-level `geodb_etl/cli_pdtable.py` per
`tasks/plan/codebase-structure-cleanup.md` Task 8's CLI-unification step.
Implemented in Phase 6b (see tasks/plan/phase-6b-pdtable-cli-completion.md) --
Phase 6 shipped `mappings.pdtable.project`/`load.pdtable.project` only; this
module wires the four pipeline stages together end to end:

    parse.pdtable.parse_pdtable_project_file
      -> validate.pdtable.validate_pdtable_project_document
      -> transform.pdtable.transform_pdtable_project_document
      -> load.load_pdtable_project_transform_result

known_region_codes / known_sea_area_codes / known_country_codes /
known_foundation_type_codes / known_project_status_codes (see
validate.pdtable.project's module docstring for why these are caller-
supplied rather than hardcoded) are read from reference.region /
reference.sea_area / reference.country / reference.foundation_type /
reference.project_status on the live connection before validation runs --
mirrors cli.ehs.main's identical pattern for known_hole_type_codes /
known_survey_phase_codes.

UNLIKE cli.ehs.main, there is no `--project-code` argument -- this file
supplies its own project codes via its own `project` block (see
mappings.pdtable.project.PROJECT_AUTHORITY).

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

from ..load import LoadError, load_pdtable_project_transform_result
from ..parse.pdtable import PdtableParseError, parse_pdtable_project_file
from ..transform.pdtable import transform_pdtable_project_document
from ..validate.pdtable import validate_pdtable_project_document
from ._report import print_rejections, print_validation_warnings

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geodb-etl-load-project",
        description=(
            "Parse, validate, and load a pdtable ('StarTable') project-input .csv "
            "into location.development_area / project.project / "
            "reference.coordinate_system / location.boundary."
        ),
    )
    parser.add_argument(
        "csv_file", type=Path, help="Path to the input_project_{area_code}.csv file."
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
        document = parse_pdtable_project_file(args.csv_file)
    except PdtableParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    config = DbConfig.from_env(role=args.role, via_tunnel=args.via_tunnel)
    with connect(config) as connection:
        known_region_codes = _fetch_known_codes(connection, "reference.region", "region_code")
        known_sea_area_codes = _fetch_known_codes(
            connection, "reference.sea_area", "sea_area_code"
        )
        known_country_codes = _fetch_known_codes(connection, "reference.country", "country_code")
        known_foundation_type_codes = _fetch_known_codes(
            connection, "reference.foundation_type", "foundation_type_code"
        )
        known_project_status_codes = _fetch_known_codes(
            connection, "reference.project_status", "project_status_code"
        )

        validated, rejections = validate_pdtable_project_document(
            document,
            known_region_codes=known_region_codes,
            known_sea_area_codes=known_sea_area_codes,
            known_country_codes=known_country_codes,
            known_foundation_type_codes=known_foundation_type_codes,
            known_project_status_codes=known_project_status_codes,
        )
        if rejections:
            print_rejections(rejections)
        if validated is None:
            print(
                "error: development_area block failed validation, nothing loaded.",
                file=sys.stderr,
            )
            return 1
        if validated.warnings:
            print_validation_warnings(validated.warnings)

        transformed = transform_pdtable_project_document(validated)

        if args.dry_run:
            project_count = len(transformed.projects)
            boundary_count = len(transformed.boundaries)
            area_code = transformed.development_area.area_code
            crs_count = len(transformed.coordinate_systems)
            print(
                f"[dry-run] would load development_area {area_code!r}, "
                f"{project_count} project row(s), {crs_count} coordinate_reference_system "
                f"block(s), and {boundary_count} boundary/boundary_vertex row(s); "
                f"{len(rejections)} row(s) rejected and skipped.",
            )
            return 0 if not rejections else 1

        try:
            result = load_pdtable_project_transform_result(transformed, connection)
        except LoadError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    print(
        f"Loaded area_id={result.area_id}, {len(result.project_ids)} project.project row(s), "
        f"{len(result.boundary_ids)} location.boundary row(s); "
        f"{len(rejections)} row(s) rejected and skipped."
    )
    return 0 if not rejections else 1


if __name__ == "__main__":
    raise SystemExit(main())



