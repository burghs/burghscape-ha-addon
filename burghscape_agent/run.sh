#!/usr/bin/env bash
set -euo pipefail

CONFIG_PATH=/config/options.json

echo "Burghscape Agent starting..."

# Use Python to parse JSON config (jq not available in container)
export PLATFORM_URL=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('platform_url',''))" "$CONFIG_PATH")
export SUBSCRIPTION_TOKEN=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('subscription_token',''))" "$CONFIG_PATH")
export INSTANCE_NAME=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('instance_name','My Home Assistant'))" "$CONFIG_PATH")
export HEARTBEAT_INTERVAL=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('heartbeat_interval',300))" "$CONFIG_PATH")
export MONITOR_ENTITIES=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('monitor_entities','true'))" "$CONFIG_PATH")
export MONITOR_DISK=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('monitor_disk','true'))" "$CONFIG_PATH")
export MONITOR_AUTOMATIONS=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('monitor_automations','true'))" "$CONFIG_PATH")
export MONITOR_UPDATES=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('monitor_updates','true'))" "$CONFIG_PATH")
export MONITOR_BACKUPS=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('monitor_backups','false'))" "$CONFIG_PATH")
export MONITOR_FRIGATE=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('monitor_frigate','false'))" "$CONFIG_PATH")
export REPORT_DAYS=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('report_days',30))" "$CONFIG_PATH")

# Get HA token from supervisor
export HA_TOKEN=$(cat /run/s6/container_environment/HA_TOKEN 2>/dev/null || echo "")

# Internal HA URL (always localhost inside the add-on container)
export HA_URL="http://localhost:8123"

echo "Platform: $PLATFORM_URL"
echo "Instance: $INSTANCE_NAME"
echo "Heartbeat: every ${HEARTBEAT_INTERVAL}s"

# Verify cloudflared is installed
if command -v cloudflared &> /dev/null; then
    echo "cloudflared: $(cloudflared --version)"
else
    echo "ERROR: cloudflared not found! Check Dockerfile."
    exit 1
fi

if [ -z "$HA_TOKEN" ]; then
    echo "WARNING: No HA token found. Set in add-on config."
fi

# The Python agent handles tunnel setup internally via /api/tunnels/config
exec python3 -m app.main
