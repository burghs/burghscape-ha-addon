import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "burghscape_agent"))

from app import main as agent_main  # noqa: E402


class ManualBackupOnceTests(unittest.TestCase):
    def state_path(self, directory: str) -> str:
        return str(Path(directory) / "managed-backup" / "manual-once-state.json")

    def read_state(self, path: str) -> dict:
        return json.loads(Path(path).read_text())

    def test_false_means_no_execution_and_armed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.state_path(tmp)
            should_run, operation_id = agent_main.prepare_manual_backup_once(False, path)
            self.assertFalse(should_run)
            self.assertIsNone(operation_id)
            self.assertEqual(self.read_state(path)["result"], "armed")

    def test_first_true_activation_runs_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.state_path(tmp)
            should_run, operation_id = agent_main.prepare_manual_backup_once(True, path)
            self.assertTrue(should_run)
            self.assertTrue(operation_id)
            state = self.read_state(path)
            self.assertTrue(state["trigger_state"])
            self.assertTrue(state["attempted"])
            self.assertEqual(state["result"], "running")

    def test_restart_while_true_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.state_path(tmp)
            first_run, first_operation = agent_main.prepare_manual_backup_once(True, path)
            second_run, second_operation = agent_main.prepare_manual_backup_once(True, path)
            self.assertTrue(first_run)
            self.assertFalse(second_run)
            self.assertEqual(first_operation, second_operation)

    def test_failed_attempt_while_true_does_not_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.state_path(tmp)
            should_run, operation_id = agent_main.prepare_manual_backup_once(True, path)
            self.assertTrue(should_run)
            Path(path).write_text(json.dumps({
                "trigger_state": True,
                "attempted": True,
                "operation_id": operation_id,
                "result": "failed",
                "error_category": "RuntimeError",
            }))
            retry, retry_operation = agent_main.prepare_manual_backup_once(True, path)
            self.assertFalse(retry)
            self.assertEqual(retry_operation, operation_id)

    def test_true_false_true_rearms_and_runs_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.state_path(tmp)
            first_run, first_operation = agent_main.prepare_manual_backup_once(True, path)
            self.assertTrue(first_run)
            reset_run, reset_operation = agent_main.prepare_manual_backup_once(False, path)
            self.assertFalse(reset_run)
            self.assertIsNone(reset_operation)
            second_run, second_operation = agent_main.prepare_manual_backup_once(True, path)
            self.assertTrue(second_run)
            self.assertNotEqual(first_operation, second_operation)

    def test_malformed_state_file_is_handled_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.state_path(tmp)
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text("not json")
            should_run, operation_id = agent_main.prepare_manual_backup_once(True, path)
            self.assertTrue(should_run)
            self.assertTrue(operation_id)

    def test_workflow_completion_records_safe_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.state_path(tmp)
            should_run, operation_id = agent_main.prepare_manual_backup_once(True, path)
            self.assertTrue(should_run)
            result = {
                "backup_id": 42,
                "ha_backup_slug": "abc123",
                "size_bytes": 100,
                "sha256": "a" * 64,
            }
            with patch("app.manual_backup.run_manual_backup", new=AsyncMock(return_value=result)):
                asyncio.run(agent_main.run_manual_backup_once_background(operation_id, path))
            state = self.read_state(path)
            self.assertEqual(state["result"], "completed")
            self.assertEqual(state["backup_id"], 42)
            self.assertEqual(state["ha_backup_slug"], "abc123")

    def test_workflow_exception_does_not_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.state_path(tmp)
            should_run, operation_id = agent_main.prepare_manual_backup_once(True, path)
            self.assertTrue(should_run)
            with patch("app.manual_backup.run_manual_backup", new=AsyncMock(side_effect=RuntimeError("boom"))):
                asyncio.run(agent_main.run_manual_backup_once_background(operation_id, path))
            state = self.read_state(path)
            self.assertEqual(state["result"], "failed")
            self.assertEqual(state["error_category"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
