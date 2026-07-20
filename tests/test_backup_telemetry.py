import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "burghscape_agent"))

from app.ha_client import HAClient


class BackupTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.client = HAClient(SimpleNamespace(ha_url="http://homeassistant.local:8123", ha_token="redacted"))

    def test_empty_backup_list_is_safe_and_not_enabled(self):
        result = self.client._parse_backup_list([])
        self.assertFalse(result["enabled"])
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["file_count"], 0)

    def test_supervisor_backup_list_returns_complete_telemetry(self):
        result = self.client._parse_backup_list([
            {"slug": "older", "date": "2026-07-18T10:00:00+00:00", "size": 100},
            {"slug": "22f6ed92", "date": "2026-07-19T10:00:00+00:00", "size": "94320640"},
        ])
        self.assertTrue(result["enabled"])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["file_count"], 2)
        self.assertEqual(result["total_size_bytes"], 94320740)
        self.assertEqual(result["last_backup_timestamp"], "2026-07-19T10:00:00+00:00")

    def test_malformed_entries_do_not_break_heartbeat_telemetry(self):
        result = self.client._parse_backup_list([None, "bad", {"date": "not-a-date", "size": "bad"}])
        self.assertTrue(result["enabled"])
        self.assertEqual(result["file_count"], 1)
        self.assertEqual(result["total_size_bytes"], 0)
        self.assertEqual(result["last_backup"], "not-a-date")


if __name__ == "__main__":
    unittest.main()
