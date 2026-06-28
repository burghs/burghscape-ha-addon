"""Home Assistant REST API client."""
import asyncio
import aiohttp
import shutil
import logging
import os
from typing import Any
from datetime import datetime, timezone

from app.config import Config

logger = logging.getLogger("burghscape.agent")


class HAClient:
    def __init__(self, config: Config):
        self.config = config
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            base_url=self.config.ha_url,
            headers={"Authorization": f"Bearer {self.config.ha_token}"},
            timeout=aiohttp.ClientTimeout(total=15),
        )
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def _get(self, path: str) -> dict[str, Any]:
        if not self.session:
            return {"error": "No session"}
        try:
            async with self.session.get(path) as resp:
                if resp.status == 200:
                    return await resp.json()
                body = await resp.text()
                logger.warning(f"HA API {path} returned HTTP {resp.status}: {body[:100]}")
                return {"error": f"HTTP {resp.status}"}
        except Exception as e:
            logger.error(f"HA API {path} exception: {e}")
            return {"error": str(e)}

    async def get_config(self) -> dict:
        return await self._get("/api/config")

    async def get_states(self) -> list[dict]:
        result = await self._get("/api/states")
        if isinstance(result, list):
            return result
        return []

    async def get_supervisor_info(self) -> dict:
        """Get supervisor info including addons list."""
        try:
            supervisor_token = os.environ.get("SUPERVISOR_TOKEN", "")
            if not supervisor_token:
                token_path = "/run/s6/container_environment/SUPERVISOR_TOKEN"
                if os.path.isfile(token_path):
                    with open(token_path) as f:
                        supervisor_token = f.read().strip()

            if not supervisor_token:
                logger.warning("No supervisor token for supervisor API")
                return {"error": "No supervisor token"}

            async with aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {supervisor_token}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as sup_session:
                async with sup_session.get("http://supervisor/api/supervisor/info") as resp:
                    if resp.status == 200:
                        return await resp.json()
                    body = await resp.text()
                    logger.warning(f"Supervisor API HTTP {resp.status}: {body[:100]}")
                    return {"error": f"HTTP {resp.status}"}
        except Exception as e:
            logger.error(f"Supervisor API exception: {e}")
            return {"error": str(e)}

    async def ping(self) -> bool:
        try:
            result = await self._get("/api/")
            return "message" in result
        except Exception:
            return False

    def count_by_domain(self, states: list) -> dict[str, int]:
        domains: dict[str, int] = {}
        for s in states:
            d = s.get("entity_id", "").split(".")[0]
            domains[d] = domains.get(d, 0) + 1
        return dict(sorted(domains.items(), key=lambda x: -x[1]))

    def count_update_entities(self, states: list) -> list[str]:
        return [s.get("entity_id", "").replace("update.", "").replace("_", " ").title() for s in states if s.get("entity_id", "").startswith("update.")]

    async def get_full_report(self) -> dict:
        """Compile a full monitoring report with all required fields."""
        report = {
            "instance_name": self.config.instance_name,
            "ip_address": self.config.ip_address,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "online": False,
            "error": None,
            "ha_version": "unknown",
            "entities_count": 0,
            "automations_count": 0,
            "updates_available": [],
            "disk_usage_percent": 0,
            "disk_total_gb": 0,
            "disk_used_gb": 0,
            "uptime_seconds": 0,
            "addons": [],
            "integrations": [],
            "cloudflare_tunnel_token": self.config.cloudflare_tunnel_token,
        }

        try:
            config_data = await self.get_config()
            states = await self.get_states()

            report["online"] = True
            report["ha_version"] = config_data.get("version", "unknown")

            if self.config.monitor_entities:
                report["entities_count"] = len(states)
                report["domains"] = self.count_by_domain(states)

            if self.config.monitor_automations:
                automations = [s for s in states if s.get("entity_id", "").startswith("automation.")]
                report["automations_count"] = len(automations)
                report["automations_on"] = sum(
                    1 for a in automations if a.get("state") == "on"
                )

            if self.config.monitor_updates:
                report["updates_available"] = self.count_update_entities(states)

            if self.config.monitor_disk:
                try:
                    u = shutil.disk_usage("/")
                    report["disk_usage_percent"] = round((u.used / u.total) * 100, 1)
                    report["disk_total_gb"] = round(u.total / (1024**3), 2)
                    report["disk_used_gb"] = round(u.used / (1024**3), 2)
                except Exception:
                    pass

            report["ha_state"] = config_data.get("state")
            report["location"] = config_data.get("location_name")
            report["timezone"] = config_data.get("time_zone")
            report["components"] = len(config_data.get("components", []))
            report["integrations"] = config_data.get("components", [])

            # Get addons from supervisor API
            try:
                supervisor_info = await self.get_supervisor_info()
                if "data" in supervisor_info:
                    supervisor_data = supervisor_info["data"]
                    addons_list = supervisor_data.get("addons", [])
                    if isinstance(addons_list, list):
                        report["addons"] = [
                            {
                                "name": a.get("name", "Unknown"),
                                "slug": a.get("slug", ""),
                                "version": a.get("version", ""),
                                "update_available": a.get("version") != a.get("version_latest") if a.get("version_latest") else False,
                                "state": a.get("state", "unknown"),
                            }
                            for a in addons_list
                            if isinstance(a, dict)
                        ]
                    report["uptime_seconds"] = supervisor_data.get("seconds_on", 0)
                    if self.config.monitor_disk:
                        disk_total = supervisor_data.get("disk_total", 0)
                        disk_used = supervisor_data.get("disk_used", 0)
                        if disk_total > 0:
                            report["disk_usage_percent"] = round((disk_used / disk_total) * 100, 1)
                            report["disk_total_gb"] = round(disk_total, 2)
                            report["disk_used_gb"] = round(disk_used, 2)
            except Exception as e:
                logger.warning(f"Supervisor API failed: {e}")

        except Exception as e:
            report["error"] = str(e)
            logger.error(f"Error collecting HA report: {e}")

        return report
