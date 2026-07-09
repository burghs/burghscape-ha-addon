#!/usr/bin/env python3
"""Entrypoint that loads config, sets up HA trusted_proxies, and launches the agent."""
import json
import os
import sys
import time
import traceback
import subprocess
import yaml

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
        }

        for key, env_var in env_map.items():
            if key in options and options[key] not in (None, ""):
                os.environ[env_var] = str(options[key])
    else:
        print(f"WARNING: {CONFIG_PATH} not found, relying on environment variables")

def ensure_ha_config(hostname: str):
    """Ensure trusted_proxies and external_url are correctly set in configuration.yaml."""
    if not os.path.isfile(HA_CONFIG_PATH):
        print(f"WARNING: HA config not found at {HA_CONFIG_PATH}")
        return

    try:
        with open(HA_CONFIG_PATH, 'r') as f:
            ha_config = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        print(f"ERROR: Could not parse {HA_CONFIG_PATH}. Skipping modifications.")
        return

    made_changes = False
    
    # 1. Ensure http block for trusted proxies
    http_config = ha_config.get('http', {})
    if not isinstance(http_config, dict): http_config = {}
    
    use_x_forwarded_for = http_config.get('use_x_forwarded_for', False)
    trusted_proxies = http_config.get('trusted_proxies', [])
    
    required_proxies = ["127.0.0.1", "::1", "172.30.32.0/23"]
    
    if not use_x_forwarded_for or any(p not in trusted_proxies for p in required_proxies):
        print("Updating http config for trusted_proxies...")
        http_config['use_x_forwarded_for'] = True
        current_proxies = set(trusted_proxies)
        current_proxies.update(required_proxies)
        http_config['trusted_proxies'] = sorted(list(current_proxies))
        ha_config['http'] = http_config
        made_changes = True

    # 2. Ensure homeassistant block for external_url
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
    """Get tunnel hostname from config or env."""
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
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
