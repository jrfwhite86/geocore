#!/usr/bin/env bash
# Universal WSL Ubuntu Dev Setup Script
# Installs AWS CLI v2, Podman, and all dependencies needed for geodb connectivity.
#
# This is geodb-specific (installs psql, session-manager-plugin — tools needed
# specifically to reach the geodb RDS instance), unlike bootstrap/ which is generic
# WSL2 workstation setup. See docs/architecture-review.md for the rationale on keeping
# these two bounded contexts separate.

set -e


# Ensure running as root
if [ "$(id -u)" -ne 0 ]; then
  echo "Please run this script with: sudo bash $0"
  exit 1
fi

# --- Add OrstedRootCA.pem to system trust store ---
CA_SRC="$(dirname "$0")/OrstedRootCA.pem"
CA_DST="/usr/local/share/ca-certificates/OrstedRootCA.crt"
if [ -f "$CA_SRC" ]; then
  cp "$CA_SRC" "$CA_DST"
  update-ca-certificates
  echo "[INFO] OrstedRootCA.pem added to system trust store."
else
  echo "[WARN] OrstedRootCA.pem not found next to this script. Skipping CA install."
fi


# Update and upgrade
apt-get update
apt-get upgrade -y

# Install dependencies
apt-get install -y curl unzip jq lsof podman postgresql-client

# Install AWS CLI v2
if ! command -v aws &>/dev/null; then
  curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
  unzip awscliv2.zip
  ./aws/install
  rm -rf aws awscliv2.zip
fi

# Install session-manager-plugin
if ! command -v session-manager-plugin &>/dev/null; then
  curl "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb" -o "session-manager-plugin.deb"
  dpkg -i session-manager-plugin.deb
  rm session-manager-plugin.deb
fi

echo "\n[INFO] All tools installed!\n"
echo "[INFO] Run 'aws --version', 'podman --version', and 'psql --version' to verify."

