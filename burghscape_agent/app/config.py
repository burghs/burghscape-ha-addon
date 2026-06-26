"""Add-on configuration from environment variables."""
import os


class Config:
    """Configuration loaded from add-on options (set by HA)."""
    
    def __init__(self):
        # HA Core connection
        self.ha_url = os.getenv("HA_URL", "http://supervisor/core/")
        self.ha_token = os.getenv("HA_TOKEN", "")
        
        # Platform connection
        self.platform_url = os.getenv("PLATFORM_URL", "").rstrip("/")
        self.subscription_token = os.getenv("SUBSCRIPTION_TOKEN", "")
        
        # Instance settings
        self.instance_name = os.getenv("INSTANCE_NAME", "My Home Assistant")
        self.ip_address = os.getenv("IP_ADDRESS", "")
        self.heartbeat_interval = int(os.getenv("HEARTBEAT_INTERVAL", "300"))
        
        # Monitoring toggles
        self.monitor_entities = os.getenv("MONITOR_ENTITIES", "true").lower() == "true"
        self.monitor_disk = os.getenv("MONITOR_DISK", "true").lower() == "true"
        self.monitor_automations = os.getenv("MONITOR_AUTOMATIONS", "true").lower() == "true"
        self.monitor_updates = os.getenv("MONITOR_UPDATES", "true").lower() == "true"
        self.monitor_backups = os.getenv("MONITOR_BACKUPS", "false").lower() == "true"
        self.monitor_frigate = os.getenv("MONITOR_FRIGATE", "false").lower() == "true"
        
        # Cloudflare Tunnel (fetched from platform automatically)
        self.cloudflare_tunnel_token = os.getenv("CLOUDFLARE_TUNNEL_TOKEN", "")
        self.cloudflare_tunnel_id = ""
        self.cloudflare_account_tag = ""
        self.cloudflare_tunnel_config = ""
        
        # Data retention
        self.report_days = int(os.getenv("REPORT_DAYS", "30"))
    
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
