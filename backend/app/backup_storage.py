"""Backup storage capacity, aggregation, and safe managed-object path helpers."""
from datetime import datetime, timezone
from pathlib import Path
import glob
import os
import shutil

from config import get_settings


def storage_health(percent: float) -> str:
    if percent >= 95:
        return "critical"
    if percent >= 85:
        return "warning"
    if percent >= 70:
        return "attention"
    return "healthy"


def storage_roots() -> tuple[Path, Path]:
    settings = get_settings()
    return (
        Path(settings.BACKUP_LOCAL_PATH).resolve(),
        Path(settings.PLATFORM_BACKUP_LOCAL_PATH).resolve(),
    )


def safe_managed_path(storage_key: str, *, require_file: bool = True) -> Path:
    managed_root, _ = storage_roots()
    if not storage_key or Path(storage_key).is_absolute() or ".." in Path(storage_key).parts:
        raise ValueError("unsafe backup storage key")
    unresolved = managed_root / storage_key
    cursor = unresolved
    while cursor != managed_root:
        if cursor.is_symlink():
            raise ValueError("symbolic links are not permitted")
        cursor = cursor.parent
    target = unresolved.resolve(strict=False)
    target.relative_to(managed_root)
    if require_file and (not target.exists() or not target.is_file()):
        raise FileNotFoundError("backup archive is unavailable")
    if target.exists() and target.is_dir():
        raise ValueError("backup target is not a file")
    return target


def platform_backup_files() -> list[Path]:
    _, platform_root = storage_roots()
    return [Path(value) for value in glob.glob(str(platform_root / "*.tar.gz")) if Path(value).is_file()]


def filesystem_summary() -> dict:
    managed_root, platform_root = storage_roots()
    if not managed_root.is_dir() or not platform_root.is_dir():
        raise FileNotFoundError("configured backup storage is unavailable")
    managed_usage = shutil.disk_usage(managed_root)
    platform_usage = shutil.disk_usage(platform_root)
    shared = os.stat(managed_root).st_dev == os.stat(platform_root).st_dev

    def volume(path: Path, usage) -> dict:
        percent = (usage.used / usage.total * 100) if usage.total else 0.0
        return {
            "label": "Backup storage" if shared else path.name or "Backup storage",
            "capacity_bytes": usage.total,
            "used_bytes": usage.used,
            "available_bytes": usage.free,
            "usage_percent": round(percent, 1),
            "health": storage_health(percent),
        }

    volumes = [volume(managed_root, managed_usage)]
    if not shared:
        volumes.append(volume(platform_root, platform_usage))
    return {
        "available": True,
        "roots_shared": shared,
        "volumes": volumes,
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }
