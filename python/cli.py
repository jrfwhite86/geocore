"""Command-line entry point: `geodb-connect` (installed console script) or
`python -m geodb_connect.cli`.
"""

from __future__ import annotations

import argparse
import logging

from .config import DbConfig
from .db import connect


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="geodb-connect",
        description="Connect to the geodb RDS PostgreSQL instance using IAM authentication.",
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
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(message)s"
    )

    config = DbConfig.from_env(role=args.role, via_tunnel=args.via_tunnel)
    with connect(config) as conn, conn.cursor() as cur:
        cur.execute("SELECT current_user, now();")
        print(cur.fetchone())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

