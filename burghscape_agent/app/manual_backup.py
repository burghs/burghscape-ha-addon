"""Manual managed backup command for one deliberate end-to-end backup run."""
import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp

from app.config import Config
from app.platform_client import PlatformClient

logger = logging.getLogger("burghscape.agent.backup")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

SUPERVISOR_URLS = ("http://supervisor", "http://172.30.32.2")
CREATE_TIMEOUT_SECONDS = 1800
POLL_INTERVAL_SECONDS = 10
UPLOAD_TIMEOUT_SECONDS = 1800


def get_supervisor_token() -> str:
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if token:
        return token
    token_path = "/run/s6/container_environment/SUPERVISOR_TOKEN"
    try:
        if os.path.isfile(token_path):
            with open(token_path) as f:
                return f.read().strip()
    except Exception as exc:
        logger.warning("Could not read Supervisor token: %s", type(exc).__name__)
    return ""


def unwrap_supervisor_payload(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def extract_backups(payload: Any) -> list[dict]:
    data = unwrap_supervisor_payload(payload)
    if isinstance(data, dict):
        backups = data.get("backups", [])
    elif isinstance(data, list):
        backups = data
    else:
        backups = []
    return [item for item in backups if isinstance(item, dict) and item.get("slug")]


def safe_backup_filename(slug: str) -> str:
    safe_slug = re.sub(r"[^A-Za-z0-9._-]+", "_", slug).strip("._") or "home_assistant_backup"
    return f"burghscape-managed-backup-{safe_slug}.tar"


class SupervisorApiError(RuntimeError):
    def __init__(self, method: str, path: str, status: int, category: str):
        self.method = method
        self.path = path
        self.status = status
        self.category = category
        super().__init__(f"Supervisor {method} {path} failed with HTTP {status}: {category}")


async def response_preview(resp, limit: int = 120) -> str:
    try:
        body = await resp.text()
    except Exception:
        return ""
    return " ".join((body or "").split())[:limit]


def raise_supervisor_http_error(method: str, path: str, status: int, preview: str = ""):
    if status == 403:
        logger.error(
            "Supervisor rejected add-on role for backup API: method=%s path=%s status=403",
            method,
            path,
        )
        raise SupervisorApiError(method, path, status, "supervisor_role_rejected")
    if status == 401:
        logger.error("Supervisor rejected backup API authentication: method=%s path=%s status=401", method, path)
        raise SupervisorApiError(method, path, status, "supervisor_authentication_rejected")
    logger.warning(
        "Supervisor backup API request failed: method=%s path=%s status=%s response_preview=%s",
        method,
        path,
        status,
        preview,
    )
    raise SupervisorApiError(method, path, status, "supervisor_http_error")


class SupervisorBackupClient:
    def __init__(self, token: str, session: aiohttp.ClientSession | None = None):
        self.token = token
        self.base_url = ""
        self.session = session
        self._owns_session = session is None

    async def __aenter__(self):
        if self.session is None:
            headers = {"Authorization": f"Bearer {self.token}"}
            self.session = aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=60))
            self._owns_session = True
        try:
            await self._select_base_url()
        except Exception:
            await self.close()
            raise
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def close(self):
        if self.session and self._owns_session:
            await self.session.close()
        if self._owns_session:
            self.session = None

    def _require_session(self) -> aiohttp.ClientSession:
        if self.session is None:
            raise RuntimeError("Supervisor API session is not initialized")
        return self.session

    async def _select_base_url(self):
        session = self._require_session()
        last_error = None
        for base in SUPERVISOR_URLS:
            try:
                async with session.get(f"{base}/backups", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        self.base_url = base
                        logger.info("Supervisor backup API selected: %s", base)
                        return
                    if resp.status in (401, 403):
                        try:
                            raise_supervisor_http_error("GET", "/backups", resp.status)
                        except SupervisorApiError as exc:
                            last_error = exc
                        continue
                    preview = await response_preview(resp)
                    logger.warning(
                        "Supervisor backup API base URL rejected: base=%s status=%s response_preview=%s",
                        base,
                        resp.status,
                        preview,
                    )
            except SupervisorApiError:
                raise
            except Exception as exc:
                logger.warning("Supervisor backup API %s unavailable: %s", base, type(exc).__name__)
        if last_error:
            raise last_error
        raise RuntimeError("Supervisor backup API unavailable")

    async def _json(self, method: str, path: str, **kwargs) -> dict:
        session = self._require_session()
        async with session.request(method, f"{self.base_url}{path}", **kwargs) as resp:
            if resp.status not in (200, 201, 202):
                preview = await response_preview(resp)
                raise_supervisor_http_error(method, path, resp.status, preview)
            body = await resp.text()
            if not body:
                return {}
            return json.loads(body)

    async def list_backups(self) -> list[dict]:
        try:
            return extract_backups(await self._json("GET", "/backups"))
        except SupervisorApiError as exc:
            if exc.status in (401, 403):
                raise
            return extract_backups(await self._json("GET", "/backups/info"))
        except Exception:
            return extract_backups(await self._json("GET", "/backups/info"))

    async def create_full_backup(self, name: str) -> dict:
        payload = {
            "name": name,
            "compressed": True,
            "location": None,
            "background": True,
        }
        return unwrap_supervisor_payload(await self._json("POST", "/backups/new/full", json=payload)) or {}

    async def get_job(self, job_id: str) -> dict:
        return unwrap_supervisor_payload(await self._json("GET", f"/jobs/{job_id}")) or {}

    async def wait_for_new_backup(self, before_slugs: set[str], expected_name: str, create_response: dict) -> dict:
        deadline = time.time() + CREATE_TIMEOUT_SECONDS
        response_slug = create_response.get("slug") if isinstance(create_response, dict) else None
        job_id = create_response.get("job_id") if isinstance(create_response, dict) else None
        while time.time() < deadline:
            if job_id:
                try:
                    job = await self.get_job(job_id)
                    logger.info(
                        "Backup creation job state: done=%s progress=%s stage=%s",
                        job.get("done"),
                        job.get("progress"),
                        job.get("stage"),
                    )
                    if isinstance(job.get("extra"), dict) and job["extra"].get("slug"):
                        response_slug = job["extra"]["slug"]
                except Exception as exc:
                    logger.warning("Could not read backup creation job: %s", type(exc).__name__)

            backups = await self.list_backups()
            by_slug = {b.get("slug"): b for b in backups}
            if response_slug and response_slug in by_slug and response_slug not in before_slugs:
                return by_slug[response_slug]
            candidates = [
                b for b in backups
                if b.get("slug") not in before_slugs and b.get("name") == expected_name
            ]
            if len(candidates) == 1:
                return candidates[0]
            if len(candidates) > 1:
                raise RuntimeError("More than one new backup matched the requested name")
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        raise TimeoutError("Timed out waiting for Home Assistant backup creation")

    async def download_backup(self, slug: str, destination: Path) -> tuple[int, str]:
        hasher = hashlib.sha256()
        size = 0
        session = self._require_session()
        async with session.get(f"{self.base_url}/backups/{slug}/download", timeout=aiohttp.ClientTimeout(total=UPLOAD_TIMEOUT_SECONDS)) as resp:
            if resp.status != 200:
                preview = await response_preview(resp)
                raise_supervisor_http_error("GET", "/backups/{slug}/download", resp.status, preview)
            with open(destination, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    hasher.update(chunk)
                    f.write(chunk)
        return size, hasher.hexdigest()


async def run_manual_backup() -> dict:
    config = Config()
    token = get_supervisor_token()
    if not token:
        raise RuntimeError("SUPERVISOR_TOKEN is unavailable")

    states = []
    name = "Burghscape Managed Backup " + datetime.now().strftime("%Y-%m-%d %H-%M")
    operation_started = time.time()
    async with SupervisorBackupClient(token) as supervisor, PlatformClient(config) as platform:
        states.append("requested")
        backup_config = await platform.get_backup_config()
        if backup_config.get("error"):
            raise RuntimeError("Platform backup config request failed")
        max_backup_size = int(backup_config.get("max_backup_size_bytes") or 0)
        before = await supervisor.list_backups()
        before_slugs = {b.get("slug") for b in before if b.get("slug")}

        states.append("creating")
        create_response = await supervisor.create_full_backup(name)
        created = await supervisor.wait_for_new_backup(before_slugs, name, create_response)
        slug = created.get("slug")
        if not slug:
            raise RuntimeError("Created backup has no slug")
        states.append("created")

        filename = safe_backup_filename(slug)
        temp_dir = Path("/data/managed-backup")
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / f".{filename}.download"
        if temp_path.exists():
            temp_path.unlink()

        download_started = time.time()
        size_bytes, checksum = await supervisor.download_backup(slug, temp_path)
        if size_bytes <= 0:
            raise RuntimeError("Downloaded backup archive is empty")
        if max_backup_size and size_bytes > max_backup_size:
            raise RuntimeError("Downloaded backup exceeds platform maximum size")

        states.append("uploading")
        upload_started = time.time()
        upload_result = await platform.upload_backup_file(
            str(temp_path),
            filename,
            size_bytes,
            checksum,
            timeout_seconds=UPLOAD_TIMEOUT_SECONDS,
        )
        if upload_result.get("error"):
            raise RuntimeError(f"Platform upload failed: {upload_result.get('error')}")
        states.append("completed")

        try:
            temp_path.unlink()
        except OSError:
            pass

        result = {
            "state": states[-1],
            "states": states,
            "ha_backup_slug": slug,
            "filename": filename,
            "size_bytes": size_bytes,
            "sha256": checksum,
            "backup_id": upload_result.get("backup_id"),
            "storage_key": upload_result.get("key"),
            "creation_duration_seconds": round(download_started - operation_started, 1),
            "upload_duration_seconds": round(time.time() - upload_started, 1),
            "upload_result": upload_result,
        }
        logger.info(
            "Manual managed backup completed slug=%s backup_id=%s bytes=%s",
            slug,
            upload_result.get("backup_id"),
            size_bytes,
        )
        return result


def main():
    parser = argparse.ArgumentParser(description="Run one manual Burghscape managed Home Assistant backup")
    parser.add_argument("--json", action="store_true", help="Print machine-readable result JSON")
    args = parser.parse_args()
    try:
        result = asyncio.run(run_manual_backup())
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            print(f"completed backup_id={result.get('backup_id')} size_bytes={result.get('size_bytes')}")
    except Exception as exc:
        logger.error("Manual managed backup failed: %s", exc)
        if args.json:
            print(json.dumps({"state": "failed", "error": str(exc)[:200]}, sort_keys=True))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
