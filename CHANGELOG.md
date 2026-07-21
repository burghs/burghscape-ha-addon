# 0.2.54

- Poll for administrator-queued managed backup operations and run them through the existing manual create, download, upload, and operation-state workflow.
- Preserve manual-only behavior; recurring scheduling, retention, and restore remain unavailable.

# 0.2.52

- Report managed backup transitions to the platform and expose whether automatic backups are enabled.
- Preserve manual-only behavior; recurring scheduling, retention, and restore remain unavailable.

# Changelog

## v0.2.26 (2026-07-03)

### 🎯 Fix: Backup Detection Now Works Without API
- Switched from HA API `/api/hassio/backups` to **filesystem-based detection** — reads `/backup/` directory directly
- This works on EVERY HA installation with NO API permissions needed
- Backup check now always runs (no config toggle required)
- Falls back to hassio API if filesystem unavailable
- Falls back to entity-based detection as last resort

### ✅ Portal Display
- Backup status now shows real data: last backup time, file count, total size
- Supports all formats: "2h ago", "3d ago", exact dates

## v0.2.25 (2026-07-03)

### ✨ New Feature: Real HA Backup Status
- Addon now queries Home Assistant's built-in /api/backups API to report real backup data
- Shows: last backup time, file count, total size, backup status
- Falls back to entity-based detection if /api/backups is unavailable
- Backup monitoring enabled by default (monitor_backups: true)

### 🎨 Portal Layout Improvements
- Monthly Hours + Support Tickets + System Report + HA News grouped together in a compact 2x2 grid
- Backup Status moved to its own section at the bottom
- Cleaner, more efficient use of space

### 🔧 Platform Changes
- Stores real backup data from HA API on each heartbeat
- Portal displays "Last Backup" with relative time (e.g. 2h ago, 3d ago)
- Email alerts and PDF report generation continue to work

## v0.2.24 (2026-07-01)

### 🔧 Fixes
- Fixed supervisor env var passing so HA_TOKEN is properly set
- Portal now automatically detects logged-in user's client

## v0.2.23 (2026-07-01)

### 🚀 Features
- R2 backup storage integration
- Entrypoint fixes for supervisor API fallback
- Cloudflare tunnel auto-config from platform

## v0.2.22 (2026-06-29)

### ✨ Features
- Tailscale auto-join on startup (auth key from platform)
- Client backup: HA backup via SFTP to VM over Tailscale
- Retention: keeps last 3 backups per client
- Platform config fetch
- Heartbeat includes tailscale status + backup_status
- HA trusted_proxies + external_url auto-config

## v0.2.21 (2026-06-28)

### 🚀 Initial Release
- Basic agent heartbeat with HA version, entities, automations
- Cloudflare tunnel management
- Platform dashboard integration
- Welcome emails with credentials
- Online/offline alert emails
- PDF system report generation
- Per-instance alert toggles