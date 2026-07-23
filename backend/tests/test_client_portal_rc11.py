import sys
import unittest
from unittest.mock import patch
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from routers import portal
from routers.portal import PORTAL_HTML


class ClientPortalRC11Tests(unittest.TestCase):
    def render(self):
        values = defaultdict(str)
        for key in ("cpu_percent", "memory_percent", "disk_percent", "hours_percent", "entity_count", "addon_count_display", "integration_count", "open_ticket_count"):
            values[key] = 0
        return PORTAL_HTML.format_map(values)

    def test_authenticated_portal_build_marker_dependency_is_available(self):
        with patch.dict(portal.os.environ, {"BUILD_COMMIT": "test<commit>"}):
            self.assertEqual(portal.portal_build_commit(), "test&lt;commit&gt;")

    def test_dashboard_has_required_consolidated_structure(self):
        html = self.render()
        for text in ("System Overview", "Environment &amp; Updates", "Backup Protection", "Account &amp; Support", "Setup Details"):
            self.assertIn(text, html)
        self.assertNotIn("Stored Managed Backups</h2>", html)
        self.assertNotIn("Native Home Assistant Backup Status", html)

    def test_setup_release_support_and_report_actions_remain(self):
        html = self.render()
        for text in ("subscription-token-value", "copySecretValue", "Home Assistant Remote URL", "View release information", "Release Notes", "Breaking Changes", "submitTicket", "/api/portal/report"):
            self.assertIn(text, html)

    def test_mobile_and_modal_controls_are_accessible(self):
        html = self.render()
        for text in ("aria-controls=\"mobile-nav\"", "aria-modal=\"true\"", "aria-label=\"Close setup details\"", "Escape", "max-height:calc(100dvh"):
            self.assertIn(text, html)

    def test_backup_history_uses_instance_and_date_not_internal_filename(self):
        html = self.render()
        self.assertIn("instance+' — '+backupDate(item.completed_at)", html)
        self.assertNotIn("title.textContent=item.filename", html)
        self.assertIn("Show fewer backups", html)
        self.assertNotIn("Encryption key", html)


if __name__ == "__main__":
    unittest.main()
