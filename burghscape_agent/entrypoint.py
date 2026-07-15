#!/usr/bin/env python3
import json
import os
import sys
import traceback
import subprocess
import yaml

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
            "ha_token": "HA_TOKEN",
            "version": "VERSION",
        }
        for key, env_var in env_map.items():
            if key in options and options[key] not in (None, ""):
                value = str(options[key])
                if key == "subscription_token":
                    value = value.strip()
                os.environ[env_var] = value

def ensure_ha_config(hostname: str):
    if not os.path.isfile(HA_CONFIG_PATH):
        print(f"WARNING: HA config not found at {HA_CONFIG_PATH}")
        return

    try:
        with open(HA_CONFIG_PATH, 'r') as f:
            ha_config = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"ERROR: Could not parse {HA_CONFIG_PATH}: {e}. Skipping modifications.")
        return

    made_changes = False
    
    # Ensure http block
    http_config = ha_config.get('http', {})
    if not isinstance(http_config, dict): http_config = {}
    if not http_config.get('use_x_forwarded_for') or not http_config.get('trusted_proxies'):
        print("Updating http config for trusted_proxies...")
        http_config['use_x_forwarded_for'] = True
        current_proxies = set(http_config.get('trusted_proxies', []))
        current_proxies.update(["127.0.0.1", "::1", "172.30.32.0/23"])
        http_config['trusted_proxies'] = sorted(list(current_proxies))
        ha_config['http'] = http_config
        made_changes = True

    # Ensure homeassistant block
    external_url = f"https://{hostname}"
    homeassistant_config = ha_config.get('homeassistant', {})
    if not isinstance(homeassistant_config, dict): homeassistant_config = {}
    if homeassistant_config.get('external_url') != external_url:
        print(f"Setting external_url to {external_url}...")
        homeassistant_config['external_url'] = external_url
        ha_config['homeassistant'] = homeassistant_config
        made_changes = True

    if made_changes:
        print(f"Writing updated configuration to {HA_CONFIG_PATH}")
        try:
            with open(HA_CONFIG_PATH, 'w') as f:
                yaml.dump(ha_config, f, default_flow_style=False, sort_keys=False)
            print("Configuration updated. A Home Assistant restart may be required.")
        except Exception as e:
            print(f"ERROR: Failed to write to {HA_CONFIG_PATH}: {e}")
    else:
        print("HA configuration for agent is already correct.")

def get_tunnel_hostname():
    instance_name = os.environ.get("INSTANCE_NAME", "home-assistant")
    return instance_name.lower().replace(" ", "-") + ".mybeacon.co.za"

def main():
    try:
        load_config()
        hostname = get_tunnel_hostname()
        ensure_ha_config(hostname)
        print("Starting agent...")
        subprocess.run([sys.executable, "-m", "app.main"], cwd="/app", check=True)
    except Exception as e:
        print(f"Fatal error in entrypoint: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
