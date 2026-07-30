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
                logger.info("Tunnel config received: %s", data.get("hostname"))
                return data
            elif resp.status == 401:
                logger.error("Invalid subscription token for tunnel config")
                return {}
            else:
                body = await resp.text()
                logger.error(f"Failed to get tunnel config: {resp.status} {body}")
                return {}

    async def report_backup_state(self, operation_id: str, state: str, **details) -> dict:
        """Report a safe managed-backup state transition."""
        payload = {"operation_id": operation_id, "state": state,
                   "automatic_enabled": bool(self.config.backup_enabled), **details}
        async with self.session.post("/api/backups/state", json=payload) as resp:
            if resp.status in (200, 201):
                return await resp.json()
            body = await resp.text()
            logger.error("Backup state report rejected: HTTP %s %s", resp.status, body[:200])
            return {"error": f"HTTP {resp.status}"}

    async def get_backup_config(self) -> dict:
        """Fetch effective backup upload limits from the platform."""
        async with self.session.get("/api/backups/config") as resp:
            if resp.status == 200:
                return await resp.json()
            body = await resp.text()
            logger.error("Failed to get backup config: HTTP %s %s", resp.status, body[:200])
            return {"error": f"HTTP {resp.status}"}

    async def upload_backup_file(
        self,
        path: str,
        filename: str,
        size_bytes: int,
        checksum_sha256: str,
        timeout_seconds: int = 1800,
    ) -> dict:
        """Stream one backup archive to the platform direct upload receiver."""
        headers = {
            "Content-Type": "application/octet-stream",
            "X-Backup-Filename": filename,
            "X-Backup-Size": str(size_bytes),
            "X-Backup-Sha256": checksum_sha256,
        }
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        try:
            with open(path, "rb") as f:
                async with self.session.post(
                    "/api/backups/upload/direct",
                    data=f,
                    headers=headers,
                    timeout=timeout,
                ) as resp:
                    body = await resp.text()
                    if resp.status in (200, 201):
                        return await resp.json(content_type=None)
                    logger.error("Backup upload rejected: HTTP %s %s", resp.status, body[:200])
                    return {"error": f"HTTP {resp.status}", "body": body[:200]}
        except Exception as e:
            logger.error("Backup upload failed: %s", type(e).__name__)
            return {"error": f"{type(e).__name__}: {str(e)[:150]}"}
