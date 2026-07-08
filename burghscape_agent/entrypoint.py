     1|#!/usr/bin/env python3
     2|"""Entrypoint that loads config, sets up HA trusted_proxies, and launches the agent."""
     3|import json
     4|import os
     5|import sys
     6|import time
     7|import traceback
     8|import subprocess
     9|
    10|CONFIG_PATH = "/data/options.json"
    11|HA_CONFIG_PATH = "/config/configuration.yaml"
    12|
    13|def load_config():
    14|    """Load add-on config from options.json and set as environment variables."""
    15|    if os.path.isfile(CONFIG_PATH):
    16|        print(f"Loading config from {CONFIG_PATH}")
    17|        with open(CONFIG_PATH) as f:
    18|            options = json.load(f)
    19|        
    20|        env_map = {
    21|            "platform_url": "PLATFORM_URL",
    22|            "subscription_token": "SUBSCRIPTION_TOKEN",
    23|            "instance_name": "INSTANCE_NAME",
    24|            "heartbeat_interval": "HEARTBEAT_INTERVAL",
    25|            "ha_token": "HA_TOKEN",
    26|            "version": "VERSION",
    27|            "monitor_entities": "MONITOR_ENTITIES",
    28|            "monitor_disk": "MONITOR_DISK",
    29|            "monitor_automations": "MONITOR_AUTOMATIONS",
    30|            "monitor_updates": "MONITOR_UPDATES",
    31|            "monitor_backups": "MONITOR_BACKUPS",
    32|            "monitor_frigate": "MONITOR_FRIGATE",
    33|            "report_days": "REPORT_DAYS",
    34|            "backup_enabled": "BACKUP_ENABLED",
    35|            "backup_interval_hours": "BACKUP_INTERVAL_HOURS",
    36|            "backup_max_part_size_mb": "BACKUP_MAX_PART_SIZE_MB",
    37|        }
    38|
    39|        for key, env_var in env_map.items():
    40|            if key in options and options[key] not in (None, ""):
    41|                os.environ[env_var] = str(options[key])
    42|    else:
    43|        print(f"WARNING: {CONFIG_PATH} not found, relying on environment variables")
    44|
    45|def ensure_ha_trusted_proxies(hostname: str):
    print(f"DEBUG: ensure_ha_trusted_proxies - received hostname: {hostname}")
    46|    """Add trusted_proxies and external_url to HA configuration.yaml if not present."""
    47|    if not os.path.isfile(HA_CONFIG_PATH):
    48|        print(f"WARNING: HA config not found at {HA_CONFIG_PATH}")
    49|        return
    50|    
    51|    with open(HA_CONFIG_PATH, "r") as f:
    52|        content = f.read()
    53|    
    external_url = f"https://{hostname}" if hostname else None
    print(f"DEBUG: ensure_ha_trusted_proxies - hostname used for external_url: {hostname}, external_url: {external_url}")
    55|    
    56|    already_has_trusted = "use_x_forwarded_for" in content and "trusted_proxies" in content
    57|    already_has_external = external_url and external_url in content
    58|    
    59|    if already_has_trusted and already_has_external:
    60|        print("HA trusted_proxies and external_url already configured")
    61|        return
    62|    
    63|    changes = []
    64|    
    65|    if not already_has_trusted:
    66|        print("Adding trusted_proxies to HA configuration.yaml...")
    67|        http_block = os.linesep.join([
    68|            "",
    69|            "http:",
    70|            "  use_x_forwarded_for: true",
    71|            "  trusted_proxies:",
    72|            "    - 127.0.0.1",
    73|            "    - ::1",
    74|            "    - 172.30.32.0/23",
    75|            "    - 10.0.0.0/8",
    76|            "    - 192.168.0.0/16",
    77|        ]) + os.linesep
    78|        with open(HA_CONFIG_PATH, "a") as f:
    79|            f.write(http_block)
    80|        changes.append("trusted_proxies")
    81|    
    82|    if not already_has_external and external_url:
    83|        print(f"Adding external_url ({external_url}) to HA configuration.yaml...")
    84|        if "homeassistant:" in content:
    85|            nl = chr(10)
    86|            lines = content.split(nl)
    87|            new_lines = []
    88|            for line in lines:
    89|                new_lines.append(line)
    90|                if line.strip() == "homeassistant:":
    91|                    new_lines.append('  external_url: "' + external_url + '"')
    92|            with open(HA_CONFIG_PATH, "w") as f:
    93|                f.write(nl.join(new_lines))
    94|        else:
    95|            ha_block = os.linesep.join([
    96|                "",
    97|                "homeassistant:",
    98|                "  external_url: "" + external_url + """,
    99|            ]) + os.linesep
   100|            with open(HA_CONFIG_PATH, "a") as f:
   101|                f.write(ha_block)
   102|        changes.append("external_url")
   103|    
   104|    if changes:
   105|        print(f"Added {', '.join(changes)} to HA configuration. Restart may be needed.")
   106|
   107|def get_tunnel_hostname():
    print(f"DEBUG: get_tunnel_hostname - INSTANCE_NAME env: {os.environ.get("INSTANCE_NAME", "")}")
   108|    """Get tunnel hostname from config or env."""
   109|    return os.environ.get("INSTANCE_NAME", "") + ".mybeacon.co.za"
   110|
   111|def main():
    print("DEBUG: main - Starting entrypoint main function")
   112|    try:
   113|        load_config()
        print(f"DEBUG: main - After load_config. PLATFORM_URL: {os.environ.get("PLATFORM_URL")}, INSTANCE_NAME: {os.environ.get("INSTANCE_NAME")}")
   114|        hostname = get_tunnel_hostname()
        print(f"DEBUG: main - After get_tunnel_hostname. hostname: {hostname}")
   115|        os.environ["TUNNEL_HOSTNAME"] = hostname
        print(f"DEBUG: main - After setting TUNNEL_HOSTNAME env: {os.environ.get("TUNNEL_HOSTNAME")}")
   116|        ensure_ha_trusted_proxies(hostname)
   117|        print("Starting agent...")
   118|        import subprocess
   119|        result = subprocess.run([sys.executable, "-m", "app.main"], cwd="/app")
   120|        sys.exit(result.returncode)
   121|    except Exception as e:
   122|        print(f"Fatal error: {e}")
   123|        traceback.print_exc()
   124|        sys.exit(1)
   125|
   126|if __name__ == "__main__":
   127|    main()
   128|