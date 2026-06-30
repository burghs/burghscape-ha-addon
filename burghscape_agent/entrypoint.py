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
            "backup_sftp_host": "BACKUP_SFTP_HOST",
            "backup_sftp_user": "BACKUP_SFTP_USER",
            "backup_sftp_path": "BACKUP_SFTP_PATH",
        }
        
        for key, env_var in env_map.items():
            if key in options and options[key] not in (None, ""):
                os.environ[env_var] = str(options[key])
                print(f"  {env_var}={options[key]}")
    else:
        print(f"WARNING: {CONFIG_PATH} not found, relying on environment variables")


def write_backup_ssh_key():
    """Write backup SSH private key from config to file for paramiko."""
    key_path = "/config/burghscape/backup_key"
    # Check if key already written (env var set by env_map or already exists)
    if os.path.isfile(key_path):
        os.chmod(key_path, 0o600)
        print("Backup SSH key already exists at %s", key_path)
        return

    # Get key from options.json directly (not in env_map to avoid printing it)
    if os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            options = json.load(f)
        ssh_key = options.get("backup_ssh_key", "")
        if ssh_key:
            os.makedirs(os.path.dirname(key_path), exist_ok=True)
            with open(key_path, "w") as f:
                f.write(ssh_key)
            os.chmod(key_path, 0o600)
            print("Backup SSH key written to %s" % key_path)
            os.environ["BACKUP_SSH_KEY"] = key_path


def get_tunnel_hostname():
    """Get tunnel hostname from platform API."""
    import urllib.request
    import json as json_mod
    platform_url = os.environ.get("PLATFORM_URL", "https://api.mybeacon.co.za")
    instance_name = os.environ.get("INSTANCE_NAME", "")
    subscription_token = os.environ.get("SUBSCRIPTION_TOKEN", "")
    
    # Try platform API first
    try:
        url = f"{platform_url.rstrip('/')}/api/tunnels/config"
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {subscription_token}",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json_mod.loads(resp.read())
            hostname = data.get("hostname", "")
            if hostname:
                return hostname
    except Exception:
        pass
    
    # Fallback: derive from instance name
    instance = instance_name.lower().replace(" ", "-")
    if instance:
        return f"{instance}.mybeacon.co.za"
    return None


def ensure_ha_trusted_proxies():
    """Add trusted_proxies and external_url to HA configuration.yaml if not present."""
    if not os.path.isfile(HA_CONFIG_PATH):
        print(f"WARNING: HA config not found at {HA_CONFIG_PATH}")
        return
    
    with open(HA_CONFIG_PATH, "r") as f:
        content = f.read()
    
    # Get the tunnel hostname
    hostname = get_tunnel_hostname()
    external_url = f"https://{hostname}" if hostname else None
    
    # Check if already configured
    already_has_trusted = "use_x_forwarded_for" in content and "trusted_proxies" in content
    already_has_external = external_url and external_url in content
    
    if already_has_trusted and already_has_external:
        print("HA trusted_proxies and external_url already configured")
        return
    
    changes = []
    
    if not already_has_trusted:
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
        changes.append("trusted_proxies")
    
    if not already_has_external and external_url:
        print(f"Adding external_url ({external_url}) to HA configuration.yaml...")
        # Add external_url to existing homeassistant block or create new one
        if "homeassistant:" in content:
            # Insert external_url right after the "homeassistant:" line
            lines = content.split("\n")
            new_lines = []
            for line in lines:
                new_lines.append(line)
                if line.strip() == "homeassistant:":
                    new_lines.append(f'  external_url: "{external_url}"')
            with open(HA_CONFIG_PATH, "w") as f:
                f.write("\n".join(new_lines))
        else:
            ha_block = f"""
homeassistant:
  external_url: "{external_url}"
"""
            with open(HA_CONFIG_PATH, "a") as f:
                f.write(ha_block)
        changes.append("external_url")
    
    if changes:
        print(f"Added {', '.join(changes)}. HA restart required to take effect.")
    
    # Try to restart HA via supervisor API (multiple URLs for host_network)
    try:
        import urllib.request
        supervisor_token = os.environ.get("SUPERVISOR_TOKEN", "")
        if os.path.isfile("/run/s6/container_environment/SUPERVISOR_TOKEN"):
            with open("/run/s6/container_environment/SUPERVISOR_TOKEN") as f:
                supervisor_token = f.read().strip()
        
        if supervisor_token:
            restarted = False
            for url in ["http://supervisor/homeassistant/restart", "http://localhost:8080/homeassistant/restart"]:
                try:
                    req = urllib.request.Request(
                        url,
                        method="POST",
                        headers={"Authorization": f"Bearer {supervisor_token}"}
                    )
                    urllib.request.urlopen(req, timeout=10)
                    print(f"HA restart triggered via {url}")
                    restarted = True
                    break
                except Exception:
                    continue
            if not restarted:
                print("Could not auto-restart HA via supervisor")
                print("Please restart HA manually for changes to take effect")
    except Exception as e:
        print(f"Could not auto-restart HA: {e}")
        print("Please restart HA manually for changes to take effect")


def main():
    load_config()

    # Write backup SSH key if configured
    write_backup_ssh_key()

    # Configure HA trusted proxies for Cloudflare tunnel
    ensure_ha_trusted_proxies()
    
    # Ensure HA_TOKEN is set (from env_map or s6 container env)
    if not os.environ.get("HA_TOKEN"):
        ha_token_path = "/run/s6/container_environment/HA_TOKEN"
        if os.path.isfile(ha_token_path):
            with open(ha_token_path) as f:
                ha_token = f.read().strip()
            if ha_token:
                os.environ["HA_TOKEN"] = ha_token
                print("HA_TOKEN loaded from s6 container env")
    
    if os.environ.get("HA_TOKEN"):
        print("HA_TOKEN: configured (length=%d)" % len(os.environ["HA_TOKEN"]))
    else:
        print("WARNING: HA_TOKEN not set — HA API calls will fail")
    
    # Set HA URL for API calls
    os.environ["HA_URL"] = "http://localhost:8123/"
    
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
