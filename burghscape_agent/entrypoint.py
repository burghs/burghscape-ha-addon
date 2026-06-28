#!/usr/bin/env python3
"""Debug and fix HA token loading + API calls."""
import json
import os
import sys
import traceback
import subprocess

CONFIG_PATH = "/data/options.json"
HA_CONFIG_PATH = "/config/configuration.yaml"


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
        }
        for key, env_var in env_map.items():
            if key in options and options[key] not in (None, ""):
                os.environ[env_var] = str(options[key])
                print(f"  {env_var}={options[key]}")
    else:
        print(f"WARNING: {CONFIG_PATH} not found")


def ensure_ha_trusted_proxies():
    if not os.path.isfile(HA_CONFIG_PATH):
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
    print("Added trusted_proxies")


def get_ha_token():
    """Try multiple methods to get a valid HA API token."""
    
    # Method 1: Check if HA_TOKEN env var is already set and non-empty
    ha_token = os.environ.get("HA_TOKEN", "")
    if ha_token:
        print("HA_TOKEN found in environment")
        return ha_token
    
    # Method 2: Try SUPERVISOR_TOKEN env var
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN", "")
    if supervisor_token:
        print(f"SUPERVISOR_TOKEN found in env (length={len(supervisor_token)})")
        return supervisor_token
    
    # Method 3: Try s6 container environment paths
    s6_paths = [
        "/run/s6/container_environment/SUPERVISOR_TOKEN",
        "/run/s6/container_environment/HA_TOKEN",
        "/run/s6-rc.env/SUPERVISOR_TOKEN",
    ]
    for path in s6_paths:
        if os.path.isfile(path):
            with open(path) as f:
                token = f.read().strip()
            if token:
                print(f"Token found at {path} (length={len(token)})")
                return token
    
    # Method 4: Try /run/secrets/
    secret_paths = [
        "/run/secrets/supervisor_token",
        "/run/secrets/ha_token",
    ]
    for path in secret_paths:
        if os.path.isfile(path):
            with open(path) as f:
                token = f.read().strip()
            if token:
                print(f"Token found at {path} (length={len(token)})")
                return token
    
    # Method 5: Check all env vars for anything token-like
    for key, val in sorted(os.environ.items()):
        if any(x in key.upper() for x in ["TOKEN", "SECRET", "KEY", "PASS"]):
            print(f"  Env: {key}={val[:10]}... (len={len(val)})")
    
    print("WARNING: No HA token found anywhere!")
    return ""


def main():
    load_config()
    ensure_ha_trusted_proxies()
    
    # Get HA token
    ha_token = get_ha_token()
    if ha_token:
        os.environ["HA_TOKEN"] = ha_token
        print(f"HA_TOKEN set (length={len(ha_token)})")
    else:
        print("WARNING: HA API calls will fail without token!")
    
    # Set HA URL
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
    
    # Launch
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
