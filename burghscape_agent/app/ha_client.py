"""Home Assistant REST API client."""
import asyncio
import aiohttp
import shutil
import os
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

    async def _get_supervisor_backup_inventory(self) -> dict | None:
        """Read supported non-secret backup inventory directly from Supervisor."""
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        token_path = "/run/s6/container_environment/SUPERVISOR_TOKEN"
        if not token and os.path.isfile(token_path):
            with open(token_path) as token_file:
                token = token_file.read().strip()
        if not token:
            return None
        headers = {"Authorization": f"Bearer {token}"}
        async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as session:
            for base_url in ("http://supervisor", "http://172.30.32.2"):
                try:
                    async with session.get(f"{base_url}/backups") as response:
                        if response.status != 200:
                            continue
                        payload = await response.json()
                        data = payload.get("data", payload) if isinstance(payload, dict) else payload
                        items = data.get("backups", []) if isinstance(data, dict) else data
                        return self._parse_backup_list(items)
                except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                    continue
        return None

    async def _get_ha_backup_api(self) -> dict:
        """Check HA backup status via filesystem (/backup/ dir) with API fallback.
        
        Primary: list files in /backup/ directory (most reliable, no auth needed).
        Fallback: try /api/hassio/backups via HA API proxy.
        """
        backup = {
            "enabled": False,
            "last_backup": None,
            "status": "unknown",
            "file_count": 0,
            "total_size_bytes": 0,
            "last_backup_timestamp": None,
            "next_backup": None,
            "error": None,
            "native_automatic_enabled": None,
            "last_native_automatic_backup": None,
            "next_native_automatic_backup": None,
            "backup_types": [],
            "encryption_enabled": None,
        }
        
        supervisor_inventory = await self._get_supervisor_backup_inventory()
        if supervisor_inventory is not None:
            return supervisor_inventory

        # --- Method 1: Filesystem fallback ---
        try:
            import os, glob, time
            backup_dir = "/backup"
            if os.path.isdir(backup_dir):
                tar_files = sorted(
                    [f for f in glob.glob(os.path.join(backup_dir, "*.tar")) if os.path.isfile(f)],
                    key=os.path.getmtime,
                    reverse=True
                )
                if tar_files:
                    backup["enabled"] = True
                    backup["file_count"] = len(tar_files)
                    total_size = sum(os.path.getsize(f) for f in tar_files)
                    backup["total_size_bytes"] = total_size
                    
                    # Most recent backup
                    latest = tar_files[0]
                    mtime = os.path.getmtime(latest)
                    now = time.time()
                    delta_secs = now - mtime
                    
                    if delta_secs < 60:
                        backup["last_backup"] = "Just now"
                    elif delta_secs < 3600:
                        backup["last_backup"] = f"{int(delta_secs // 60)}m ago"
                    elif delta_secs < 86400:
                        backup["last_backup"] = f"{int(delta_secs // 3600)}h ago"
                    elif delta_secs < 604800:
                        backup["last_backup"] = f"{int(delta_secs // 86400)}d ago"
                    else:
                        import datetime
                        dt = datetime.datetime.fromtimestamp(mtime)
                        backup["last_backup"] = dt.strftime("%Y-%m-%d")
                    
                    backup["last_backup_timestamp"] = mtime
                    backup["status"] = "ok"
                    
                    import logging as _log
                    _log = _log.getLogger("burghscape.agent")
                    _log.info("Backup: found %d tar files in %s, latest %s", len(tar_files), backup_dir, backup["last_backup"])
                    return backup
            else:
                backup["error"] = f"Backup directory {backup_dir} not found"
        except Exception as e:
            import logging as _log
            _log = _log.getLogger("burghscape.agent")
            _log.warning("Backup filesystem check failed: %s", e)
            backup["error"] = f"FS error: {e}"
        
        # --- Method 2: Hassio API proxy fallback ---
        if self.session:
            try:
                async with self.session.get("/api/hassio/backups") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        inner = data
                        if isinstance(data, dict) and "data" in data:
                            inner = data["data"]
                        backups_list = inner.get("backups", []) if isinstance(inner, dict) else (inner if isinstance(inner, list) else [])
                        
                        if backups_list:
                            backup["enabled"] = True
                            backup["status"] = "ok"
                            import logging as _log2
                            _log2 = _log2.getLogger("burghscape.agent")
                            _log2.info("Backup: found %d backups via hassio API", len(backups_list))
                            return self._parse_backup_list(backups_list)
            except Exception:
                pass
        
        # --- Method 3: Try raw API endpoint (old HA versions) ---
        if self.session:
            try:
                async with self.session.get("/api/backups") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, list) and len(data) > 0:
                            backup["enabled"] = True
                            return self._parse_backup_list(data)
            except Exception:
                pass
        
        return backup

    def _parse_backup_list(self, backups_list: list) -> dict:
        """Parse a list of backup dicts into the standard backup telemetry shape."""
        backup = {
            "enabled": False,
            "last_backup": None,
            "status": "unknown",
            "file_count": 0,
            "total_size_bytes": 0,
            "last_backup_timestamp": None,
            "next_backup": None,
            "error": None,
            "native_automatic_enabled": None,
            "last_native_automatic_backup": None,
            "next_native_automatic_backup": None,
            "backup_types": [],
            "encryption_enabled": None,
        }
        from datetime import datetime

        if not isinstance(backups_list, list) or not backups_list:
            return backup

        normalized = [b for b in backups_list if isinstance(b, dict)]
        if not normalized:
            backup["error"] = "No valid backup entries returned"
            return backup

        backup["enabled"] = True
        backup["status"] = "ok"
        backup["file_count"] = len(normalized)
        backup["backup_types"] = sorted({str(item.get("type")) for item in normalized if item.get("type") in ("full", "partial")})

        total = 0
        for item in normalized:
            try:
                size = int(float(item.get("size", 0) or 0))
                if size > 0:
                    total += size
            except (ValueError, TypeError):
                continue
        backup["total_size_bytes"] = total

        sorted_bk = sorted(normalized, key=lambda b: str(b.get("date") or b.get("created_at") or ""), reverse=True)
        latest = sorted_bk[0]
        backup_date = latest.get("date") or latest.get("created_at") or latest.get("last_modified")
        if backup_date:
            backup["last_backup_timestamp"] = backup_date
            try:
                dt = datetime.fromisoformat(str(backup_date).replace("Z", "+00:00"))
                delta = datetime.now().astimezone() - dt
                if delta.days > 0:
                    backup["last_backup"] = f"{delta.days}d ago"
                elif delta.seconds > 3600:
                    backup["last_backup"] = f"{delta.seconds // 3600}h ago"
                else:
                    backup["last_backup"] = f"{delta.seconds // 60}m ago"
            except (ValueError, TypeError):
                backup["last_backup"] = str(backup_date)[:19]

        return backup
    def get_backup_status(self, states: list) -> dict:
        """Extract OneDrive backup status from HA sensors (lavinir/hassio-onedrive-backup add-on)."""
        backup = {
            "enabled": False,
            "last_backup": None,
            "status": "unknown",
            "file_count": 0,
            "total_size_bytes": 0,
            "last_backup_timestamp": None,
            "next_backup": None,
            "error": None,
            "native_automatic_enabled": None,
            "last_native_automatic_backup": None,
            "next_native_automatic_backup": None,
            "backup_types": [],
            "encryption_enabled": None,
        }
        
        # Look for onedrive backup sensors
        onedrive_sensors = [
            s for s in states
            if "onedrive" in s.get("entity_id", "").lower()
            or "backup" in s.get("entity_id", "").lower()
        ]
        
        if not onedrive_sensors:
            return backup
        
        backup["enabled"] = True
        
        for sensor in onedrive_sensors:
            entity_id = sensor.get("entity_id", "")
            state = sensor.get("state", "")
            attrs = sensor.get("attributes", {})
            
            # Last backup time
            if "last_backup" in entity_id and "timestamp" not in entity_id:
                backup["last_backup"] = state
                backup["last_backup_timestamp"] = attrs.get("last_backup") or state
            
            # Backup status/state
            if entity_id.endswith("_status") or entity_id.endswith("_state"):
                backup["status"] = state
            
            # File count
            if "file" in entity_id and "count" in entity_id:
                try:
                    backup["file_count"] = int(float(state))
                except (ValueError, TypeError):
                    pass
            
            # Size
            if "size" in entity_id:
                try:
                    backup["total_size_bytes"] = int(float(state))
                except (ValueError, TypeError):
                    pass
            
            # Timestamp variant
            if "last_backup_timestamp" in entity_id:
                backup["last_backup_timestamp"] = state
            
            # Next backup
            if "next_backup" in entity_id:
                backup["next_backup"] = state
            
            # Error/problem
            if "problem" in entity_id and state == "on":
                backup["error"] = "Backup problem detected"
        
        # If we found onedrive sensors but no explicit status, infer from last_backup
        if backup["status"] == "unknown" and backup["last_backup"]:
            backup["status"] = "ok"
        
        return backup

    def get_system_stats(self) -> dict:
        """Collect CPU and memory usage from /proc (works with host_network:true)."""
        stats = {
            "cpu_usage_percent": 0,
            "memory_total_gb": 0,
            "memory_used_gb": 0,
            "memory_usage_percent": 0,
            "disk_total_gb": 0,
            "disk_used_gb": 0,
            "disk_usage_percent": 0,
        }
        try:
            # CPU usage from /proc/stat
            if os.path.exists("/proc/stat"):
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
            if os.path.exists("/proc/meminfo"):
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

        try:
            # Disk usage for HA data partitions (/config and /backup are best indicators)
            # In HAOS add-ons, these are mounted from the host
            for path in ["/config", "/backup", "/data", "/"]:
                if os.path.exists(path):
                    u = shutil.disk_usage(path)
                    if u.total > 0:
                        stats["disk_total_gb"] = round(u.total / (1024**3), 2)
                        stats["disk_used_gb"] = round(u.used / (1024**3), 2)
                        stats["disk_usage_percent"] = round((u.used / u.total) * 100, 1)
                        if path in ["/config", "/backup"]: # Prefer these
                            break
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
        # Amlways include required fields (even when offline)
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
            "backup": {
                "enabled": False,
                "last_backup": None,
                "status": "unknown",
                "file_count": 0,
                "total_size_bytes": 0,
                "last_backup_timestamp": None,
                "next_backup": None,
                "error": None,
            },
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

            # CPU, memory and disk from /proc and shutil (requires host_network:true)
            sys_stats = self.get_system_stats()
            report.update(sys_stats)

            # OneDrive backup status from HA sensors
            if isinstance(states, list):
                ha_backup = await self._get_ha_backup_api()
                if ha_backup.get("enabled"):
                    report["backup"] = ha_backup
                else:
                    fallback = self.get_backup_status(states)
                    if fallback.get("enabled"):
                        report["backup"] = fallback

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

                    # Disk info from supervisor (if provided)
                    if self.config.monitor_disk and supervisor_data.get("disk_total"):
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
