# Burghscape Agent - Client Deployment Guide

## Prerequisites
- Home Assistant (any recent version)
- A subscription token (provided by Burghscape)
- Platform URL: `https://mybeacon.co.za`

## Installation

### Option 1: Sideload the add-on
1. Copy the `ha-agent-addon` folder to your HA's `/addons/` directory via SSH or Samba
2. Go to **Settings → Add-ons → Add-on Store**
3. Click the **three dots** (top right) → **Repositories**
4. Click **Add** and enter: `local:///addons/burghscape_agent`
5. The "Burghscape Agent" will appear in the Local section
6. Click **Install**

### Option 2: Manual Docker (advanced)
If running HA in Docker directly:
```bash
docker run -d \
  --name burghscape-agent \
  --restart unless-stopped \
  -v /path/to/config:/config \
  -e PLATFORM_URL=https://mybeacon.co.za \
  -e SUBSCRIPTION_TOKEN=your-token-here \
  -e INSTANCE_NAME="Your Home" \
  -e HA_TOKEN=your-ha-long-lived-token \
  -e HA_URL=http://homeassistant:8123 \
  burghscape/ha-agent:0.2.0
```

## Configuration

After install, click **Configuration** and set:
- **Platform URL**: `https://mybeacon.co.za`
- **Subscription Token**: (provided by Burghscape)
- **Instance Name**: A friendly name like "Daniel Burton Home"

Click **Save** then **Start** the add-on.

## What happens automatically
1. The add-on connects to the Burghscape platform
2. A Cloudflare Tunnel is auto-provisioned for your subdomain (e.g., `daniel.mybeacon.co.za`)
3. cloudflared starts inside the container, creating a secure tunnel to Cloudflare
4. Your HA is now accessible at `https://daniel.mybeacon.co.za` (once DNS propagates — usually instant)
5. Health reports are sent to the platform every 5 minutes

## Troubleshooting

### Check add-on logs
Go to **Settings → Add-ons → Burghscape Agent → Log**

Common issues:
- **"cloudflared not found"**: Rebuild the add-on (re-install)
- **"Invalid subscription token"**: Regenerate token on the platform dashboard
- **"No tunnel config available"**: Ensure your client has a subdomain set in the platform
- **Tunnel not connecting**: Check internet connectivity on the HA machine

### Verify tunnel is working
```bash
# From any computer
curl -I https://your-subdomain.mybeacon.co.za
# Should return HTTP 200 with "server: cloudflare" header
```

## Support
Contact Burghscape for help: support@mybeacon.co.za
