"""Cloudflare R2 (S3-compatible) storage backend."""
import os
import hashlib
from typing import Optional, List, Dict, Any
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from . import (
    StorageBackend, 
    UploadPart, 
    MultipartUpload, 
    UploadResult, 
    BackupObject
)


class R2Backend(StorageBackend):
    """R2 storage backend using boto3."""

    def __init__(self, config: Dict[str, Any]):
        self.account_id = config.get("account_id") or os.getenv("R2_ACCOUNT_ID")
        self.access_key = config.get("access_key_id") or os.getenv("R2_ACCESS_KEY_ID")
        self.secret_key = config.get("secret_access_key") or os.getenv("R2_SECRET_ACCESS_KEY")
        self.bucket = config.get("bucket") or os.getenv("R2_BUCKET", "burghscape-backups")
        self.region = config.get("region", "auto")
        self.prefix = config.get("prefix", "")
        
        if not all([self.account_id, self.access_key, self.secret_key]):
            raise ValueError("R2 credentials not configured")

        self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"
        
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region,
            config=Config(signature_version="s3v4"),
        )

    def _full_key(self, key: str) -> str:
        """Prepend prefix to key."""
        if self.prefix and not key.startswith(self.prefix):
            return f"{self.prefix.rstrip('/')}/{key}"
        return key

    async def create_multipart_upload(
        self, 
        key: str, 
        content_type: str = "application/gzip",
        metadata: Optional[Dict[str, str]] = None
    ) -> MultipartUpload:
        key = self._full_key(key)
        response = self.client.create_multipart_upload(
            Bucket=self.bucket,
            Key=key,
            ContentType=content_type,
            Metadata=metadata or {},
        )
        upload_id = response["UploadId"]
        
        # Generate presigned URLs for parts (up to 10000 parts max, but we'll do 100 at a time)
        # Client will request more as needed
        parts = []
        for i in range(1, 101):  # Generate first 100 part URLs
            url = self.client.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": self.bucket,
                    "Key": key,
                    "UploadId": upload_id,
                    "PartNumber": i,
                },
                ExpiresIn=3600,  # 1 hour
            )
            parts.append(UploadPart(part_number=i, upload_url=url))
        
        return MultipartUpload(upload_id=upload_id, key=key, parts=parts)

    async def get_more_presigned_parts(
        self, 
        upload_id: str, 
        key: str, 
        start_part: int, 
        count: int = 100
    ) -> List[UploadPart]:
        """Get more presigned part URLs for large uploads."""
        key = self._full_key(key)
        parts = []
        for i in range(start_part, start_part + count):
            url = self.client.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": self.bucket,
                    "Key": key,
                    "UploadId": upload_id,
                    "PartNumber": i,
                },
                ExpiresIn=3600,
            )
            parts.append(UploadPart(part_number=i, upload_url=url))
        return parts

    async def complete_multipart_upload(
        self, 
        upload_id: str, 
        key: str, 
        parts: List[Dict[str, Any]]
    ) -> UploadResult:
        key = self._full_key(key)
        # parts should be list of {"PartNumber": int, "ETag": str}
        response = self.client.complete_multipart_upload(
            Bucket=self.bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )
        return UploadResult(
            key=key,
            size=0,  # Will be filled by head_object
            etag=response.get("ETag", "").strip('"'),
            checksum=response.get("ChecksumSHA256"),
        )

    async def abort_multipart_upload(self, upload_id: str, key: str) -> bool:
        key = self._full_key(key)
        try:
            self.client.abort_multipart_upload(
                Bucket=self.bucket,
                Key=key,
                UploadId=upload_id,
            )
            return True
        except ClientError:
            return False

    async def generate_presigned_download_url(
        self, 
        key: str, 
        expires_in: int = 3600,
        filename: Optional[str] = None
    ) -> str:
        key = self._full_key(key)
        params = {
            "Bucket": self.bucket,
            "Key": key,
        }
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        return self.client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in,
        )

    async def delete_object(self, key: str) -> bool:
        key = self._full_key(key)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    async def list_objects(self, prefix: str = "", max_keys: int = 100) -> List[BackupObject]:
        prefix = self._full_key(prefix)
        response = self.client.list_objects_v2(
            Bucket=self.bucket,
            Prefix=prefix,
            MaxKeys=max_keys,
        )
        objects = []
        for obj in response.get("Contents", []):
            objects.append(BackupObject(
                key=obj["Key"],
                size=obj["Size"],
                etag=obj["ETag"].strip('"'),
                last_modified=obj["LastModified"].isoformat(),
                metadata={},
            ))
        return objects

    async def get_object_metadata(self, key: str) -> Optional[BackupObject]:
        key = self._full_key(key)
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=key)
            return BackupObject(
                key=key,
                size=response["ContentLength"],
                etag=response["ETag"].strip('"'),
                last_modified=response["LastModified"].isoformat(),
                metadata=response.get("Metadata", {}),
            )
        except ClientError:
            return None

