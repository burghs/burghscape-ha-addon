import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from fastapi import HTTPException
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from routers.backup_state import STALE_AFTER, _validate_transition, effective_state
class BackupStateTests(unittest.TestCase):
    def operation(self, state, age=timedelta()):
        return SimpleNamespace(state=state, updated_at=datetime.utcnow() - age)
    def test_active_operation_becomes_stale_after_threshold(self):
        self.assertEqual(effective_state(self.operation("uploading", STALE_AFTER + timedelta(seconds=1))), "stale")
    def test_recent_and_terminal_operations_are_not_rewritten(self):
        self.assertEqual(effective_state(self.operation("creating")), "creating")
        self.assertEqual(effective_state(self.operation("completed", STALE_AFTER * 2)), "completed")
    def test_transition_order_and_terminal_state_are_enforced(self):
        _validate_transition(self.operation("creating"), "uploading")
        with self.assertRaises(HTTPException): _validate_transition(self.operation("uploading"), "downloading")
        with self.assertRaises(HTTPException): _validate_transition(self.operation("completed"), "failed")
