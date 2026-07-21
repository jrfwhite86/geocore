#!/usr/bin/env bash
# geodb/shell/lib/common.sh
#
# Shared functions sourced by every geodb connectivity script. This is the fix for
# docs/technical-debt-assessment.md hotspot #2 (the DB connectivity script cluster) and
# docs/solid-dry-review.md's LSP section: connect-db.sh, get-token.sh, tunnel.sh, and
# tunnel-local-user.sh previously each reimplemented assume-role / bastion-resolution /
# tunnel-waiting independently, with subtly inconsistent contracts (e.g. one script
# destructured 4 fields from `aws sts assume-role`, another only 3, silently dropping
# expiry). There is now exactly one implementation of each operation.
#
# Not meant to be executed directly.

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
	echo "common.sh is a library and must be sourced, not executed directly." >&2
	exit 1
fi

_GEODB_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_GEODB_CONFIG_FILE="${GEODB_CONFIG_FILE:-$_GEODB_LIB_DIR/../../config/environment.env}"
_GEODB_LOCAL_CONFIG_FILE="${GEODB_LOCAL_CONFIG_FILE:-$_GEODB_LIB_DIR/../../config/environment.local.env}"

# load_geodb_env
# Sources config/environment.env (and, if present, the gitignored environment.local.env
# override) with all variables exported, and sets AWS_CA_BUNDLE for Ørsted's CA if not
# already set.
load_geodb_env() {
	if [[ -f "$_GEODB_CONFIG_FILE" ]]; then
		set -a
		# shellcheck source=/dev/null
		#
		# Sourced via `source <(tr -d '\r' < file)` rather than a plain `source file` so a
		# CRLF-terminated config file (e.g. saved/edited with a Windows tool, or checked out
		# with core.autocrlf=true — see .gitattributes) can never break this again. A bare
		# `\r` on a blank/short line otherwise fails as: "$'\r': command not found".
		source <(tr -d '\r' < "$_GEODB_CONFIG_FILE")
		if [[ -f "$_GEODB_LOCAL_CONFIG_FILE" ]]; then
			# shellcheck source=/dev/null
			source <(tr -d '\r' < "$_GEODB_LOCAL_CONFIG_FILE")
		fi
		set +a
	else
		echo "Warning: environment config not found at $_GEODB_CONFIG_FILE" >&2
	fi

	if [[ -z "${AWS_CA_BUNDLE:-}" && -f /etc/ssl/certs/ca-certificates.crt ]]; then
		export AWS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
	fi
}

# require_command <name>
require_command() {
	command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }
}

# resolve_instance_id <instance-id-or-name-tag>
resolve_instance_id() {
	local bastion="$1"
	if [[ "$bastion" =~ ^i-[0-9a-f]+$ ]]; then
		echo "$bastion"
	else
		aws ec2 describe-instances \
			--filters "Name=tag:Name,Values=$bastion" \
			--query "Reservations[0].Instances[0].InstanceId" \
			--output text
	fi
}

# assume_geodb_role <role_arn> <region> [session_name_prefix]
# Always exports all four fields: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
# AWS_SESSION_TOKEN, AWS_SESSION_EXPIRATION — no caller silently loses expiry information.
assume_geodb_role() {
	local role_arn="$1" region="$2" prefix="${3:-geodb}"
	local ak sk st exp
	read -r ak sk st exp <<< "$(
		aws sts assume-role \
			--role-arn "$role_arn" \
			--role-session-name "${prefix}-$(date +%Y%m%d%H%M%S)" \
			--query 'Credentials.[AccessKeyId,SecretAccessKey,SessionToken,Expiration]' \
			--output text
	)"
	export AWS_ACCESS_KEY_ID="$ak" AWS_SECRET_ACCESS_KEY="$sk" AWS_SESSION_TOKEN="$st"
	export AWS_SESSION_EXPIRATION="$exp" AWS_REGION="$region" AWS_DEFAULT_REGION="$region"
}

# generate_geodb_token <hostname> <port> <region> <username>
generate_geodb_token() {
	local hostname="$1" port="$2" region="$3" username="$4"
	aws rds generate-db-auth-token \
		--hostname "$hostname" \
		--port "$port" \
		--region "$region" \
		--username "$username"
}

# wait_for_tunnel <local_port> <tunnel_pid> <log_file> [max_attempts]
wait_for_tunnel() {
	local local_port="$1" tunnel_pid="$2" log_file="$3" max_attempts="${4:-30}"
	echo -n "==> Waiting for tunnel to accept connections"
	for _ in $(seq 1 "$max_attempts"); do
		if (exec 3<>/dev/tcp/127.0.0.1/"$local_port") 2>/dev/null; then
			exec 3<&- 3>&-
			echo " — ready"
			return 0
		fi
		if ! kill -0 "$tunnel_pid" 2>/dev/null; then
			echo
			echo "Tunnel process exited before becoming ready. Log:" >&2
			cat "$log_file" >&2
			return 1
		fi
		echo -n "."
		sleep 1
	done
	echo
	echo "Timed out waiting for tunnel on port $local_port" >&2
	return 1
}

# resolve_role_arn <role: superuser|dba|reader>
resolve_role_arn() {
	case "$1" in
		superuser) echo "${GEODB_SUPERUSER_ROLE_ARN:-}" ;;
		dba)       echo "${GEODB_DBA_ROLE_ARN:-}" ;;
		reader)    echo "${GEODB_READER_ROLE_ARN:-}" ;;
		*) echo "Unknown role: $1 (expected superuser|dba|reader)" >&2; return 1 ;;
	esac
}

# resolve_role_username <role: superuser|dba|reader>
resolve_role_username() {
	case "$1" in
		superuser|dba|reader) echo "$1" ;;
		*) echo "Unknown role: $1 (expected superuser|dba|reader)" >&2; return 1 ;;
	esac
}

