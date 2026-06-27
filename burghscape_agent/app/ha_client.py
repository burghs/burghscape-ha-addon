"""Home Assistant REST API client."""
import asyncio
import aiohttp
from typing import Any

from app.config import Config


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
        try:
            async with self.session.get(path) as resp:
                if resp.status == 200:
                    return await resp.json()
                return {"error": f"HTTP {resp.status}"}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_config(self) -> dict:
        return await self._get("/api/config")
    
    async def get_states(self) -> list[dict]:
        result = await self._get("/api/states")
        if isinstance(result, list):
            return result
        return []
    
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
        from datetime import datetime, timezone
        
        # Always include required fields (even when offline)
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
                import shutil
                try:
                    u = shutil.disk_usage("/")
                    report["disk_usage_percent"] = round((u.used / u.total) * 100, 1)
                except Exception:
                    pass
            
            report["ha_state"] = config_data.get("state")
            report["location"] = config_data.get("location_name")
            report["timezone"] = config_data.get("time_zone")
            report["components"] = len(config_data.get("components", []))
            
        except Exception as e:
            report["error"] = str(e)
        
        return report
