"""Tailscale OAuth auth key generation for client onboarding."""
import httpx
import logging
import importlib
import sys
import os

logger = logging.getLogger("burghscape.tailscale")

# Lazy import to avoid path issues
def _get_settings_class():
    """Import Settings class, handling path issues."""
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    from app.config import Settings
    return Settings


async def generate_auth_key(settings) -> str:
    """Generate a Tailscale auth key for a client agent to join the Tailnet.
    
    Uses the OAuth client credentials stored in settings.
    Returns the auth key string, or empty string on failure.
    """
    client_id = settings.TAILSCALE_OAUTH_CLIENT_ID
    client_secret = settings.TAILSCALE_OAUTH_CLIENT_SECRET
    tag = settings.TAILSCALE_TAG or "burghscape-agent"

    if not client_id or not client_secret:
        logger.warning("Tailscale OAuth credentials not configured")
        return ""

    try:
        async with httpx.AsyncClient() as client:
            # Get OAuth token
            resp = await client.post(
                "https://api.tailscale.com/api/v2/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                timeout=15,
            )
            if resp.status_code != 200:
                logger.error("Tailscale OAuth token request failed: %d", resp.status_code)
                return ""
            token = resp.json().get("access_token", "")

            # Create an auth key
            resp2 = await client.post(
                "https://api.tailscale.com/api/v2/tailnet/-/keys",
                headers={"Authorization": "Bearer " + token},
                json={
                    "capabilities": {
                        "devices": {
                            "create": {
                                "reusable": True,
                                "ephemeral": True,
                                "preauthorized": True,
                                "tags": [tag],
                            }
                        }
                    },
                    "expirySeconds": 7776000,
                    "description": "Burghscape Agent client onboarding",
                },
                timeout=15,
            )
            if resp2.status_code == 200:
                key = resp2.json().get("key", "")
                logger.info("Generated Tailscale auth key for tag=%s", tag)
                return key
            else:
                logger.error("Failed to create auth key: %d %s", resp2.status_code, resp2.text[:200])
                return ""
    except Exception as e:
        logger.error("Tailscale auth key generation error: %s", e, exc_info=True)
        return ""
