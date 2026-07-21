#!/usr/bin/env bash
# Open a standing SSM port-forwarding tunnel to the geodb RDS instance, for use with
# pgAdmin or any other GUI client (pair with ./get-token.sh to obtain a token).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib/common.sh
source "$SCRIPT_DIR/lib/common.sh"

load_geodb_env

read -rp "EC2 instance ID or Name tag [$GEODB_BASTION_ID]: " BASTION_INPUT
read -rp "PostgreSQL hostname [$GEODB_RDS_HOST]: " RDSHOST_INPUT

BASTION="${BASTION_INPUT:-$GEODB_BASTION_ID}"
RDSHOST="${RDSHOST_INPUT:-$GEODB_RDS_HOST}"
INSTANCE_ID="$(resolve_instance_id "$BASTION")"

echo "Starting tunnel localhost:$GEODB_LOCAL_PORT -> $RDSHOST:$GEODB_RDS_PORT via $INSTANCE_ID"
echo "Clients should connect to 127.0.0.1:$GEODB_LOCAL_PORT with sslmode=require."
echo "Tokens must still be generated with --hostname=$RDSHOST --port=$GEODB_RDS_PORT."

exec aws ssm start-session \
	--target "$INSTANCE_ID" \
	--document-name AWS-StartPortForwardingSessionToRemoteHost \
	--parameters "host=$RDSHOST,portNumber=$GEODB_RDS_PORT,localPortNumber=$GEODB_LOCAL_PORT"
