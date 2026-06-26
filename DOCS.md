# Burghscape Agent

Central monitoring agent that reports your Home Assistant instance status to the Burghscape management platform. Also creates a Cloudflare Tunnel for secure remote access.

## Configuration

- **Platform URL**: Your central dashboard URL (e.g., https://mybeacon.co.za)
- **Subscription Token**: API token from your platform dashboard
- **Instance Name**: Friendly name for this HA instance (e.g., "Daniel Burton Home")
- **Heartbeat Interval**: How often to report (in seconds, default: 300)

## Monitoring Options

- **Entities**: Count and categorize all entities
- **Disk Usage**: Monitor storage utilization
- **Automations**: Track automation count and status
- **Updates**: Track available updates for core, add-ons, etc.
- **Backups**: Monitor backup status (if configured)
- **Frigate**: Monitor Frigate NVR status (if installed)

## Cloudflare Tunnel

The agent automatically fetches Cloudflare Tunnel credentials from the platform and starts cloudflared inside the container. No manual tunnel configuration needed — just ensure your client has a tunnel configured in the platform dashboard.

## Features

- Automatic HA API discovery
- Periodic health reporting to central platform
- Cloudflare Tunnel for secure remote access
- Lightweight, low resource usage
- Configurable monitoring toggles
- Automatic restart on failure

## Support

Visit https://mybeacon.co.za for support.
