"""Local filesystem storage backend for tenant-scoped backup objects."""
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
import aiofiles
from datetime import datetime

from .base import (
    StorageBackend,
    UploadPart,
    MultipartUpload,
    UploadResult,
    BackupObject,
)


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage rooted at /backups/client-backups by default."""

    def __init__(self, config: Dict[str, Any]):
        self.storage_path = Path(config.get("path", "/backups/client-backups")).resolve()
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _full_path(self, key: str) -> Path:
        """Convert a tenant-scoped storage key to a safe filesystem path."""
        candidate = (self.storage_path / key).resolve()
        try:
            candidate.relative_to(self.storage_path)
        except ValueError:
            raise ValueError("storage key resolves outside backup root")
        return candidate

    async def create_multipart_upload(
        self,
        key: str,
        content_type: str = "application/gzip",
        metadata: Optional[Dict[str, str]] = None,
    ) -> MultipartUpload:
        path = self._full_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        import time
        upload_id = f"local_{int(time.time())}"
        upload_url = f"/api/backups/upload/local/{upload_id}/parts/1"
        return MultipartUpload(
            upload_id=upload_id,
            key=key,
            parts=[UploadPart(part_number=1, upload_url=upload_url)],
        )

    async def get_more_presigned_parts(
        self,
        upload_id: str,
        key: str,
        start_part: int,
        count: int = 100,
    ) -> List[UploadPart]:
        self._full_path(key)
        return []

    async def complete_multipart_upload(
        self,
        upload_id: str,
        key: str,
        parts: List[Dict[str, Any]],
    ) -> UploadResult:
        path = self._full_path(key)
        if not path.is_file():
            raise FileNotFoundError("backup object not found")
        async with aiofiles.open(path, "rb") as f:
            content = await f.read()
        size = len(content)
        etag = hashlib.md5(content).hexdigest()
        checksum = hashlib.sha256(content).hexdigest()
        return UploadResult(key=key, size=size, etag=f'"{etag}"', checksum=checksum)

    async def abort_multipart_upload(self, upload_id: str, key: str) -> bool:
        path = self._full_path(key)
        try:
            if path.exists():
                path.unlink()
            return True
        except Exception:
            return False

    async def generate_presigned_download_url(
        self,
        key: str,
        expires_in: int = 3600,
        filename: Optional[str] = None,
    ) -> str:
        self._full_path(key)
        return "/api/backups/download-file"

    async def delete_object(self, key: str) -> bool:
        path = self._full_path(key)
        try:
            if path.exists():
                path.unlink()
            return True
        except Exception:
            return False

    async def list_objects(self, prefix: str = "", max_keys: int = 100) -> List[BackupObject]:
        prefix_path = self._full_path(prefix) if prefix else self.storage_path
        objects = []
        count = 0
        for file_path in prefix_path.rglob("*"):
            if file_path.is_file() and count < max_keys:
                stat = file_path.stat()
                objects.append(BackupObject(
                    key=str(file_path.relative_to(self.storage_path)),
                    size=stat.st_size,
                    etag='"0"',
                    last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    metadata={},
                ))
                count += 1
        return objects

    async def get_object_metadata(self, key: str) -> Optional[BackupObject]:
        path = self._full_path(key)
        try:
            if path.exists() and path.is_file():
                stat = path.stat()
                return BackupObject(
                    key=key,
                    size=stat.st_size,
                    etag='"0"',
                    last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    metadata={},
                )
            return None
        except Exception:
            return None
