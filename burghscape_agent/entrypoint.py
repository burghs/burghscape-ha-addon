#!/usr/bin/env python3
import json
import os
import sys
import traceback
import subprocess

CONFIG_PATH = "/data/options.json"

def load_config():
    if os.path.isfile(CONFIG_PATH):
        print(f"Loading config from {CONFIG_PATH}")
        with open(CONFIG_PATH) as f:
            options = json.load(f)
        env_map = {
            "platform_url": "PLATFORM_URL",
            "subscription_token": "SUBSCRIPTION_TOKEN",
            "instance_name": "INSTANCE_NAME",
            "heartbeat_interval": "HEARTBEAT_INTERVAL",
            "monitor_entities": "MONITOR_ENTITIES",
            "monitor_disk": "MONITOR_DISK",
            "monitor_automations": "MONITOR_AUTOMATIONS",
            "monitor_updates": "MONITOR_UPDATES",
            "monitor_backups": "MONITOR_BACKUPS",
            "monitor_frigate": "MONITOR_FRIGATE",
            "report_days": "REPORT_DAYS",
            "ha_token": "HA_TOKEN",
            "backup_enabled": "BACKUP_ENABLED",
            "backup_interval_hours": "BACKUP_INTERVAL_HOURS",
            "backup_max_part_size_mb": "BACKUP_MAX_PART_SIZE_MB",
            "manual_backup_once": "MANUAL_BACKUP_ONCE",
            "version": "VERSION",
        }
        for key, env_var in env_map.items():
            if key in options and options[key] not in (None, ""):
                value = str(options[key])
                if key == "subscription_token":
                    value = value.strip()
                os.environ[env_var] = value



def main():
    try:
        load_config()
        print("Starting agent...")
        subprocess.run([sys.executable, "-m", "app.main"], cwd="/app", check=True)
    except Exception as e:
        print(f"Fatal error in entrypoint: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
