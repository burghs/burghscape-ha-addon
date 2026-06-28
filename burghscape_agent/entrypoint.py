#!/usr/bin/env python3
"""Entrypoint that loads config, sets up HA trusted_proxies, and launches the agent."""
import json
import os
import sys
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
            "monitor_entities": "MONITOR_ENTITIES",
            "monitor_disk": "MONITOR_DISK",
            "monitor_automations": "MONITOR_AUTOMATIONS",
            "monitor_updates": "MONITOR_UPDATES",
            "monitor_backups": "MONITOR_BACKUPS",
            "monitor_frigate": "MONITOR_FRIGATE",
            "report_days": "REPORT_DAYS",
        }
        
        for key, env_var in env_map.items():
            if key in options and options[key] not in (None, ""):
                os.environ[env_var] = str(options[key])
                print(f"  {env_var}={options[key]}")
    else:
        print(f"WARNING: {CONFIG_PATH} not found, relying on environment variables")


def get_supervisor_token():
    """Get supervisor token from env or s6 container environment."""
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if token:
        return token
    
    # Try s6 container environment paths
    for path in [
        "/run/s6/container_environment/SUPERVISOR_TOKEN",
        "/run/s6-rc.env/SUPERVISOR_TOKEN",
    ]:
        if os.path.isfile(path):
            with open(path) as f:
                token = f.read().strip()
            if token:
                os.environ["SUPERVISOR_TOKEN"] = token
                return token
    
    # Try newer HA addon path
    env_path = "/etc/services.d/supervisor_token"
    if os.path.isfile(env_path):
        with open(env_path) as f:
            token = f.read().strip()
        if token:
            os.environ["SUPERVISOR_TOKEN"] = token
            return token
    
    return ""


def ensure_ha_trusted_proxies():
    """Add trusted_proxies to HA configuration.yaml if not present."""
    if not os.path.isfile(HA_CONFIG_PATH):
        print(f"WARNING: HA config not found at {HA_CONFIG_PATH}")
        return
    
    with open(HA_CONFIG_PATH, "r") as f:
        content = f.read()
    
    if "use_x_forwarded_for" in content and "trusted_proxies" in content:
        print("HA trusted_proxies already configured")
        return
    
    print("Adding trusted_proxies to HA configuration.yaml...")
    
    http_block = """
http:
  use_x_forwarded_for: true
  trusted_proxies:
    - 127.0.0.1
    - ::1
    - 172.30.32.0/23
    - 10.0.0.0/8
    - 192.168.0.0/16
"""
    
    with open(HA_CONFIG_PATH, "a") as f:
        f.write(http_block)
    
    print("Added trusted_proxies. HA restart required to take effect.")


def main():
    load_config()
    
    # Configure HA trusted proxies for Cloudflare tunnel
    ensure_ha_trusted_proxies()
    
    # Get supervisor token - use it for HA API calls
    supervisor_token = get_supervisor_token()
    
    if supervisor_token:
        # Use supervisor token for HA API (via supervisor proxy)
        os.environ["HA_TOKEN"] = supervisor_token
        print("HA_TOKEN set from SUPERVISOR_TOKEN")
    else:
        # Try legacy HA_TOKEN path
        ha_token_path = "/run/s6/container_environment/HA_TOKEN"
        if os.path.isfile(ha_token_path):
            with open(ha_token_path) as f:
                ha_token = f.read().strip()
            if ha_token:
                os.environ["HA_TOKEN"] = ha_token
                print("HA_TOKEN loaded from file")
        else:
            print("WARNING: No HA token found - HA API calls will fail!")
    
    # Set HA URL for API calls
    os.environ["HA_URL"] = "http://supervisor/core/"
    
    # Verify cloudflared
    try:
        result = subprocess.run(["cloudflared", "--version"], capture_output=True, text=True)
        print(f"cloudflared: {result.stdout.strip()}")
    except FileNotFoundError:
        print("ERROR: cloudflared not found!")
        sys.exit(1)
    
    print(f"Platform: {os.environ.get('PLATFORM_URL', 'not set')}")
    print(f"Instance: {os.environ.get('INSTANCE_NAME', 'My Home Assistant')}")
    print(f"Heartbeat: every {os.environ.get('HEARTBEAT_INTERVAL', '300')}s")
    
    # Launch the agent
    os.chdir("/app")
    sys.path.insert(0, "/app")
    
    try:
        from app.main import main_loop
        import asyncio
        asyncio.run(main_loop())
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
