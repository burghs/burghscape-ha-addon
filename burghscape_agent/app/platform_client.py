"""Client to report data to central Burghscape platform."""
import asyncio
import aiohttp
import logging

from app.config import Config

logger = logging.getLogger("burghscape.agent")


class PlatformClient:
    def __init__(self, config: Config):
        self.config = config
        self.session: aiohttp.ClientSession | None = None
    
    async def __aenter__(self):
        headers = {
            "Content-Type": "application/json",
        }
        if self.config.subscription_token:
            headers["Authorization"] = f"Bearer {self.config.subscription_token}"
        self.session = aiohttp.ClientSession(
            base_url=self.config.platform_url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
        )
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def send_heartbeat(self, report: dict) -> dict:
        """Send instance report to platform."""
        async with self.session.post("/api/agent/report", json=report) as resp:
            if resp.status in (200, 201):
                return await resp.json()
            body = await resp.text()
            logger.error(f"Platform rejected heartbeat: {resp.status} {body}")
            return {"error": f"HTTP {resp.status}"}

    async def get_tunnel_config(self) -> dict:
        """Fetch Cloudflare tunnel config from platform.
        Platform auto-creates tunnel if none exists."""
        async with self.session.get("/api/tunnels/config") as resp:
            if resp.status == 200:
                data = await resp.json()
                logger.info(f"Tunnel config received: {data.get("hostname")}")
                return data
            elif resp.status == 401:
                logger.error("Invalid subscription token for tunnel config")
                return {}
            else:
                body = await resp.text()
                logger.error(f"Failed to get tunnel config: {resp.status} {body}")
                return {}
