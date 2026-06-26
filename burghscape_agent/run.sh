#!/usr/bin/env bash
set -euo pipefail

echo "Burghscape Agent starting..."

CONFIG_PATH=/data/options.json

if [ -f "$CONFIG_PATH" ]; then
    echo "Loading config from $CONFIG_PATH..."
    PLATFORM_URL=$(jq -r '.platform_url // ""' "$CONFIG_PATH")
    SUBSCRIPTION_TOKEN=*** -r '.subscription_token // ""' "$CONFIG_PATH")
    INSTANCE_NAME=$(jq -r '.instance_name // "My Home Assistant"' "$CONFIG_PATH")
    HEARTBEAT_INTERVAL=$(jq -r '.heartbeat_interval // 300' "$CONFIG_PATH")
    export PLATFORM_URL SUBSCRIPTION_TOKEN INSTANCE_NAME HEARTBEAT_INTERVAL
else
    echo "WARNING: No config file at $CONFIG_PATH, using env vars"
fi

# Get HA token from supervisor
if [ -f /run/s6/container_environment/HA_TOKEN ]; then
    HA_TOKEN=*** /run/s6/container_environment/HA_TOKEN)
    export HA_TOKEN
fi

export HA_URL="http://localhost:8123"

echo "Platform: $PLATFORM_URL"
echo "Instance: ${INSTANCE_NAME:-My Home Assistant}"
echo "Heartbeat: every ${HEARTBEAT_INTERVAL:-300}s"

if command -v cloudflared &> /dev/null; then
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
