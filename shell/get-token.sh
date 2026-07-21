#!/usr/bin/env bash
# Generate a fresh 15-min RDS IAM auth token for pgAdmin (or any GUI client).
# Copies the token to the Windows clipboard when run from WSL.
#
# Usage: ./get-token.sh [role]
#   role: superuser (default) | dba | reader
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

ROLE="${1:-superuser}"

load_geodb_env

ROLE_ARN="$(resolve_role_arn "$ROLE")"
PGUSER="$(resolve_role_username "$ROLE")"

if [[ -z "$ROLE_ARN" ]]; then
	echo "No role ARN configured for role '$ROLE' in geodb/config/environment.env" >&2
	exit 1
fi

assume_geodb_role "$ROLE_ARN" "$AWS_REGION" "pg-iam-token"

TOKEN="$(generate_geodb_token "$GEODB_RDS_HOST" "$GEODB_RDS_PORT" "$AWS_REGION" "$PGUSER")"

if command -v clip.exe >/dev/null 2>&1; then
	printf '%s' "$TOKEN" | clip.exe
	CLIP_NOTE="(copied to Windows clipboard)"
else
	CLIP_NOTE="(clipboard unavailable — paste from below)"
fi

cat <<EOF

Token generated $CLIP_NOTE — valid for 15 minutes.

pgAdmin connection details:
  Host        : 127.0.0.1
  Port        : $GEODB_LOCAL_PORT
  Database    : $GEODB_DB_NAME
  Username    : $PGUSER
  Password    : <paste from clipboard>
  SSL mode    : require

EOF

if ! command -v clip.exe >/dev/null 2>&1; then
	echo "$TOKEN"
fi

