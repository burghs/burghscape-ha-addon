"""Local filesystem storage backend (for development/testing)."""
import os
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
    BackupObject
)


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, config: Dict[str, Any]):
        self.storage_path = Path(config.get("path", "/backups/client-backups"))
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.base_url = config.get("base_url", "http://localhost:8000/static/backups")

    def _full_path(self, key: str) -> Path:
        """Convert storage key to filesystem path."""
        safe_key = key.replace("../", "").replace("./", "")
        return self.storage_path / safe_key

    async def create_multipart_upload(
        self, 
        key: str, 
        content_type: str = "application/gzip",
        metadata: Optional[Dict[str, str]] = None
    ) -> MultipartUpload:
        path = self._full_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        import time
        upload_id = f"local_{int(time.time())}"
        
        upload_url = f"{self.base_url}/{key}?upload_id={upload_id}"
        
        parts = [UploadPart(part_number=1, upload_url=upload_url)]
        
        return MultipartUpload(upload_id=upload_id, key=key, parts=parts)

    async def get_more_presigned_parts(
        self, 
        upload_id: str, 
        key: str, 
        start_part: int, 
        count: int = 100
    ) -> List[UploadPart]:
        return []

    async def complete_multipart_upload(
        self, 
        upload_id: str, 
        key: str, 
        parts: List[Dict[str, Any]]
    ) -> UploadResult:
        path = self._full_path(key)
        async with aiofiles.open(path, "rb") as f:
            content = await f.read()
        
        size = len(content)
        etag = hashlib.md5(content).hexdigest()
        
        return UploadResult(
            key=key,
            size=size,
            etag=f'"{etag}"',
            checksum=None,
        )

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
        filename: Optional[str] = None
    ) -> str:
        base_url = self.base_url.rstrip("/")
        url = f"{base_url}/{key}"
        if filename:
            url += f"?response-content-disposition=attachment;filename={filename}"
        url += f"&expires_in={expires_in}"
        return url

    async def delete_object(self, key: str) -> bool:
        path = self._full_path(key)
        try:
            if path.exists():
                path.unlink()
            return True
        except Exception:
            return False

    async def list_objects(self, prefix: str = "", max_keys: int = 100) -> List[BackupObject]:
        prefix_path = self.storage_path / prefix if prefix else self.storage_path
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
            if path.exists():
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

