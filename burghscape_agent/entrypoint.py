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
    47|    print(f"DEBUG: ensure_ha_trusted_proxies - received hostname: {hostname}")
    48|    if not os.path.isfile(HA_CONFIG_PATH):
    49|        print(f"WARNING: HA config not found at {HA_CONFIG_PATH}")
    50|        return
    51|    
    52|    with open(HA_CONFIG_PATH, "r") as f:
    53|        content = f.read()
    54|    
    55|    # original issue: this line overwrites the passed hostname with an env var that may not be set yet, or is empty.
    56|    # external_url = f"https://{hostname}" if hostname else None
    57|    # FIXED: Use the passed hostname argument directly.
    58|    current_hostname_for_config = hostname # Use the hostname passed as argument
    59|    external_url = f"https://{current_hostname_for_config}" if current_hostname_for_config else None
    60|    
    61|    print(f"DEBUG: ensure_ha_trusted_proxies - current_hostname_for_config: {current_hostname_for_config}, external_url: {external_url}")
    62|
    63|    already_has_trusted = "use_x_forwarded_for" in content and "trusted_proxies" in content
    64|    already_has_external = external_url and external_url in content
    65|    
    66|    if already_has_trusted and already_has_external:
    67|        print("HA trusted_proxies and external_url already configured")
    68|        return
    69|    
    70|    changes = []
    71|    
    72|    if not already_has_trusted:
    73|        print("Adding trusted_proxies to HA configuration.yaml...")
    74|        http_block = os.linesep.join([
    75|            "",
    76|            "http:",
    77|            "  use_x_forwarded_for: true",
    78|            "  trusted_proxies:",
    79|            "    - 127.0.0.1",
    80|            "    - ::1",
    81|            "    - 172.30.32.0/23",
    82|            "    - 10.0.0.0/8",
    83|            "    - 192.168.0.0/16",
    84|        ]) + os.linesep
    85|        with open(HA_CONFIG_PATH, "a") as f:
    86|            f.write(http_block)
    87|        changes.append("trusted_proxies")
    88|    
    89|    if not already_has_external and external_url:
    90|        print(f"Adding external_url ({external_url}) to HA configuration.yaml...")
    91|        if "homeassistant:" in content:
    92|            nl = chr(10)
    93|            lines = content.split(nl)
    94|            new_lines = []
    95|            for line in lines:
    96|                new_lines.append(line)
    97|                if line.strip() == "homeassistant:":
    98|                    new_lines.append('  external_url: "' + external_url + '"')
    99|            with open(HA_CONFIG_PATH, \"w\") as f:
   100|                f.write(nl.join(new_lines))
   101|        else:
   102|            ha_block = os.linesep.join([
   103|                "",
   104|                "homeassistant:",
   105|                "  external_url: "" + external_url + """,
   106|            ]) + os.linesep
   107|            with open(HA_CONFIG_PATH, "a") as f:
   108|                f.write(ha_block)
   109|        changes.append("external_url")
   110|    
   111|    if changes:
   112|        print(f"Added {', '.join(changes)} to HA configuration. Restart may be needed.")
   113|
   114|def get_tunnel_hostname():
    print(f"DEBUG: get_tunnel_hostname - INSTANCE_NAME env: {os.environ.get("INSTANCE_NAME", "")}")
   115|    """Get tunnel hostname from config or env."""
   116|    print(f"DEBUG: get_tunnel_hostname - INSTANCE_NAME env: {os.environ.get("INSTANCE_NAME", "")}")
   117|    derived_hostname = os.environ.get("INSTANCE_NAME", "") + ".mybeacon.co.za"
    print(f"DEBUG: get_tunnel_hostname - Derived hostname: {derived_hostname}")
   118|    print(f"DEBUG: get_tunnel_hostname - Derived hostname: {derived_hostname}")
   119|    return derived_hostname
   120|
   121|def main():
    print("DEBUG: main - Starting entrypoint main function")
   122|    try:
   123|        print("DEBUG: main - Starting entrypoint main function")
   124|        load_config()
        print(f"DEBUG: main - After load_config. PLATFORM_URL: {os.environ.get("PLATFORM_URL")}, INSTANCE_NAME: {os.environ.get("INSTANCE_NAME")}")
   125|        print(f"DEBUG: main - After load_config. PLATFORM_URL: {os.environ.get("PLATFORM_URL")}, INSTANCE_NAME: {os.environ.get("INSTANCE_NAME")}")
   126|        hostname = get_tunnel_hostname()
        print(f"DEBUG: main - After get_tunnel_hostname. hostname: {hostname}")
   127|        print(f"DEBUG: main - After get_tunnel_hostname. hostname: {hostname}")
   128|        os.environ["TUNNEL_HOSTNAME"] = hostname
        print(f"DEBUG: main - After setting TUNNEL_HOSTNAME env: {os.environ.get("TUNNEL_HOSTNAME")}")
   129|        print(f"DEBUG: main - After setting TUNNEL_HOSTNAME env: {os.environ.get("TUNNEL_HOSTNAME")}")
   130|        ensure_ha_trusted_proxies(hostname)
   131|        print("Starting agent...")
   132|        import subprocess
   133|        result = subprocess.run([sys.executable, "-m", "app.main"], cwd="/app")
   134|        sys.exit(result.returncode)
   135|    except Exception as e:
   136|        print(f"Fatal error: {e}")
   137|        traceback.print_exc()
   138|        sys.exit(1)
   139|
   140|if __name__ == "__main__":
   141|    main()
   142|