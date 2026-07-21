"""Configuration loading for geodb_connect.

Reads shared environment facts from geodb/config/environment.env — the single source
of truth also consumed by the Bash scripts in geodb/shell/ (docs/architecture-review.md
duplication matrix fix) — with real process environment variables taking precedence,
and an explicit `role` argument selecting which database user/IAM role to use.

Fixes docs/solid-dry-review.md's SRP/DIP findings: the previous scripts/pg_iam_connect.py
hardcoded RDS_HOST/RDS_USER/AWS_REGION etc. as module-level constants, so get_auth_token()
and connect() depended directly on hardcoded literals instead of an injected abstraction.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# geodb/python/src/geodb_connect/config.py -> parents[3] == geodb/
_REPO_ENV_FILE = Path(__file__).resolve().parents[3] / "config" / "environment.env"

_ROLE_USERNAMES = {"superuser", "dba", "reader"}
_ROLE_ARN_ENV_KEYS = {
    "superuser": "GEODB_SUPERUSER_ROLE_ARN",
    "dba": "GEODB_DBA_ROLE_ARN",
    "reader": "GEODB_READER_ROLE_ARN",
}


def _parse_env_file(path: Path) -> dict[str, str]:
    """Minimal dependency-free KEY=VALUE parser.

    Deliberately avoids adding python-dotenv as a new dependency for what is still a
    PoC-scoped tool — this repo's shared environment.env format is simple enough
    (no quoting/interpolation) that a few lines here are sufficient and keep
    requirements minimal.
    """
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def _load_merged_env() -> dict[str, str]:
    merged = _parse_env_file(_REPO_ENV_FILE)
    merged.update(os.environ)  # real environment variables always win
    return merged


@dataclass(frozen=True)
class DbConfig:
    """Immutable connection settings for one geodb role/session.

    host/port are always the REAL RDS endpoint -- this is what an IAM auth
    token must be signed for (see auth.get_auth_token), regardless of how the
    actual TCP socket reaches the database. connect_host/connect_port are
    where psycopg actually opens that socket, and differ from host/port
    whenever an SSM tunnel is in play: geodb/shell/connect-db.sh's own
    pattern is "generate the token for $GEODB_RDS_HOST, but psql connects to
    127.0.0.1:$GEODB_LOCAL_PORT" -- see tunnel.sh's own printed reminder,
    "Tokens must still be generated with --hostname=... --port=...". Before
    this field existed, running this package from a laptop without a direct
    network path to RDS (the normal case -- see geodb/QUICK_START.md) had no
    way to express "sign for the real host, but dial the tunnel" and failed
    with a connection timeout.
    """

    host: str
    port: int
    dbname: str
    user: str
    region: str
    role_arn: str | None
    connect_host: str
    connect_port: int

    @classmethod
    def from_env(cls, role: str = "superuser", *, via_tunnel: bool = False) -> DbConfig:
        """Build a DbConfig from environment.env + real env vars.

        Args:
            role: Which geodb IAM role/database user to connect as.
            via_tunnel: If True, the actual psycopg socket targets
                127.0.0.1:$GEODB_LOCAL_PORT (an SSM tunnel opened separately,
                e.g. `bash geodb/shell/tunnel.sh`) while the IAM auth token
                is still signed for the real RDS host/port. If False
                (default), the socket connects directly to the real RDS
                host/port -- correct only when running somewhere with a
                direct network path to RDS (e.g. inside the VPC), not from
                an ordinary laptop.
        """

        if role not in _ROLE_USERNAMES:
            raise ValueError(f"Unknown role '{role}', expected one of {sorted(_ROLE_USERNAMES)}")

        env = _load_merged_env()
        role_arn_key = _ROLE_ARN_ENV_KEYS[role]

        host = env.get("GEODB_RDS_HOST", "geodb-rds-pg.cnckeywiw239.eu-north-1.rds.amazonaws.com")
        port = int(env.get("GEODB_RDS_PORT", "5432"))

        if via_tunnel:
            connect_host = "127.0.0.1"
            connect_port = int(env.get("GEODB_LOCAL_PORT", "55432"))
        else:
            connect_host = host
            connect_port = port

        return cls(
            host=host,
            port=port,
            dbname=env.get("GEODB_DB_NAME", "geodb"),
            user=env.get("GEODB_USER_OVERRIDE", role),
            region=env.get("AWS_REGION", "eu-north-1"),
            role_arn=env.get(role_arn_key) or None,
            connect_host=connect_host,
            connect_port=connect_port,
        )

