#!/usr/bin/env bash
# Open a standing SSM port-forwarding tunnel for a password-authenticated LOCAL database
# user (NOT an IAM role — a distinct auth model from tunnel.sh/connect-db.sh/get-token.sh).
#
# Fix (docs/technical-debt-assessment.md Phase 0 / docs/solid-dry-review.md LSP section):
# this script previously hardcoded and echoed a plaintext password ("pass1234") to the
# terminal. That is removed — the password is never stored or displayed by this script;
# psql/pgAdmin will prompt for it interactively.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

load_geodb_env

read -rp "EC2 instance ID or Name tag [$GEODB_BASTION_ID]: " BASTION_INPUT
read -rp "PostgreSQL hostname [$GEODB_RDS_HOST]: " RDSHOST_INPUT
read -rp "Local database username [useringeodb]: " LOCAL_DB_USER_INPUT

BASTION="${BASTION_INPUT:-$GEODB_BASTION_ID}"
RDSHOST="${RDSHOST_INPUT:-$GEODB_RDS_HOST}"
LOCAL_DB_USER="${LOCAL_DB_USER_INPUT:-useringeodb}"
INSTANCE_ID="$(resolve_instance_id "$BASTION")"

echo "Starting tunnel localhost:$GEODB_LOCAL_PORT -> $RDSHOST:$GEODB_RDS_PORT via $INSTANCE_ID"
echo ""
echo "This tunnel is for a password-authenticated local database user (not an IAM role)."
echo "You will be prompted for that user's password on demand by psql/pgAdmin — it is"
echo "never stored, generated, or printed by this script."
echo ""
echo "psql example (will prompt for password):"
echo "  psql -h 127.0.0.1 -p $GEODB_LOCAL_PORT -U $LOCAL_DB_USER -d $GEODB_DB_NAME"
echo ""
echo "pgAdmin: Host=127.0.0.1, Port=$GEODB_LOCAL_PORT, Database=$GEODB_DB_NAME, Username=$LOCAL_DB_USER, SSL mode=require"
echo ""

exec aws ssm start-session \
	--target "$INSTANCE_ID" \
	--document-name AWS-StartPortForwardingSessionToRemoteHost \
	--parameters "host=$RDSHOST,portNumber=$GEODB_RDS_PORT,localPortNumber=$GEODB_LOCAL_PORT"

