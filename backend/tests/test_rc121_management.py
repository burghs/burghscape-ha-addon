import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from middleware import AdminAuthMiddleware
from routers import support
from support_hours import calculate_support_hours


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class RC121Tests(unittest.TestCase):
    def test_aggregate_support_metric_uses_ticket_values(self):
        values = [calculate_support_hours(0, [1])["logged"], calculate_support_hours(0, [0.25])["logged"]]
        self.assertEqual(sum(values), 1.25)

    def test_ticket_deletion_is_unauthenticated_without_admin_session(self):
        app = FastAPI()
        app.add_middleware(AdminAuthMiddleware)
        app.include_router(support.router, prefix="/api/support")
        with TestClient(app) as client:
            response = client.delete("/api/support/9")
        self.assertEqual(response.status_code, 401)

    def test_ticket_deletion_removes_only_selected_ticket(self):
        ticket = SimpleNamespace(id=7, client_id=3)
        db = SimpleNamespace(
            execute=AsyncMock(return_value=ScalarResult(ticket)),
            delete=AsyncMock(),
            commit=AsyncMock(),
            rollback=AsyncMock(),
        )
        result = asyncio.run(support.delete_ticket(7, {"username": "admin"}, db))
        db.delete.assert_awaited_once_with(ticket)
        db.commit.assert_awaited_once()
        db.rollback.assert_not_awaited()
        self.assertEqual(result["ticket_id"], 7)
        self.assertEqual(result["client_id"], 3)

    def test_ticket_deletion_missing_record_is_404(self):
        db = SimpleNamespace(execute=AsyncMock(return_value=ScalarResult(None)))
        with self.assertRaisesRegex(Exception, "404"):
            asyncio.run(support.delete_ticket(404, {"username": "admin"}, db))

    def test_ticket_deletion_failure_is_controlled_and_rolled_back(self):
        ticket = SimpleNamespace(id=7, client_id=3)
        db = SimpleNamespace(
            execute=AsyncMock(return_value=ScalarResult(ticket)),
            delete=AsyncMock(side_effect=RuntimeError("database failure")),
            commit=AsyncMock(),
            rollback=AsyncMock(),
        )
        with self.assertRaisesRegex(Exception, "500"):
            asyncio.run(support.delete_ticket(7, {"username": "admin"}, db))
        db.rollback.assert_awaited_once()
        db.commit.assert_not_awaited()

    def test_support_totals_recalculate_after_deletion(self):
        before = calculate_support_hours(2, [1, 0.25])
        after = calculate_support_hours(2, [1])
        self.assertEqual(before["logged"], 1.25)
        self.assertEqual(after["logged"], 1)
        self.assertEqual(after["remaining"], 1)

    def test_rc121_frontend_contract(self):
        root = Path(__file__).resolve().parents[2]
        clients = (root / "frontend/src/pages/Clients.jsx").read_text()
        instances = (root / "frontend/src/pages/Instances.jsx").read_text()
        backups = (root / "frontend/src/pages/Backups.jsx").read_text()
        support_page = (root / "frontend/src/pages/Support.jsx").read_text()
        self.assertIn("Support Time Logged This Month", clients)
        self.assertNotIn('label="Hours Remaining"', clients)
        self.assertIn("item.ip_address &&", instances)
        self.assertNotIn("Managed backup operations remain available", instances)
        self.assertIn("Last successful managed backup", instances)
        self.assertIn("Burghscape Platform", backups)
        self.assertIn("platformBackupSummary", backups)
        self.assertNotIn("Delete", backups)
        self.assertIn("groupTicketsByClient", support_page)
        self.assertIn("Permanently delete ticket", support_page)
        self.assertIn("permanently removes its recorded time", support_page)


if __name__ == "__main__":
    unittest.main()
