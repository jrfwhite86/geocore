"""Connection helpers for the geodb RDS PostgreSQL instance."""

from __future__ import annotations

import logging

import psycopg

from .auth import get_auth_token
from .config import DbConfig

logger = logging.getLogger(__name__)


def connect(config: DbConfig) -> psycopg.Connection:
    """Open a psycopg connection using a freshly generated IAM auth token.

    The auth token is always signed for config.host/config.port (the real
    RDS endpoint) -- IAM auth token validation is host/port-specific, per
    connect-db.sh's own comment ("Generating IAM auth token ... for
    $PGUSER@$GEODB_RDS_HOST"). The TCP socket itself, however, targets
    config.connect_host/config.connect_port, which is 127.0.0.1:<tunnel port>
    when DbConfig was built with via_tunnel=True -- see DbConfig's docstring.
    """
    logger.debug(
        "Connecting to %s:%s/%s as %s (socket: %s:%s)",
        config.host,
        config.port,
        config.dbname,
        config.user,
        config.connect_host,
        config.connect_port,
    )
    token = get_auth_token(config)
    return psycopg.connect(
        host=config.connect_host,
        port=config.connect_port,
        dbname=config.dbname,
        user=config.user,
        password=token,
        sslmode="require",
    )

