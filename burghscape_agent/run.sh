#!/usr/bin/env bash
set -euo pipefail

echo "Burghscape Agent starting..."

CONFIG_PATH=/data/options.json

if [ -f "$CONFIG_PATH" ]; then
    echo "Loading config from $CONFIG_PATH"
    export PLATFORM_URL=$(jq -r '.platform_url // ""' "$CONFIG_PATH")
    export SUBSCRIPTION_TOKEN=*** -r '.subscription_token // ""' "$CONFIG_PATH")
    export INSTANCE_NAME=$(jq -r '.instance_name // "My Home Assistant"' "$CONFIG_PATH")
    export HEARTBEAT_INTERVAL=$(jq -r '.heartbeat_interval // 300' "$CONFIG_PATH")
    export REPORT_DAYS=$(jq -r '.report_days // 30' "$CONFIG_PATH")
else
    echo "WARNING: $CONFIG_PATH not found"
fi

# HA token
if [ -f /run/s6/container_environment/HA_TOKEN ]; then
    export HA_TOKEN=*** /run/s6/container_environment/HA_TOKEN)
fi

export HA_URL="http://localhost:8123"

echo "Platform: ${PLATFORM_URL:-not set}"
echo "Instance: ${INSTANCE_NAME:-My Home Assistant}"
echo "Heartbeat: every ${HEARTBEAT_INTERVAL:-300}s"

if command -v cloudflared &>/dev/null; then
    echo "cloudflared: $(cloudflared --version)"
else
    echo "ERROR: cloudflared not found!"
    exit 1
fi

if [ -z "${HA_TOKEN:-}" ]; then
    echo "WARNING: No HA token found."
fi

cd /app
exec python3 -m app.main
