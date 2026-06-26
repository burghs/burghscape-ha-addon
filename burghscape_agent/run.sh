#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH=/config/options.json

echo "Burghscape Agent starting..."

# Use jq to parse JSON config
export PLATFORM_URL=$(jq -r '.platform_url // ""' "$CONFIG_PATH")
export SUBSCRIPTION_TOKEN=$(jq -r '.subscription_token // ""' "$CONFIG_PATH")
export INSTANCE_NAME=$(jq -r '.instance_name // "My Home Assistant"' "$CONFIG_PATH")
export HEARTBEAT_INTERVAL=$(jq -r '.heartbeat_interval // 300' "$CONFIG_PATH")
export MONITOR_ENTITIES=$(jq -r '.monitor_entities // true' "$CONFIG_PATH")
export MONITOR_DISK=$(jq -r '.monitor_disk // true' "$CONFIG_PATH")
export MONITOR_AUTOMATIONS=$(jq -r '.monitor_automations // true' "$CONFIG_PATH")
export MONITOR_UPDATES=$(jq -r '.monitor_updates // true' "$CONFIG_PATH")
export MONITOR_BACKUPS=$(jq -r '.monitor_backups // false' "$CONFIG_PATH")
export MONITOR_FRIGATE=$(jq -r '.monitor_frigate // false' "$CONFIG_PATH")
export REPORT_DAYS=$(jq -r '.report_days // 30' "$CONFIG_PATH")

# Get HA token from supervisor
export HA_TOKEN=$(cat /run/s6/container_environment/HA_TOKEN 2>/dev/null || echo "")

# Internal HA URL
export HA_URL="http://localhost:8123"

echo "Platform: $PLATFORM_URL"
echo "Instance: $INSTANCE_NAME"
echo "Heartbeat: every ${HEARTBEAT_INTERVAL}s"

if command -v cloudflared &> /dev/null; then
    echo "cloudflared: $(cloudflared --version)"
else
    echo "ERROR: cloudflared not found!"
    exit 1
fi

if [ -z "$HA_TOKEN" ]; then
    echo "WARNING: No HA token found."
fi

exec python3 -m app.main
