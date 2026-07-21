"""IAM auth token generation for RDS PostgreSQL."""

from __future__ import annotations

import time

import boto3

from .config import DbConfig


class AuthConfigError(Exception):
    """Raised when a role has no IAM role ARN configured to assume.

    Mirrors geodb/shell/lib/common.sh's resolve_role_arn, which exits with
    "No role ARN configured for role ..." rather than proceeding (see
    connect-db.sh) -- surfacing this clearly here, rather than generating a
    token anyway, avoids an opaque `PAM authentication failed for user "X"`
    error later from Postgres once such a token is rejected by RDS.
    """


def get_auth_token(config: DbConfig) -> str:
    """Generate a short-lived (~15 min) IAM auth token for RDS PostgreSQL.

    Mirrors geodb/shell/lib/common.sh's assume_geodb_role + generate_geodb_token
    pair. The ambient AWS SSO session's own permission set is NOT what RDS's
    rds-db:connect policy grants access to (see
    docs/infrastructure-reference.md's "Superuser role IAM policy" — the
    Resource ARN there is scoped to dbuser geodbconnect, reachable only via
    config.role_arn, e.g. geodb-rds-pg-superuser-role, not the caller's own
    WorkloadPowerUserAccess SSO permission set) -- the token must be signed
    using the TEMPORARY credentials obtained by assuming config.role_arn
    first, never the ambient/default credentials directly.

    Raises:
        AuthConfigError: config.role_arn is None (e.g. the dba/reader roles,
            whose ARNs are still blank placeholders in
            geodb/config/environment.env -- see docs/architecture-review.md).
    """
    if not config.role_arn:
        raise AuthConfigError(
            f"No IAM role ARN is configured for role {config.user!r} in "
            "geodb/config/environment.env (see docs/architecture-review.md) -- "
            "cannot generate an RDS IAM auth token without first assuming a role."
        )

    sts = boto3.client("sts", region_name=config.region)
    assumed = sts.assume_role(
        RoleArn=config.role_arn,
        RoleSessionName=f"pg-iam-{int(time.time())}",
    )
    credentials = assumed["Credentials"]
    session = boto3.Session(
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
        region_name=config.region,
    )
    client = session.client("rds")
    return client.generate_db_auth_token(
        DBHostname=config.host,
        Port=config.port,
        DBUsername=config.user,
        Region=config.region,
    )

