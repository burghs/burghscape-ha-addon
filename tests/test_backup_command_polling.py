import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "burghscape_agent"))

from app import main
from app.platform_client import PlatformClient


class BackupCommandPollingTests(unittest.TestCase):
    def test_unsupported_polling_is_not_exposed_or_called(self):
        self.assertFalse(hasattr(PlatformClient, "get_backup_command"))
        source = inspect.getsource(main.main_loop)
        self.assertNotIn("/api/backups/command", source)
        self.assertNotIn("get_backup_command", source)

    def test_manual_backup_workflow_remains_available(self):
        self.assertTrue(callable(main.prepare_manual_backup_once))
        self.assertTrue(callable(main.run_manual_backup_once_background))


if __name__ == "__main__":
    unittest.main()
