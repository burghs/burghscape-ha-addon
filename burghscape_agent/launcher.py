import os, sys, asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("PLATFORM_URL", "http://192.168.1.112:8000")
os.environ.setdefault("SUBSCRIPTION_TOKEN", "H8pWGiNXfmdDUUZeD2VMEwxeRUt02-L7Vce3W8R4r0w")
os.environ.setdefault("INSTANCE_NAME", "Dev HA")
os.environ.setdefault("IP_ADDRESS", "192.168.1.100")
os.environ.setdefault("HA_URL", "http://192.168.1.100:8123/")
os.environ.setdefault("HEARTBEAT_INTERVAL", "60")
os.environ.setdefault("MONITOR_ENTITIES", "true")
os.environ.setdefault("MONITOR_DISK", "true")
os.environ.setdefault("MONITOR_AUTOMATIONS", "true")
os.environ.setdefault("MONITOR_UPDATES", "true")
os.environ.setdefault("MONITOR_BACKUPS", "false")
os.environ.setdefault("MONITOR_FRIGATE", "false")
os.environ.setdefault("REPORT_DAYS", "30")

# Read HA token from file
token = open("/home/kenny/burghscape/ha_token.txt").read().strip()
os.environ["HA_TOKEN"] = token

from app.main import main_loop
asyncio.run(main_loop())
