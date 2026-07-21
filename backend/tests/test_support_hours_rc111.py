import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from routers import portal_users
from support_hours import calculate_support_hours, format_hours, support_ticket_notice
from routers.portal import PORTAL_HTML
from collections import defaultdict


class SupportHoursCalculationTests(unittest.TestCase):
    def test_quarter_plus_one_hour_is_one_and_quarter(self):
        result = calculate_support_hours(0, [0.25, 1.00])
        self.assertEqual(format_hours(result["logged"]), "1.25")

    def test_basic_plan_calculation(self):
        result = calculate_support_hours(0, [0.25, 1.00])
        self.assertEqual(format_hours(result["included"]), "0")
        self.assertEqual(format_hours(result["remaining"]), "0")
        self.assertEqual(format_hours(result["potentially_billable"]), "1.25")

    def test_plan_with_included_hours(self):
        result = calculate_support_hours(2, [0.25, 1.00])
        self.assertEqual(format_hours(result["logged"]), "1.25")
        self.assertEqual(format_hours(result["remaining"]), "0.75")
        self.assertEqual(format_hours(result["potentially_billable"]), "0")

    def test_over_hour_calculation(self):
        result = calculate_support_hours(2, [1, 2])
        self.assertEqual(format_hours(result["remaining"]), "0")
        self.assertEqual(format_hours(result["potentially_billable"]), "1")

    def test_basic_plan_notice_is_visible_and_non_blocking(self):
        notice = support_ticket_notice("basic")
        self.assertIn("does not include monthly support hours", notice)
        self.assertIn("may be billable after review", notice)
        self.assertNotIn("checkbox", notice.lower())
        self.assertEqual(support_ticket_notice("standard"), "")
        values = defaultdict(str, support_ticket_notice_html=notice)
        html = PORTAL_HTML.format_map(values)
        self.assertLess(html.index("does not include monthly support hours"), html.index('id="ticket-title"'))
        self.assertIn("submitTicket()", html)


class PortalTicketSubmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_existing_ticket_submission_remains_functional(self):
        class DB:
            def __init__(self): self.added = None
            def add(self, value): self.added = value
            async def flush(self): self.added.id = 42
        db = DB()
        request = SimpleNamespace(cookies={"portal_token": "session"})
        user = SimpleNamespace(client_id=7)
        with patch.object(portal_users, "verify_portal_token", new=AsyncMock(return_value=user)):
            result = await portal_users.create_portal_ticket({"title": "Help", "description": "Details", "priority": "normal"}, request, db)
        self.assertEqual(result, {"status": "created", "ticket_id": 42})
        self.assertEqual(db.added.client_id, 7)
        self.assertEqual(db.added.hours_used, 0.0)


if __name__ == "__main__":
    unittest.main()
