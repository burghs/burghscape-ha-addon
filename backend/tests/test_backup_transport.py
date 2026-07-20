import hashlib
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from models import ClientStatus
from routers import backups
from storage.local_backend import LocalStorageBackend


class _ScalarResult:
    def __init__(self, value=None):
        self.value = value

    def scalars(self):
        return self

    def first(self):
        return self.value


class _UploadDB:
    def __init__(self, existing=None, fail_flush=False):
        self.existing = existing
        self.fail_flush = fail_flush
        self.added = None
        self.committed = False

    async def execute(self, _query):
        return _ScalarResult(self.existing)

    def add(self, value):
        self.added = value

    async def flush(self):
        if self.fail_flush:
            raise RuntimeError("database unavailable")
        self.added.id = 42

    async def commit(self):
        self.committed = True


class _Request:
    def __init__(self, chunks):
        self.chunks = chunks

    async def stream(self):
        for chunk in self.chunks:
            yield chunk


class _TokenDB:
    async def execute(self, _query):
        return _ScalarResult(None)


class BackupTransportTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = SimpleNamespace(id=7, status=ClientStatus.ACTIVE)
        self.payload = b"validated-home-assistant-backup"
        self.checksum = hashlib.sha256(self.payload).hexdigest()
        self.tempdir = tempfile.TemporaryDirectory()
        self.backend = LocalStorageBackend({"path": self.tempdir.name})

    def tearDown(self):
        self.tempdir.cleanup()

    async def _upload(self, db, chunks=None, checksum=None, declared_size=None):
        with (
            patch.object(backups, "validate_client_token", return_value=self.client),
            patch.object(backups, "get_client_storage_backend", return_value=self.backend),
            patch.object(backups, "get_backup_limits", return_value=(1024 * 1024, 1024)),
        ):
            return await backups.direct_backup_upload(
                request=_Request(chunks if chunks is not None else [self.payload]),
                authorization="Bearer redacted",
                x_backup_filename="ha-backup.tar",
                x_backup_size=declared_size if declared_size is not None else len(self.payload),
                x_backup_sha256=checksum or self.checksum,
                x_idempotency_key="operation-1",
                db=db,
            )

    async def test_validated_direct_upload_returns_backup_id_and_stores_checksum(self):
        db = _UploadDB()
        response = await self._upload(db)

        self.assertEqual(response.backup_id, 42)
        self.assertEqual(response.size, len(self.payload))
        self.assertEqual(response.checksum_sha256, self.checksum)
        self.assertEqual(db.added.client_id, self.client.id)
        self.assertEqual(db.added.storage_etag, f"sha256:{self.checksum}")
        self.assertTrue(db.committed)
        self.assertEqual(self.backend._full_path(response.key).read_bytes(), self.payload)

    async def test_checksum_mismatch_removes_incomplete_upload(self):
        with self.assertRaises(HTTPException) as raised:
            await self._upload(_UploadDB(), checksum="0" * 64)
        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(list(Path(self.tempdir.name).rglob("*.*")), [])

    async def test_incomplete_stream_and_database_failure_leave_no_archive(self):
        with self.assertRaises(HTTPException):
            await self._upload(_UploadDB(), chunks=[self.payload[:5]])
        with self.assertRaises(HTTPException) as raised:
            await self._upload(_UploadDB(fail_flush=True))
        self.assertEqual(raised.exception.status_code, 500)
        self.assertFalse(any(path.is_file() for path in Path(self.tempdir.name).rglob("*")))

    async def test_invalid_authentication_does_not_log_token_fragments(self):
        secret = "unique-sensitive-token-value"
        with self.assertLogs("burghscape.backup", logging.WARNING) as captured:
            with self.assertRaises(HTTPException) as raised:
                await backups.validate_client_token(f"Bearer {secret}", _TokenDB())
        self.assertEqual(raised.exception.status_code, 401)
        rendered = " ".join(captured.output)
        self.assertNotIn(secret, rendered)
        self.assertNotIn(secret[:8], rendered)

    async def test_local_download_is_tenant_scoped_and_missing_file_is_safe(self):
        key = "7/backup.tar"
        path = self.backend._full_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.payload)
        record = SimpleNamespace(id=3, client_id=7, filename="backup.tar", storage_key=key, status="completed")

        with (
            patch.object(backups, "validate_client_token", return_value=self.client),
            patch.object(backups, "get_client_storage_backend", return_value=self.backend),
        ):
            response = await backups.download_backup_file(3, "Bearer redacted", _UploadDB(existing=record))
            self.assertEqual(Path(response.path), path)

            with self.assertRaises(HTTPException) as rejected:
                await backups.download_backup_file(3, "Bearer redacted", _UploadDB(existing=None))
            self.assertEqual(rejected.exception.status_code, 404)

            path.unlink()
            with self.assertRaises(HTTPException) as missing:
                await backups.download_backup_file(3, "Bearer redacted", _UploadDB(existing=record))
            self.assertEqual(missing.exception.status_code, 404)

    def test_storage_keys_cannot_cross_tenant_or_escape_root(self):
        self.assertEqual(backups.validate_client_storage_key(self.client, "7/backup.tar"), "7/backup.tar")
        with self.assertRaises(HTTPException) as wrong_tenant:
            backups.validate_client_storage_key(self.client, "8/backup.tar")
        self.assertEqual(wrong_tenant.exception.status_code, 403)
        with self.assertRaises(ValueError):
            self.backend._full_path("../outside.tar")


if __name__ == "__main__":
    unittest.main()
