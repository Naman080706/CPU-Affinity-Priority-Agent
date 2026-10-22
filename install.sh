#!/usr/bin/env bash
# Installer for cpu-affinity-agent on Ubuntu Linux.
# Run as root:  sudo ./install.sh
set -euo pipefail

APP_DIR=/opt/cpu-affinity-agent
CFG_DIR=/etc/cpu-affinity-agent
UNIT=/etc/systemd/system/cpu-affinity-agent.service
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root (sudo ./install.sh)" >&2
  exit 1
fi

echo "==> Installing Python dependency (psutil)"
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y python3 python3-psutil
else
  python3 -m pip install -r "$SRC_DIR/requirements.txt"
fi

echo "==> Copying application to $APP_DIR"
mkdir -p "$APP_DIR"
cp -r "$SRC_DIR/cpu_affinity_agent" "$APP_DIR/"

echo "==> Installing config to $CFG_DIR"
mkdir -p "$CFG_DIR"
if [[ ! -f "$CFG_DIR/config.json" ]]; then
  cp "$SRC_DIR/config/agent.json" "$CFG_DIR/config.json"
else
  echo "    (keeping existing $CFG_DIR/config.json)"
fi

echo "==> Installing systemd unit"
cp "$SRC_DIR/systemd/cpu-affinity-agent.service" "$UNIT"

echo "==> Validating config"
python3 -m cpu_affinity_agent.agent --config "$CFG_DIR/config.json" --check \
  && cd "$APP_DIR" || true

echo "==> Enabling + starting service"
systemctl daemon-reload
systemctl enable --now cpu-affinity-agent.service

echo
echo "Done. Useful commands:"
echo "  systemctl status cpu-affinity-agent"
echo "  journalctl -u cpu-affinity-agent -f"
echo "  systemctl reload cpu-affinity-agent    # re-read config after editing"
