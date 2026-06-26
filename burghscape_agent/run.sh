#!/usr/bin/env bash
set -euo pipefail

echo "Burghscape Agent starting..."

# HA add-on config is mounted at /data/options.json
CONFIG_PATH=/data/options.json

if [ -f "$CONFIG_PATH" ]; then
    echo "Loading config from $CONFIG_PATH..."
    export PLATFORM_URL=$(jq -r '.platform_url // ""' "$CONFIG_PATH")
    export SUBSCRIPTION_TOKEN=*** -r '.subscription_token // ""' "$CONFIG_PATH")
    export INSTANCE_NAME=$(jq -r '.instance_name // "My Home Assistant"' "$CONFIG_PATH")
    export HEARTBEAT_INTERVAL=$(jq -r '.heartbeat_interval // 300' "$CONFIG_PATH")
    export MONITOR_ENTITIES=$(jq -r '.monitor_entities // true' "$CONFIG_PATH")
    export MONITOR_DISK=$(jq -r '.monitor_disk // true' "$CONFIG_PATH")
    export MONITOR_AUTOMATIONS=$(jq -r '.monitor_automations // true' "$CONFIG_PATH")
    export MONITOR_UPDATES=$(jq -r '.monitor_updates // true' "$CONFIG_PATH")
    export MONITOR_BACKUPS=$(jq -r '.monitor_backups // false' "$CONFIG_PATH")
    export MONITOR_FRIGATE=$(jq -r '.monitor_frigate // false' "$CONFIG_PATH")
    export REPORT_DAYS=$(jq -r '.report_days // 30' "$CONFIG_PATH")
else
    echo "WARNING: No config file at $CONFIG_PATH, using env vars"
fi

# Validate required config
if [ -z "$PLATFORM_URL" ]; then
    echo "ERROR: PLATFORM_URL not set"
    exit 1
fi

if [ -z "$SUBSCRIPTION_TOKEN" ]; then
    echo "ERROR: SUBSCRIPTION_TOKEN not set"
    exit 1
fi

# Get HA token from supervisor
if [ -f /run/s6/container_environment/HA_TOKEN ]; then
    export HA_TOKEN=*** /run/s6/container_environment/HA_TOKEN)
fi

# Internal HA URL
export HA_URL="${HA_URL:-http://localhost:8123}"

echo "Platform: $PLATFORM_URL"
echo "Instance: ${INSTANCE_NAME:-My Home Assistant}"
echo "Heartbeat: every ${HEARTBEAT_INTERVAL:-300}s"

# Verify cloudflared
if command -v cloudflared &> /dev/null; then
    echo "cloudflared: $(cloudflared --version)"
else
    echo "ERROR: cloudflared not found!"
    exit 1
fi

if [ -z "${HA_TOKEN:-}" ]; then
    echo "WARNING: No HA token found. Set in add-on config."
fi

cd /app
exec python3 -m app.main
