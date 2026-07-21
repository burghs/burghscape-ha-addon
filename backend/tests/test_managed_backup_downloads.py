import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from admin_auth import get_current_admin
from routers import backup_state, backups, portal
from storage.local_backend import LocalStorageBackend


class ScalarResult:
    def __init__(self, first=None, all_values=None):
        self.first_value = first
        self.all_values = all_values

    def scalars(self):
        return self

    def first(self):
        return self.first_value

    def all(self):
        return self.all_values if self.all_values is not None else ([] if self.first_value is None else [self.first_value])


class SequenceDB:
    def __init__(self, results):
        self.results = list(results)
        self.queries = []

    async def execute(self, query):
        self.queries.append(str(query))
        return self.results.pop(0)


class SessionContext:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *_args):
        return None


class Request:
    def __init__(self, cookies=None):
        self.cookies = cookies or {}
        self.headers = {}


class ManagedBackupDownloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_can_list_and_download_completed_backup(self):
        client = SimpleNamespace(id=7, name="Client Seven")
        backup = SimpleNamespace(id=3, client_id=7, filename="backup.tar", size_bytes=10, status="completed", completed_at=None, created_at=None)
        instance = SimpleNamespace(client_id=7, name="Client Seven HA")
        list_db = SequenceDB([
            ScalarResult(all_values=[client]),
            ScalarResult(all_values=[backup]),
            ScalarResult(all_values=[instance]),
            ScalarResult(all_values=[]),
            ScalarResult(first=backup),
        ])
        with patch.object(backup_state, "is_customer_backup_available", new=AsyncMock(return_value=True)):
            result = await backup_state.admin_backup_state({"username": "admin"}, list_db)
        self.assertEqual(result["backups"][0]["client_name"], "Client Seven")
        self.assertEqual(result["backups"][0]["instance_name"], "Client Seven HA")
        self.assertEqual(result["backups"][0]["download_url"], "/api/admin/managed-backups/3/download")

        download_db = SequenceDB([ScalarResult(first=backup), ScalarResult(first=client), ScalarResult(first=instance)])
        with patch.object(backup_state, "build_backup_file_response", new=AsyncMock(return_value="file-response")):
            response = await backup_state.admin_managed_backup_download(3, {"username": "admin"}, download_db)
        self.assertEqual(response, "file-response")

    async def test_unauthenticated_admin_is_rejected(self):
        with self.assertRaises(HTTPException) as raised:
            await get_current_admin(Request())
        self.assertEqual(raised.exception.status_code, 401)

    async def test_client_lists_only_completed_tenant_backups(self):
        user = SimpleNamespace(id=4, client_id=7, is_active=True)
        record = SimpleNamespace(id=3, filename="backup.tar", size_bytes=10, status="completed", started_at=None, completed_at=None)
        client = SimpleNamespace(id=7, name="Client Seven")
        db = SequenceDB([ScalarResult(first=user), ScalarResult(all_values=[record]), ScalarResult(first=client)])
        portal.portal_sessions["session"] = user.id
        try:
            with patch.object(portal, "async_session", return_value=SessionContext(db)), patch.object(portal, "is_customer_backup_available", new=AsyncMock(return_value=True)):
                result = await portal.portal_backups(Request({"portal_token": "session"}))
        finally:
            portal.portal_sessions.pop("session", None)
        self.assertEqual(len(result["backups"]), 1)
        self.assertIn("backups.client_id", db.queries[1])
        self.assertIn("backups.status", db.queries[1])

    async def test_client_can_download_own_backup_but_not_another_clients(self):
        user = SimpleNamespace(id=4, client_id=7, is_active=True)
        client = SimpleNamespace(id=7, name="Client Seven")
        record = SimpleNamespace(id=3, client_id=7, filename="backup.tar", storage_key="7/backup.tar", status="completed", completed_at=None, created_at=None)
        portal.portal_sessions["session"] = user.id
        try:
            own_db = SequenceDB([ScalarResult(first=user), ScalarResult(first=record), ScalarResult(first=client), ScalarResult(first=SimpleNamespace(name="Client Seven HA"))])
            with patch.object(portal, "async_session", return_value=SessionContext(own_db)), patch.object(portal, "build_backup_file_response", new=AsyncMock(return_value="file-response")):
                response = await portal.portal_backup_download(3, Request({"portal_token": "session"}))
            self.assertEqual(response, "file-response")
            self.assertIn("backups.client_id", own_db.queries[1])

            foreign_db = SequenceDB([ScalarResult(first=user), ScalarResult(first=None)])
            with patch.object(portal, "async_session", return_value=SessionContext(foreign_db)):
                with self.assertRaises(HTTPException) as rejected:
                    await portal.portal_backup_download(99, Request({"portal_token": "session"}))
            self.assertEqual(rejected.exception.status_code, 404)
        finally:
            portal.portal_sessions.pop("session", None)

    async def test_missing_record_and_missing_file_are_controlled(self):
        with self.assertRaises(HTTPException) as missing_record:
            await backup_state.admin_managed_backup_download(999, {"username": "admin"}, SequenceDB([ScalarResult(first=None)]))
        self.assertEqual(missing_record.exception.status_code, 404)

        with tempfile.TemporaryDirectory() as tempdir:
            backend = LocalStorageBackend({"path": tempdir})
            client = SimpleNamespace(id=7)
            record = SimpleNamespace(filename="backup.tar", storage_key="7/backup.tar", status="completed")
            with patch.object(backups, "get_client_storage_backend", return_value=backend):
                with self.assertRaises(HTTPException) as missing_file:
                    await backups.build_backup_file_response(record, client)
            self.assertEqual(missing_file.exception.status_code, 404)

    async def test_download_sanitizes_filename_and_sets_archive_attachment(self):
        with tempfile.TemporaryDirectory() as tempdir:
            backend = LocalStorageBackend({"path": tempdir})
            path = backend._full_path("7/backup.tar")
            path.parent.mkdir(parents=True)
            path.write_bytes(b"archive")
            client = SimpleNamespace(id=7)
            record = SimpleNamespace(filename="../../backup.tar", storage_key="7/backup.tar", status="completed")
            with patch.object(backups, "get_client_storage_backend", return_value=backend):
                response = await backups.build_backup_file_response(record, client)
            self.assertEqual(Path(response.path), path)
            self.assertEqual(response.media_type, "application/x-tar")
            self.assertIn('filename="backup.tar"', response.headers["content-disposition"])


    def test_meaningful_download_filename_uses_safe_local_time(self):
        from datetime import datetime
        client = SimpleNamespace(name="Jackie & Co")
        record = SimpleNamespace(filename="internal.tar", storage_key="7/internal.tar", completed_at=datetime.fromisoformat("2026-07-21T11:01:00"), created_at=None)
        self.assertEqual(backups.meaningful_backup_filename(record, client, "Jackies HA"), "jackie-co-jackies-ha-2026-07-21-1301.tar")

    async def test_synthetic_and_zero_byte_records_are_excluded(self):
        client = SimpleNamespace(id=7)
        synthetic = SimpleNamespace(filename="phase2a-synthetic.tar", storage_key="7/synthetic.tar", status="completed", size_bytes=44)
        empty = SimpleNamespace(filename="real.tar", storage_key="7/real.tar", status="completed", size_bytes=0)
        self.assertFalse(await backups.is_customer_backup_available(synthetic, client))
        self.assertFalse(await backups.is_customer_backup_available(empty, client))


if __name__ == "__main__":
    unittest.main()
