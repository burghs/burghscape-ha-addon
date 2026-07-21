import asyncio
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from fastapi import HTTPException
from backup_storage import filesystem_summary, safe_managed_path, storage_health
from models import Backup, Client
from routers import backup_state


class ScalarResult:
    def __init__(self, values):
        self.values = values if isinstance(values, list) else [values]
    def scalars(self):
        return self
    def all(self):
        return self.values
    def first(self):
        return self.values[0] if self.values else None


class FakeDB:
    def __init__(self, results):
        self.results = list(results)
        self.deleted = []
        self.committed = 0
        self.rolled_back = 0
        self.added = []
    async def execute(self, *_args, **_kwargs):
        return self.results.pop(0) if self.results else ScalarResult([])
    async def delete(self, value):
        self.deleted.append(value)
    async def commit(self):
        self.committed += 1
    async def rollback(self):
        self.rolled_back += 1
    def add(self, value):
        self.added.append(value)


class RC132StorageTests(unittest.TestCase):
    def test_health_thresholds(self):
        self.assertEqual(storage_health(69.9), "healthy")
        self.assertEqual(storage_health(70.0), "attention")
        self.assertEqual(storage_health(85.0), "warning")
        self.assertEqual(storage_health(95.0), "critical")

    def test_filesystem_capacity_calculation(self):
        usage = shutil._ntuple_diskusage(1000, 425, 575)
        settings = SimpleNamespace(BACKUP_LOCAL_PATH="/managed", PLATFORM_BACKUP_LOCAL_PATH="/platform")
        stat = SimpleNamespace(st_dev=7)
        with patch("backup_storage.get_settings", return_value=settings), patch.object(Path, "mkdir"), patch.object(Path, "is_dir", return_value=True), patch("backup_storage.shutil.disk_usage", return_value=usage), patch("backup_storage.os.stat", return_value=stat):
            summary = filesystem_summary()
        volume = summary["volumes"][0]
        self.assertEqual((volume["capacity_bytes"], volume["used_bytes"], volume["available_bytes"]), (1000, 425, 575))
        self.assertEqual(volume["usage_percent"], 42.5)
        self.assertTrue(summary["roots_shared"])

    def test_path_traversal_outside_directory_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "managed"
            platform = Path(temp)
            root.mkdir()
            settings = SimpleNamespace(BACKUP_LOCAL_PATH=str(root), PLATFORM_BACKUP_LOCAL_PATH=str(platform))
            with patch("backup_storage.get_settings", return_value=settings):
                for key in ("../escape.tar", "/tmp/escape.tar"):
                    with self.assertRaises(ValueError):
                        safe_managed_path(key)
                directory = root / "1" / "folder"
                directory.mkdir(parents=True)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    safe_managed_path("1/folder")
                outside = Path(temp) / "outside.tar"
                outside.write_bytes(b"x")
                link = root / "1" / "link.tar"
                link.symlink_to(outside)
                with self.assertRaises(ValueError):
                    safe_managed_path("1/link.tar")

    def test_storage_summary_aggregates_and_sorts_groups(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "managed"
            root.mkdir()
            (root / "1").mkdir()
            (root / "2").mkdir()
            (root / "1/a.tar").write_bytes(b"a" * 10)
            (root / "1/b.tar").write_bytes(b"b" * 15)
            (root / "2/c.tar").write_bytes(b"c" * 40)
            settings = SimpleNamespace(BACKUP_LOCAL_PATH=str(root), PLATFORM_BACKUP_LOCAL_PATH=temp)
            clients = [SimpleNamespace(id=1, name="Alpha"), SimpleNamespace(id=2, name="Beta")]
            instances = [SimpleNamespace(client_id=1, name="Alpha HA"), SimpleNamespace(client_id=2, name="Beta HA")]
            records = [
                SimpleNamespace(id=1, client_id=1, storage_key="1/a.tar", status="completed", completed_at=datetime(2026, 7, 1), created_at=datetime(2026, 7, 1)),
                SimpleNamespace(id=2, client_id=1, storage_key="1/b.tar", status="completed", completed_at=datetime(2026, 7, 2), created_at=datetime(2026, 7, 2)),
                SimpleNamespace(id=3, client_id=2, storage_key="2/c.tar", status="completed", completed_at=datetime(2026, 7, 3), created_at=datetime(2026, 7, 3)),
            ]
            db = FakeDB([ScalarResult(clients), ScalarResult(instances), ScalarResult(records)])
            capacity = {"available": True, "volumes": [], "roots_shared": True, "refreshed_at": "now"}
            async def available(*_args): return True
            with patch("routers.backup_state.filesystem_summary", return_value=capacity), patch("routers.backup_state.get_settings", create=True), patch("backup_storage.get_settings", return_value=settings), patch("routers.backup_state.is_customer_backup_available", side_effect=available), patch("routers.backup_state.platform_backup_files", return_value=[]):
                result = asyncio.run(backup_state.build_storage_summary(db))
        self.assertEqual(result["managed"], {"count": 3, "size_bytes": 65})
        self.assertEqual([group["client_name"] for group in result["groups"]], ["Beta", "Alpha"])
        self.assertEqual(result["groups"][1]["count"], 2)
        self.assertEqual(result["groups"][1]["oldest_at"], "2026-07-01T00:00:00")
        self.assertEqual(result["groups"][1]["newest_at"], "2026-07-02T00:00:00")

    def test_summary_failure_is_controlled(self):
        db = FakeDB([])
        with patch("routers.backup_state.filesystem_summary", side_effect=PermissionError()):
            result = asyncio.run(backup_state.build_storage_summary(db))
        self.assertFalse(result["available"])

    def test_successful_deletion_is_scoped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "managed"
            (root / "4").mkdir(parents=True)
            archive = root / "4/backup.tar"
            archive.write_bytes(b"archive")
            settings = SimpleNamespace(BACKUP_LOCAL_PATH=str(root), PLATFORM_BACKUP_LOCAL_PATH=temp)
            backup = Backup(id=8, client_id=4, storage_key="4/backup.tar", filename="backup.tar", size_bytes=7, status="completed")
            client = Client(id=4, name="Client")
            db = FakeDB([ScalarResult(backup), ScalarResult(client), ScalarResult([]), ScalarResult([])])
            with patch("backup_storage.get_settings", return_value=settings), patch("routers.backup_state.build_storage_summary", new=AsyncMock(return_value={"available": True})):
                result = asyncio.run(backup_state.admin_delete_managed_backup(8, {"username": "admin"}, db))
            self.assertFalse(archive.exists())
            self.assertEqual(db.deleted, [backup])
            self.assertEqual(result["recovered_bytes"], 7)
            self.assertEqual(client.id, 4)

    def test_missing_and_cross_client_paths_preserve_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "managed"
            root.mkdir()
            settings = SimpleNamespace(BACKUP_LOCAL_PATH=str(root), PLATFORM_BACKUP_LOCAL_PATH=temp)
            client = Client(id=4, name="Client")
            for key, expected in (("4/missing.tar", 409), ("9/wrong.tar", 400), ("../wrong.tar", 400)):
                backup = Backup(id=8, client_id=4, storage_key=key, filename="backup.tar", status="completed")
                db = FakeDB([ScalarResult(backup), ScalarResult(client)])
                with patch("backup_storage.get_settings", return_value=settings):
                    with self.assertRaises(HTTPException) as raised:
                        asyncio.run(backup_state.admin_delete_managed_backup(8, {"username": "admin"}, db))
                self.assertEqual(raised.exception.status_code, expected)
                self.assertEqual(db.deleted, [])

    def test_missing_record_is_404(self):
        db = FakeDB([ScalarResult([])])
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(backup_state.admin_delete_managed_backup(404, {"username": "admin"}, db))
        self.assertEqual(raised.exception.status_code, 404)

    def test_unauthenticated_admin_endpoints_are_rejected(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(backup_state.router)
        response = TestClient(app).get("/api/admin/backup-storage")
        self.assertEqual(response.status_code, 401)
        response = TestClient(app).delete("/api/admin/managed-backups/1")
        self.assertEqual(response.status_code, 401)

    def test_database_failure_restores_archive_and_preserves_metadata(self):
        class FailingDB(FakeDB):
            async def commit(self):
                raise RuntimeError("database failure")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "managed"
            (root / "4").mkdir(parents=True)
            archive = root / "4/backup.tar"
            archive.write_bytes(b"archive")
            settings = SimpleNamespace(BACKUP_LOCAL_PATH=str(root), PLATFORM_BACKUP_LOCAL_PATH=temp)
            backup = Backup(id=8, client_id=4, storage_key="4/backup.tar", filename="backup.tar", size_bytes=7, status="completed")
            client = Client(id=4, name="Client")
            db = FailingDB([ScalarResult(backup), ScalarResult(client), ScalarResult([]), ScalarResult([])])
            with patch("backup_storage.get_settings", return_value=settings):
                with self.assertRaises(HTTPException) as raised:
                    asyncio.run(backup_state.admin_delete_managed_backup(8, {"username": "admin"}, db))
            self.assertEqual(raised.exception.status_code, 500)
            self.assertTrue(archive.is_file())
            self.assertEqual(db.rolled_back, 1)

    def test_frontend_contains_storage_and_confirmed_delete_without_platform_delete(self):
        backups = (ROOT.parent / "frontend/src/pages/Backups.jsx").read_text()
        dashboard = (ROOT.parent / "frontend/src/pages/Dashboard.jsx").read_text()
        self.assertIn("Backup Storage", backups)
        self.assertIn("Estimated space recovered", backups)
        self.assertIn("Permanently delete", backups)
        self.assertIn("Download", backups)
        self.assertIn("Backup Storage", dashboard)
        platform_section = backups.split('id="server-backups"', 1)[1].split("{deleteTarget &&", 1)[0]
        self.assertNotIn('variant="danger"', platform_section)


if __name__ == "__main__":
    unittest.main()
