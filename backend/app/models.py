"""Database models for Burghscape platform."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, Enum as SQLEnum, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
import enum
from database import Base
class SubscriptionTier(str, enum.Enum):
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"
class ClientStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    CANCELLED = "cancelled"
class BackupStorageBackend(str, enum.Enum):
    R2 = "r2"
    S3 = "s3"
    LOCAL = "local"
class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(50))
    subdomain = Column(String(100), unique=True, nullable=False, index=True)
    tier = Column(SQLEnum(SubscriptionTier), default=SubscriptionTier.BASIC, nullable=False)
    status = Column(SQLEnum(ClientStatus), default=ClientStatus.ACTIVE, nullable=False)
    monthly_hours_included = Column(Integer, default=0)
    hours_used_this_month = Column(Float, default=0.0)
    cloudflare_tunnel_id = Column(String(255))
    cloudflare_tunnel_token = Column(String(500))
    # Backup storage configuration
    backup_storage_backend = Column(SQLEnum(BackupStorageBackend), default=BackupStorageBackend.R2, nullable=False)
    backup_storage_config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen = Column(DateTime)
    tailscale_authkey = Column(String(500), nullable=True)
    instances = relationship("HomeAssistantInstance", back_populates="client", cascade="all, delete-orphan")
    support_tickets = relationship("SupportTicket", back_populates="client", cascade="all, delete-orphan")
    backups = relationship("Backup", back_populates="client", cascade="all, delete-orphan")
    tokens = relationship("SubscriptionToken", back_populates="client", cascade="all, delete-orphan")
    portal_users = relationship("ClientUser", back_populates="client", cascade="all, delete-orphan")
    campaign_targets = relationship("CampaignTarget", back_populates="client", cascade="all, delete-orphan")

    @property
    def hours_remaining(self) -> float:
        return max(0, self.monthly_hours_included - self.hours_used_this_month)

    @property
    def portal_url(self) -> str:
        return f"https://{self.subdomain}.mybeacon.co.za"
class ClientUser(Base):
    __tablename__ = "client_users"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="viewer")  # admin, viewer
    force_password_change = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    client = relationship("Client", back_populates="portal_users")
    campaign_reads = relationship("CampaignReadState", back_populates="user", cascade="all, delete-orphan")
    campaign_popup_events = relationship("CampaignPopupEvent", back_populates="user", cascade="all, delete-orphan")
    onboarding_states = relationship("ClientOnboardingState", back_populates="user", cascade="all, delete-orphan")

class ClientOnboardingState(Base):
    __tablename__ = "client_onboarding_states"
    id = Column(Integer, primary_key=True)
    client_user_id = Column(Integer, ForeignKey("client_users.id", ondelete="CASCADE"), nullable=False, index=True)
    onboarding_version = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, default="not_started")
    current_step = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    skipped_at = Column(DateTime)
    last_replay_at = Column(DateTime)
    replay_active = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = relationship("ClientUser", back_populates="onboarding_states")
    __table_args__ = (UniqueConstraint("client_user_id", "onboarding_version", name="uq_client_onboarding_user_version"), Index("ix_client_onboarding_status", "onboarding_version", "status"),)
class HomeAssistantInstance(Base):
    __tablename__ = "ha_instances"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    name = Column(String(255))
    ha_version = Column(String(50))
    ip_address = Column(String(45))
    hostname = Column(String(255))
    is_online = Column(Boolean, default=False)
    last_backup = Column(DateTime)
    next_backup = Column(DateTime)
    disk_usage_percent = Column(Float)
    disk_total_gb = Column(Float)
    disk_used_gb = Column(Float)
    cpu_usage_percent = Column(Float, default=0)
    memory_usage_percent = Column(Float, default=0)
    memory_total_gb = Column(Float, default=0)
    memory_used_gb = Column(Float, default=0)
    addons = Column(JSON, default=list)
    integrations = Column(JSON, default=list)
    uptime_seconds = Column(Integer, default=0)
    automations_count = Column(Integer, default=0)
    entities_count = Column(Integer, default=0)
    updates_available = Column(JSON, default=list)
    send_alerts = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime)
    client = relationship("Client", back_populates="instances")
    alerts = relationship("Alert", back_populates="instance", cascade="all, delete-orphan")
class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    resolution = Column(Text, nullable=True)
    hours_used = Column(Float, default=0.0)
    status = Column(String(50), default="open")
    priority = Column(String(20), default="normal")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    completed_at = Column(DateTime)
    client = relationship("Client", back_populates="support_tickets")
class Backup(Base):
    __tablename__ = "backups"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    filename = Column(String(500))
    size_bytes = Column(Integer)
    # R2/S3 storage metadata
    storage_backend = Column(String(20), default="r2")
    storage_key = Column(String(500))
    storage_etag = Column(String(255))
    status = Column(String(50), default="pending")
    error_message = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    client = relationship("Client", back_populates="backups")
class BackupOperation(Base):
    __tablename__ = "backup_operations"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    operation_id = Column(String(64), nullable=False, unique=True, index=True)
    state = Column(String(20), nullable=False)
    automatic_enabled = Column(Boolean, default=False, nullable=False)
    ha_backup_slug = Column(String(255))
    backup_id = Column(Integer, ForeignKey("backups.id"))
    error_category = Column(String(100))
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime)
    failed_at = Column(DateTime)
class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    instance_id = Column(Integer, ForeignKey("ha_instances.id"), nullable=False)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), default="info")
    message = Column(Text)
    is_resolved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)
    instance = relationship("HomeAssistantInstance", back_populates="alerts")
class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    instance_id = Column(Integer, ForeignKey("ha_instances.id"))
    cpu_percent = Column(Float)
    memory_percent = Column(Float)
    disk_percent = Column(Float)
    uptime_seconds = Column(Integer)
    captured_at = Column(DateTime, default=datetime.utcnow)
class SubscriptionToken(Base):
    __tablename__ = "subscription_tokens"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    token = Column(String(64), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    last_used = Column(DateTime)
    client = relationship("Client", back_populates="tokens")

class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(Integer, primary_key=True, index=True)
    internal_name = Column(String(255), nullable=False, unique=True)
    title = Column(String(255), nullable=False)
    subtitle = Column(String(500))
    campaign_type = Column(String(50), nullable=False, index=True)
    body_content = Column(Text, nullable=False)
    price_text = Column(String(100))
    regular_price_text = Column(String(100))
    call_to_action_label = Column(String(100))
    call_to_action_url = Column(String(1000))
    popup_enabled = Column(Boolean, nullable=False, default=False)
    popup_summary = Column(String(500))
    image_reference = Column(String(255))
    image_content_type = Column(String(50))
    status = Column(String(20), nullable=False, default="draft", index=True)
    priority = Column(Integer, nullable=False, default=0, index=True)
    starts_at = Column(DateTime)
    ends_at = Column(DateTime)
    published_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=False)
    updated_by = Column(String(255), nullable=False)
    target_all_clients = Column(Boolean, nullable=False, default=True)
    archived_at = Column(DateTime)
    targets = relationship("CampaignTarget", back_populates="campaign", cascade="all, delete-orphan")
    read_states = relationship("CampaignReadState", back_populates="campaign", cascade="all, delete-orphan")
    popup_events = relationship("CampaignPopupEvent", back_populates="campaign", cascade="all, delete-orphan")
    __table_args__ = (Index("ix_campaign_visibility", "status", "starts_at", "ends_at", "priority"),)

class CampaignTarget(Base):
    __tablename__ = "campaign_targets"
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True)
    campaign = relationship("Campaign", back_populates="targets")
    client = relationship("Client", back_populates="campaign_targets")

class CampaignReadState(Base):
    __tablename__ = "campaign_read_states"
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    client_user_id = Column(Integer, ForeignKey("client_users.id", ondelete="CASCADE"), nullable=False, index=True)
    read_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    campaign = relationship("Campaign", back_populates="read_states")
    user = relationship("ClientUser", back_populates="campaign_reads")
    __table_args__ = (UniqueConstraint("campaign_id", "client_user_id", name="uq_campaign_read_user"),)


class CampaignPopupEvent(Base):
    __tablename__ = "campaign_popup_events"
    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    client_user_id = Column(Integer, ForeignKey("client_users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(30), nullable=False, index=True)
    occurred_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    campaign = relationship("Campaign", back_populates="popup_events")
    user = relationship("ClientUser", back_populates="campaign_popup_events")
    __table_args__ = (Index("ix_campaign_popup_user_event", "client_user_id", "campaign_id", "event_type"),)
