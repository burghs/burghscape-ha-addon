#!/bin/bash
export PATH=$HOME/.local/bin:$PATH
export PLATFORM_URL=http://192.168.1.112:8000
export ACCESS_TOKEN=*** INSTANCE_NAME=Dev HA
export IP_ADDRESS=192.168.1.100
export HEARTBEAT_INTERVAL=60
export MONITOR_ENTITIES=true
export MONITOR_DISK=true
export MONITOR_AUTOMATIONS=true
export MONITOR_UPDATES=true
export MONITOR_BACKUPS=false
export MONITOR_FRIGATE=false
export REPORT_DAYS=30

cd /home/kenny/burghscape/ha-agent-addon
exec python3 -c "
import os, sys
sys.path.insert(0, ".")
# Read token from file
token = open("/home/kenny/burghscape/ha_token.txt").read().strip()
os.environ["HA_TOKEN"] = token
from app.main import main_loop
import asyncio
asyncio.run(main_loop())
"
