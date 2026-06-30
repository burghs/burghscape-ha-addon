"""Add-on configuration from environment variables."""
import os


def _get_int_env(var_name, default):
    """Safely get an integer environment variable."""
    val = os.getenv(var_name, "")
    if val == "":
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _get_bool_env(var_name, default):
    """Safely get a boolean environment variable."""
    val = os.getenv(var_name, "")
    if val == "":
        return default
    return str(val).lower() == "true"


class Config:
    """Configuration loaded from add-on options (set by HA)."""
    
    def __init__(self):
        # HA Core connection - use supervisor API proxy
        self.ha_url = os.getenv("HA_URL", "http://localhost:8123/")
        self.ha_token = os.getenv("HA_TOKEN", "")
        
        # Platform connection
        self.platform_url = os.getenv("PLATFORM_URL", "").rstrip("/")
        self.subscription_token = os.getenv("SUBSCRIPTION_TOKEN", "")
        
        # Instance settings
        self.instance_name = os.getenv("INSTANCE_NAME", "My Home Assistant")
        self.ip_address = os.getenv("IP_ADDRESS", "")
        self.burghscape_version = os.getenv("VERSION", "")
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

        # Client backup (SFTP to Burghscape VM)
        self.backup_enabled = _get_bool_env("BACKUP_ENABLED", False)
        self.backup_interval_hours = _get_int_env("BACKUP_INTERVAL_HOURS", 24)
        self.backup_sftp_host = os.getenv("BACKUP_SFTP_HOST", "")
        self.backup_sftp_user = os.getenv("BACKUP_SFTP_USER", "kenny")
        self.backup_sftp_path = os.getenv("BACKUP_SFTP_PATH", "/home/kenny/client-backups")
        self.backup_ssh_key_path = os.getenv("BACKUP_SSH_KEY", "/config/burghscape/backup_key")
    
    def validate(self):
        """Validate configuration."""
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


config = Config()
