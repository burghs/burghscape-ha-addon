#!/usr/bin/env python3
"""Entrypoint that loads config, sets up HA trusted_proxies, and launches the agent."""
import json
import os
import sys
import time
import traceback
import subprocess

CONFIG_PATH = "/data/options.json"
HA_CONFIG_PATH = "/config/configuration.yaml"

def load_config():
    """Load add-on config from options.json and set as environment variables."""
    if os.path.isfile(CONFIG_PATH):
        print(f"Loading config from {CONFIG_PATH}")
        with open(CONFIG_PATH) as f:
            options = json.load(f)
        
        env_map = {
            "platform_url": "PLATFORM_URL",
            "subscription_token": "SUBSCRIPTION_TOKEN",
            "instance_name": "INSTANCE_NAME",
            "heartbeat_interval": "HEARTBEAT_INTERVAL",
            "ha_token": "HA_TOKEN",
            "version": "VERSION",
            "monitor_entities": "MONITOR_ENTITIES",
            "monitor_disk": "MONITOR_DISK",
            "monitor_automations": "MONITOR_AUTOMATIONS",
            "monitor_updates": "MONITOR_UPDATES",
            "monitor_backups": "MONITOR_BACKUPS",
            "monitor_frigate": "MONITOR_FRIGATE",
            "report_days": "REPORT_DAYS",
            "backup_enabled": "BACKUP_ENABLED",
            "backup_interval_hours": "BACKUP_INTERVAL_HOURS",
            "backup_max_part_size_mb": "BACKUP_MAX_PART_SIZE_MB",
        }

        for key, env_var in env_map.items():
            if key in options and options[key] not in (None, ""):
                os.environ[env_var] = str(options[key])
    else:
        print(f"WARNING: {CONFIG_PATH} not found, relying on environment variables")

def ensure_ha_trusted_proxies(hostname: str):
    """Add trusted_proxies and external_url to HA configuration.yaml if not present."""
    if not os.path.isfile(HA_CONFIG_PATH):
        print(f"WARNING: HA config not found at {HA_CONFIG_PATH}")
        return
    
    with open(HA_CONFIG_PATH, "r") as f:
        content = f.read()
    
    hostname = os.environ.get("TUNNEL_HOSTNAME", "")
    external_url = f"https://{hostname}" if hostname else None
    
    already_has_trusted = "use_x_forwarded_for" in content and "trusted_proxies" in content
    already_has_external = external_url and external_url in content
    
    if already_has_trusted and already_has_external:
        print("HA trusted_proxies and external_url already configured")
        return
    
    changes = []
    
    if not already_has_trusted:
        print("Adding trusted_proxies to HA configuration.yaml...")
        http_block = os.linesep.join([
            "",
            "http:",
            "  use_x_forwarded_for: true",
            "  trusted_proxies:",
            "    - 127.0.0.1",
            "    - ::1",
            "    - 172.30.32.0/23",
            "    - 10.0.0.0/8",
            "    - 192.168.0.0/16",
        ]) + os.linesep
        with open(HA_CONFIG_PATH, "a") as f:
            f.write(http_block)
        changes.append("trusted_proxies")
    
    if not already_has_external and external_url:
        print(f"Adding external_url ({external_url}) to HA configuration.yaml...")
        if "homeassistant:" in content:
            nl = chr(10)
            lines = content.split(nl)
            new_lines = []
            for line in lines:
                new_lines.append(line)
                if line.strip() == "homeassistant:":
                    new_lines.append('  external_url: "' + external_url + '"')
            with open(HA_CONFIG_PATH, "w") as f:
                f.write(nl.join(new_lines))
        else:
            ha_block = os.linesep.join([
                "",
                "homeassistant:",
                "  external_url: \"" + external_url + "\"",
            ]) + os.linesep
            with open(HA_CONFIG_PATH, "a") as f:
                f.write(ha_block)
        changes.append("external_url")
    
    if changes:
        print(f"Added {', '.join(changes)} to HA configuration. Restart may be needed.")

def get_tunnel_hostname():
    """Get tunnel hostname from config or env."""
    return os.environ.get("INSTANCE_NAME", "") + ".mybeacon.co.za"

def main():
    try:
        load_config()
                hostname = get_tunnel_hostname()
        os.environ["TUNNEL_HOSTNAME"] = hostname
        ensure_ha_trusted_proxies(hostname)
        print("Starting agent...")
        import subprocess
        result = subprocess.run([sys.executable, "-m", "app.main"], cwd="/app")
        sys.exit(result.returncode)
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
