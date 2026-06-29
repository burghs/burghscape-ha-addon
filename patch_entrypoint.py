#!/usr/bin/env python3
import sys

with open("burghscape_agent/entrypoint.py", "r") as f:
    content = f.read()

# Add ha_token to env_map in load_config
old = '"report_days": "REPORT_DAYS",\n        },'
new = '"report_days": "REPORT_DAYS",\n            "ha_token": "HA_TOKEN",\n        },'

if old in content:
    content = content.replace(old, new)
    print("Patched: added ha_token to env_map")
else:
    print("WARNING: could not find env_map pattern")

# Also remove the redundant HA_TOKEN loading from s6 path (now handled by env_map)
old2 = '''    # Get HA token from supervisor
    ha_token_path = "/run/s6/container_environment/HA_TOKEN"
    if os.path.isfile(ha_token_path):
        with open(ha_token_path) as f:
            ha_token = f.read().strip()
        if ha_token:
            os.environ["HA_TOKEN"] = ha_token
            print("HA_TOKEN loaded from supervisor")'''

new2 = '''    # HA_TOKEN also loaded from options.json via load_config() above
    # Fallback: try s6 container environment
    if not os.environ.get("HA_TOKEN"):
        ha_token_path = "/run/s6/container_environment/HA_TOKEN"
        if os.path.isfile(ha_token_path):
            with open(ha_token_path) as f:
                ha_token = f.read().strip()
            if ha_token:
                os.environ["HA_TOKEN"] = ha_token
                print("HA_TOKEN loaded from supervisor environment")'''

if old2 in content:
    content = content.replace(old2, new2)
    print("Patched: HA_TOKEN fallback logic updated")
else:
    print("WARNING: could not find HA_TOKEN block")

with open("burghscape_agent/entrypoint.py", "w") as f:
    f.write(content)

print("Done")
