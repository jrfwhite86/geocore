#!/usr/bin/env bash
# Connect to geodb via psql, using an SSM tunnel through the bastion + an IAM auth token.
#
# Usage: ./connect-db.sh [role]
#   role: superuser (default) | dba | reader
#
# Fix (geodb/QUICK_START.md previously said "To switch user, edit PGUSER and ROLE_ARN at
# the top of connect-db.sh" — a manual-file-edit workflow). Now: ./connect-db.sh dba
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

ROLE="${1:-superuser}"

load_geodb_env
require_command aws
require_command psql
require_command session-manager-plugin

ROLE_ARN="$(resolve_role_arn "$ROLE")"
PGUSER="$(resolve_role_username "$ROLE")"

if [[ -z "$ROLE_ARN" ]]; then
	echo "No role ARN configured for role '$ROLE' in geodb/config/environment.env" >&2
	exit 1
fi

echo "==> Assuming role $ROLE_ARN"
assume_geodb_role "$ROLE_ARN" "$AWS_REGION" "pg-iam"
echo "    role session valid until $AWS_SESSION_EXPIRATION"

TUNNEL_PID=""
cleanup() {
	set +e
	echo
	echo "==> Cleaning up"
	if [[ -n "$TUNNEL_PID" ]] && kill -0 "$TUNNEL_PID" 2>/dev/null; then
		kill "$TUNNEL_PID" 2>/dev/null
		wait "$TUNNEL_PID" 2>/dev/null
	fi
}
trap cleanup EXIT INT TERM

TUNNEL_LOG="$(mktemp -t ssm-tunnel.XXXXXX.log)"
echo "==> Starting SSM tunnel localhost:$GEODB_LOCAL_PORT -> $GEODB_RDS_HOST:$GEODB_RDS_PORT via $GEODB_BASTION_ID"
echo "    tunnel log: $TUNNEL_LOG"
aws ssm start-session \
	--target "$GEODB_BASTION_ID" \
	--document-name AWS-StartPortForwardingSessionToRemoteHost \
	--parameters "host=$GEODB_RDS_HOST,portNumber=$GEODB_RDS_PORT,localPortNumber=$GEODB_LOCAL_PORT" \
	>"$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!

wait_for_tunnel "$GEODB_LOCAL_PORT" "$TUNNEL_PID" "$TUNNEL_LOG"

echo "==> Generating IAM auth token (valid 15 min) for $PGUSER@$GEODB_RDS_HOST"
export PGPASSWORD
PGPASSWORD="$(generate_geodb_token "$GEODB_RDS_HOST" "$GEODB_RDS_PORT" "$AWS_REGION" "$PGUSER")"

echo "==> Connecting via 127.0.0.1:$GEODB_LOCAL_PORT (no /etc/hosts edits required)"
psql "host=127.0.0.1 port=$GEODB_LOCAL_PORT dbname=$GEODB_DB_NAME user=$PGUSER sslmode=require"

