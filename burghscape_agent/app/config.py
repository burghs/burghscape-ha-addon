"""Add-on configuration from environment variables."""
import os


def _get_int_env(var_name, default):
    val = os.getenv(var_name, "")
    if val == "":
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _get_bool_env(var_name, default):
    val = os.getenv(var_name, "")
    if val == "":
        return default
    return str(val).lower() == "true"


def _load_token_from_files():
    """Try to load SUPERVISOR_TOKEN from various file locations."""
    for path in [
        "/run/s6/container_environment/SUPERVISOR_TOKEN",
        "/run/secrets/supervisor_token",
    ]:
        if os.path.isfile(path):
            with open(path) as f:
                token = f.read().strip()
            if token:
                return token
    return ""


class Config:
    """Configuration loaded from add-on options (set by HA)."""
    
    def __init__(self):
        # HA Core connection - use supervisor API proxy
        self.ha_url = os.getenv("HA_URL", "http://localhost:8123")
        
        # HA Token: use ha_token from config first, then fall back to SUPERVISOR_TOKEN
        self.ha_token = os.getenv("HA_TOKEN", "")
        if not self.ha_token:
            # Fall back to SUPERVISOR_TOKEN env or file
            self.ha_token = os.environ.get("SUPERVISOR_TOKEN", "") or _load_token_from_files()
        
        # Platform connection
        self.platform_url = os.getenv("PLATFORM_URL", "").rstrip("/")
        self.subscription_token = os.getenv("SUBSCRIPTION_TOKEN", "")
        
        # Instance settings
        self.instance_name = os.getenv("INSTANCE_NAME", "My Home Assistant")
        self.ip_address = os.getenv("IP_ADDRESS", "")
        self.heartbeat_interval = _get_int_env("HEARTBEAT_INTERVAL", 300)
        
        # Monitoring toggles
        self.monitor_entities = _get_bool_env("MONITOR_ENTITIES", True)
        self.monitor_disk = _get_bool_env("MONITOR_DISK", True)
        self.monitor_automations = _get_bool_env("MONITOR_AUTOMATIONS", True)
        self.monitor_updates = _get_bool_env("MONITOR_UPDATES", True)
        self.monitor_backups = _get_bool_env("MONITOR_BACKUPS", False)
        self.monitor_frigate = _get_bool_env("MONITOR_FRIGATE", False)
        
        # Cloudflare Tunnel (fetched from platform automatically)
        self.cloudflare_tunnel_token = os.getenv("CLOUDFLARE_TUNNEL_TOKEN", "")
        self.cloudflare_tunnel_id = ""
        self.cloudflare_account_tag = ""
        self.cloudflare_tunnel_config = ""
        
        # Data retention
        self.report_days = _get_int_env("REPORT_DAYS", 30)
    
    def validate(self):
        errors = []
        if not self.platform_url:
            errors.append("PLATFORM_URL is required")
        if not self.subscription_token:
            errors.append("SUBSCRIPTION_TOKEN is required")
        if not self.ha_url:
            errors.append("HA_URL is required")
        return errors
    
    def __repr__(self):
        return (
            f"Config(platform_url={self.platform_url}, "
            f"instance_name={self.instance_name}, "
            f"interval={self.heartbeat_interval}s)"
        )
