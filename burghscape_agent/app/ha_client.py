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
            headers={"Authorization": f"Bearer {self.config.ha_token}", "X-Forwarded-For": "127.0.0.1"},
            timeout=aiohttp.ClientTimeout(total=15),
        )
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def _get(self, path: str) -> dict[str, Any]:
        async with self.session.get(path) as resp:
            if resp.status == 200:
                return await resp.json()
            return {"error": f"HTTP {resp.status}"}
    
    async def get_config(self) -> dict:
        return await self._get("/api/config")
    
    async def get_status(self) -> dict:
        return await self._get("/api/")
    
    async def get_states(self) -> list[dict]:
        return await self._get("/api/states")
    
    async def get_states_domain(self, domain: str) -> list[dict]:
        return await self._get(f"/api/states/{domain}")
    
    async def get_automations(self) -> list[dict]:
        states = await self.get_states()
        return [s for s in states if s.get("entity_id", "").startswith("automation.")]
    
    async def get_entity(self, entity_id: str) -> dict:
        return await self._get(f"/api/states/{entity_id}")
    
    async def get_discovery_info(self) -> dict:
        return await self._get("/api/discovery_info")
    
    async def ping(self) -> bool:
        try:
            result = await self._get("/")
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
        """Compile a full monitoring report."""
        report = {
            "instance_name": self.config.instance_name,
            "ip_address": self.config.ip_address,
            "timestamp": None,
            "online": False,
            "error": None,
            "cloudflare_tunnel_token": self.config.cloudflare_tunnel_token,
        }
        
        try:
            config_data = await self.get_config()
            states = await self.get_states()
            
            from datetime import datetime, timezone
            report["timestamp"] = datetime.now(timezone.utc).isoformat()
            report["online"] = True
            
            if self.config.monitor_disk:
                import shutil
                try:
                    u = shutil.disk_usage("/")
                    report["disk_usage_percent"] = round((u.used / u.total) * 100, 1)
                except Exception:
                    report["disk_usage_percent"] = None
            
            if self.config.monitor_entities:
                report["entities_count"] = len(states)
                report["domains"] = self.count_by_domain(states)
            
            if self.config.monitor_automations:
                automations = await self.get_automations()
                report["automations_count"] = len(automations)
                report["automations_on"] = sum(
                    1 for a in automations if a.get("state") == "on"
                )
            
            if self.config.monitor_updates:
                report["updates_available"] = self.count_update_entities(states)
            
            report["ha_version"] = config_data.get("version")
            report["ha_state"] = config_data.get("state")
            report["location"] = config_data.get("location_name")
            report["timezone"] = config_data.get("time_zone")
            report["components"] = len(config_data.get("components", []))
            integrations = config_data.get("integrations", [])
            report["integrations"] = integrations if isinstance(integrations, list) else []
            
        except Exception as e:
            report["error"] = str(e)
        
        return report
