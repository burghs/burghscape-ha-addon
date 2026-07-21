import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from support_hours import calculate_support_hours
from routers.support import serialize_ticket


class RC12SupportTests(unittest.TestCase):
    def test_ticket_derived_plan_totals_remain_correct(self):
        self.assertEqual(calculate_support_hours(0, [0.25, 1])["potentially_billable"], 1.25)
        included = calculate_support_hours(2, [0.25, 1])
        self.assertEqual(included["remaining"], 0.75)
        over = calculate_support_hours(2, [1, 2])
        self.assertEqual(over["potentially_billable"], 1)

    def test_resolution_is_serialized_separately(self):
        ticket = SimpleNamespace(id=7, client_id=3, title="Test", description="Original",
            resolution="<script>alert(1)</script>", hours_used=1.25, status="closed", priority="normal",
            created_at=None, updated_at=None, completed_at=None)
        result = serialize_ticket(ticket, "Jackie")
        self.assertEqual(result["description"], "Original")
        self.assertEqual(result["resolution"], "<script>alert(1)</script>")
        self.assertEqual(result["client_name"], "Jackie")

    def test_management_sources_preserve_security_and_scope(self):
        root = Path(__file__).resolve().parents[2]
        clients = (root / "frontend/src/pages/Clients.jsx").read_text()
        backups = (root / "frontend/src/pages/Backups.jsx").read_text()
        portal = (root / "backend/app/routers/portal.py").read_text()
        self.assertIn("existing Agent token will stop working", clients)
        self.assertIn("/tokens", clients)
        self.assertNotIn("method: 'DELETE',\n        credentials: 'include' });\n      if (res.ok) {\n        fetchClients", clients)
        self.assertIn("Home Assistant Backups", backups)
        self.assertIn("Platform Server Backups", backups)
        self.assertNotIn("Delete</Button>", backups)
        self.assertIn("escape(t.resolution)", portal)


if __name__ == "__main__":
    unittest.main()
