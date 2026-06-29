"""Home Assistant REST API client."""
import asyncio
import aiohttp
import shutil
from typing import Any
from datetime import datetime, timezone

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
        if not self.session:
            return {"error": "No session"}
        try:
            async with self.session.get(path) as resp:
                if resp.status == 200:
                    return await resp.json()
                body = await resp.text()
                return {"error": f"HTTP {resp.status}: {body[:200]}"}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {str(e)[:150]}"}
    
    async def _get_raw(self, path: str) -> dict[str, Any]:
        """GET raw (alias for _get)."""
        return await self._get(path)

    async def get_config(self) -> dict:
        return await self._get("/api/config")

    async def get_states(self) -> list[dict]:
        result = await self._get("/api/states")
        if isinstance(result, list):
            return result
        return []

    async def get_supervisor_info(self) -> dict:
        """Get supervisor info including addons list.
        Uses supervisor API directly with supervisor token."""
        import logging as _log_sup
        _log_sup = _log_sup.getLogger("burghscape.agent")
        try:
            import os
            supervisor_token = os.environ.get("SUPERVISOR_TOKEN", "")
            if not supervisor_token:
                token_path = "/run/s6/container_environment/SUPERVISOR_TOKEN"
                if os.path.isfile(token_path):
                    with open(token_path) as f:
                        supervisor_token = f.read().strip()
            
            if not supervisor_token:
                return {"error": "No supervisor token available"}
            
            # With host_network:true, supervisor API is typically unreachable (HAOS security)
            # These are low-priority since we fall back to entity-based detection
            supervisor_urls = [
                "http://172.30.32.2/api/supervisor/info",
                "http://supervisor/api/supervisor/info",
                "http://hassio/api/supervisor/info",
            ]
            async with aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {supervisor_token}"},
                timeout=aiohttp.ClientTimeout(total=5),
            ) as sup_session:
                for url in supervisor_urls:
                    try:
                        async with sup_session.get(url) as resp:
                            if resp.status == 200:
                                return await resp.json()
                    except Exception:
                        continue
                return {"error": "Supervisor API unavailable (host_network mode)"}
        except Exception as e:
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
        return [s.get("entity_id", "").replace("update.", "").replace("_", " ").title() for s in states if s.get("entity_id", "").startswith("update.") and s.get("state") == "on"]

    def get_system_stats(self) -> dict:
        """Collect CPU and memory usage from /proc (works with host_network:true)."""
        stats = {}
        try:
            # CPU usage from /proc/stat
            with open("/proc/stat") as f:
                line = f.readline()
                fields = line.split()
                if fields[0] == "cpu":
                    values = [int(x) for x in fields[1:]]
                    idle = values[3]
                    total = sum(values)
                    usage = ((total - idle) / total) * 100 if total > 0 else 0
                    stats["cpu_usage_percent"] = round(usage, 1)
        except Exception:
            pass

        try:
            # Memory from /proc/meminfo
            mem_info = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(":")
                        val = int(parts[1])
                        mem_info[key] = val
            total_kb = mem_info.get("MemTotal", 0)
            available_kb = mem_info.get("MemAvailable", 0)
            used_kb = total_kb - available_kb
            if total_kb > 0:
                stats["memory_total_gb"] = round(total_kb / (1024**2), 2)
                stats["memory_used_gb"] = round(used_kb / (1024**2), 2)
                stats["memory_usage_percent"] = round((used_kb / total_kb) * 100, 1)
        except Exception:
            pass

        return stats

    async def _try_supervisor_core_api(self) -> bool:
        """Try to set up HA API via supervisor core proxy using SUPERVISOR_TOKEN."""
        import os
        supervisor_token = os.environ.get("SUPERVISOR_TOKEN", "")
        if not supervisor_token:
            token_path = "/run/s6/container_environment/SUPERVISOR_TOKEN"
            if os.path.isfile(token_path):
                with open(token_path) as f:
                    supervisor_token = f.read().strip()
        if not supervisor_token:
            return False

        import logging as _logging2
        _log2 = _logging2.getLogger("burghscape.agent")

        # Try supervisor core API proxy URLs + localhost:8123 with supervisor token
        # NOTE: aiohttp requires trailing '/' on base_url
        # With host_network:true, supervisor hostname may not resolve but IP should work
        supervisor_core_urls = [
            "http://172.30.32.2/core/",
            "http://172.30.32.2:4358/core/",
            "http://supervisor/core/",
            "http://localhost:8123/",
            "http://127.0.0.1:8123/",
        ]
        for base in supervisor_core_urls:
            try:
                async with aiohttp.ClientSession(
                    base_url=base,
                    headers={"Authorization": f"Bearer {supervisor_token}"},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as test_sess:
                    async with test_sess.get("/api/config") as resp:
                        if resp.status == 200:
                            _log2.info("Supervisor fallback connected via %s", base)
                            if self.session:
                                await self.session.close()
                            self.session = aiohttp.ClientSession(
                                base_url=base,
                                headers={"Authorization": f"Bearer {supervisor_token}"},
                                timeout=aiohttp.ClientTimeout(total=15),
                            )
                            return True
                        else:
                            _log2.warning("Supervisor fallback %s → HTTP %d", base, resp.status)
            except Exception as e:
                _log2.warning("Supervisor fallback %s → %s: %s", base, type(e).__name__, str(e)[:100])
                continue
        return False

    async def get_full_report(self) -> dict:
        """Compile a full monitoring report with all required fields."""
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
            "disk_total_gb": 0,
            "disk_used_gb": 0,
            "cpu_usage_percent": 0,
            "memory_usage_percent": 0,
            "memory_total_gb": 0,
            "memory_used_gb": 0,
            "uptime_seconds": 0,
            "addons": [],
            "integrations": [],
            "cloudflare_tunnel_token": self.config.cloudflare_tunnel_token,
        }

        try:
            # Try primary HA connection first
            config_data = await self.get_config()
            states = await self.get_states()
            
            # If primary failed (401/connection error), try supervisor core API fallback
            if isinstance(config_data, dict) and "error" in config_data:
                import logging as _logging
                _log = _logging.getLogger("burghscape.agent")
                _log.info("Primary HA API failed: %s, trying supervisor fallback...", config_data.get("error"))
                if await self._try_supervisor_core_api():
                    _log.info("Supervisor fallback succeeded, retrying...")
                    config_data = await self.get_config()
                    states = await self.get_states()
                else:
                    _log.warning("Supervisor fallback also failed")
            
            # Only mark online if API actually responded (not an error dict)
            if isinstance(config_data, dict) and "error" not in config_data:
                report["online"] = True
            else:
                report["error"] = config_data.get("error", "HA API unreachable") if isinstance(config_data, dict) else str(config_data)
            report["ha_version"] = config_data.get("version", "unknown") if isinstance(config_data, dict) else "unknown"

            if self.config.monitor_entities and isinstance(states, list):
                report["entities_count"] = len(states)
                report["domains"] = self.count_by_domain(states)

            if self.config.monitor_automations and isinstance(states, list):
                automations = [s for s in states if s.get("entity_id", "").startswith("automation.")]
                report["automations_count"] = len(automations)
                report["automations_on"] = sum(
                    1 for a in automations if a.get("state") == "on"
                )

            if self.config.monitor_updates and isinstance(states, list):
                report["updates_available"] = self.count_update_entities(states)

            if self.config.monitor_disk:
                try:
                    u = shutil.disk_usage("/")
                    report["disk_usage_percent"] = round((u.used / u.total) * 100, 1)
                    report["disk_total_gb"] = round(u.total / (1024**3), 2)
                    report["disk_used_gb"] = round(u.used / (1024**3), 2)
                except Exception:
                    pass

            # CPU and memory from /proc (requires host_network:true)
            sys_stats = self.get_system_stats()
            report.update(sys_stats)

            if isinstance(config_data, dict):
                report["ha_state"] = config_data.get("state")
                report["location"] = config_data.get("location_name")
                report["timezone"] = config_data.get("time_zone")
                report["components"] = len(config_data.get("components", []))

            # Get integrations from config components
            report["integrations"] = config_data.get("components", []) if isinstance(config_data, dict) else []

            # Get addons from supervisor API (or HA hassio API as fallback)
            supervisor_info = await self.get_supervisor_info()
            try:
                if "data" in supervisor_info:
                    supervisor_data = supervisor_info["data"]
                    supervisor_version = supervisor_data.get("supervisor", "unknown")
                    report["ha_version"] = config_data.get("version", supervisor_version) if isinstance(config_data, dict) else supervisor_version
                    
                    # Addons list
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
                    
                    # Uptime from supervisor
                    report["uptime_seconds"] = supervisor_data.get("seconds_on", 0)

                    # Disk info from supervisor
                    if self.config.monitor_disk:
                        disk_free = supervisor_data.get("disk_free", 0)
                        disk_total = supervisor_data.get("disk_total", 0)
                        disk_used = supervisor_data.get("disk_used", 0)
                        if disk_total > 0:
                            report["disk_usage_percent"] = round((disk_used / disk_total) * 100, 1)
                            report["disk_total_gb"] = round(disk_total, 2)
                            report["disk_used_gb"] = round(disk_used, 2)
                elif "error" in supervisor_info:
                    # Fallback: derive addons from HA update.* entities
                    import logging as _log_addons
                    _log_addons = _log_addons.getLogger("burghscape.agent")
                    _log_addons.info("Supervisor API failed (%s), using entity fallback for addons", supervisor_info.get("error"))
                    if isinstance(states, list):
                        # update.* entities represent installed addons with update status
                        # Filter out system components (supervisor, core, os) - only keep real add-ons
                        _system_slugs = {"home_assistant_supervisor", "home_assistant_core",
                                         "home_assistant_operating_system", "caos"}
                        addon_entities = [
                            s for s in states
                            if s.get("entity_id", "").startswith("update.")
                            and s.get("entity_id", "").replace("update.", "").replace("_update", "") not in _system_slugs
                        ]
                        report["addons"] = [
                            {
                                "name": s.get("entity_id", "").replace("update.", "").replace("_update", "").replace("_", " ").title(),
                                "slug": s.get("entity_id", "").replace("update.", "").replace("_update", ""),
                                "version": s.get("attributes", {}).get("installed_version", ""),
                                "update_available": s.get("state") == "on",
                                "state": "started" if s.get("attributes", {}).get("state") == "started" else "unknown",
                            }
                            for s in addon_entities
                            if isinstance(s, dict)
                        ]
                        # Add this agent itself (it won't appear in update.* entities)
                        report["addons"].append({
                            "name": "Burghscape Agent",
                            "slug": "burghscape_agent",
                            "version": self.config.burghscape_version or "",
                            "update_available": False,
                            "state": "started",
                        })
                    # Also try HA hassio API via localhost with HA token
                    if not report["addons"]:
                        hassio_addons = await self._get("/api/hassio/addons")
                        if isinstance(hassio_addons, dict) and "data" in hassio_addons:
                            addons_list = hassio_addons["data"].get("addons", [])
                            report["addons"] = [
                                {
                                    "name": a.get("name", "Unknown"),
                                    "slug": a.get("slug", ""),
                                    "version": a.get("version", ""),
                                    "update_available": a.get("update_available", False),
                                    "state": a.get("state", "unknown"),
                                }
                                for a in addons_list
                                if isinstance(a, dict)
                            ]
            except Exception:
                pass  # Supervisor API might not be available

        except Exception as e:
            report["error"] = str(e)

        return report
