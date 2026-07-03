"""Base storage backend abstract class."""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class UploadPart:
    part_number: int
    upload_url: str


@dataclass
class MultipartUpload:
    upload_id: str
    key: str
    parts: List[UploadPart]


@dataclass
class UploadResult:
    key: str
    size: int
    etag: str
    checksum: Optional[str] = None


@dataclass
class BackupObject:
    key: str
    size: int
    etag: str
    last_modified: str
    metadata: Dict[str, str]


class StorageBackend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    async def create_multipart_upload(
        self, 
        key: str, 
        content_type: str = 'application/gzip',
        metadata: Optional[Dict[str, str]] = None
    ) -> MultipartUpload:
        pass
    
    @abstractmethod
    async def get_more_presigned_parts(
        self, 
        upload_id: str, 
        key: str, 
        start_part: int, 
        count: int = 100
    ) -> List[UploadPart]:
        pass
    
    @abstractmethod
    async def complete_multipart_upload(
        self, 
        upload_id: str, 
        key: str, 
        parts: List[Dict[str, Any]]
    ) -> UploadResult:
        pass
    
    @abstractmethod
    async def abort_multipart_upload(self, upload_id: str, key: str) -> bool:
        pass
    
    @abstractmethod
    async def generate_presigned_download_url(
        self, 
        key: str, 
        expires_in: int = 3600,
        filename: Optional[str] = None
    ) -> str:
        pass
    
    @abstractmethod
    async def delete_object(self, key: str) -> bool:
        pass
    
    @abstractmethod
    async def list_objects(self, prefix: str = '', max_keys: int = 100) -> List[BackupObject]:
        pass
    
    @abstractmethod
    async def get_object_metadata(self, key: str) -> Optional[BackupObject]:
        pass

