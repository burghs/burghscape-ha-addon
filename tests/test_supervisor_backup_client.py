import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "burghscape_agent"))

from app.manual_backup import SupervisorApiError, SupervisorBackupClient  # noqa: E402


class FakeContent:
    async def iter_chunked(self, size):
        yield b"backup-bytes"


class FakeResponse:
    def __init__(self, status=200, body="{}"):
        self.status = status
        self.body = body
        self.content = FakeContent()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self):
        return self.body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.closed = False
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url))
        return self._next_response()

    def request(self, method, url, **kwargs):
        self.calls.append((method, url))
        return self._next_response()

    def _next_response(self):
        if not self.responses:
            raise AssertionError("No fake response queued")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def close(self):
        self.closed = True


class FakeSessionFactory:
    def __init__(self, responses):
        self.responses = responses
        self.instance = None

    def __call__(self, *args, **kwargs):
        self.instance = FakeSession(self.responses)
        return self.instance


def run(coro):
    return asyncio.run(coro)


class SupervisorBackupClientTests(unittest.TestCase):
    def test_config_uses_manager_role(self):
        text = (REPO / "burghscape_agent" / "config.yaml").read_text()
        self.assertIn('version: "0.2.53"', text)
        self.assertIn("hassio_api: true", text)
        self.assertIn("hassio_role: manager", text)
        self.assertIn("backup_enabled: false", text)
        self.assertNotIn("hassio_role: admin", text)
        self.assertNotIn("docker_api: true", text)
        self.assertNotIn("full_access: true", text)
        self.assertNotIn("protected: false", text)

    def test_supervisor_403_logs_safe_failure_and_closes_session(self):
        token = "test-token-value-not-for-logs"
        factory = FakeSessionFactory([FakeResponse(403, "forbidden"), FakeResponse(403, "forbidden")])

        async def use_client():
            async with SupervisorBackupClient(token):
                pass

        with patch("app.manual_backup.aiohttp.ClientSession", factory):
            with self.assertLogs("burghscape.agent.backup", level="ERROR") as logs:
                with self.assertRaises(SupervisorApiError) as ctx:
                    run(use_client())

        self.assertEqual(ctx.exception.status, 403)
        self.assertEqual(ctx.exception.category, "supervisor_role_rejected")
        self.assertTrue(factory.instance.closed)
        rendered_logs = "\n".join(logs.output)
        self.assertIn("Supervisor rejected add-on role", rendered_logs)
        self.assertNotIn(token, rendered_logs)
        self.assertNotIn("Authorization", rendered_logs)

    def test_session_closes_after_successful_client_operation(self):
        factory = FakeSessionFactory([
            FakeResponse(200, '{"data":{"backups":[]}}'),
            FakeResponse(200, '{"data":{"backups":[]}}'),
        ])

        async def use_client():
            async with SupervisorBackupClient("test-token-value") as client:
                backups = await client.list_backups()
                self.assertEqual(backups, [])

        with patch("app.manual_backup.aiohttp.ClientSession", factory):
            run(use_client())

        self.assertTrue(factory.instance.closed)

    def test_session_closes_after_backup_creation_exception(self):
        factory = FakeSessionFactory([
            FakeResponse(200, '{"data":{"backups":[]}}'),
            FakeResponse(500, "creation failed"),
        ])

        async def use_client():
            async with SupervisorBackupClient("test-token-value") as client:
                await client.create_full_backup("Burghscape Managed Backup Test")

        with patch("app.manual_backup.aiohttp.ClientSession", factory):
            with self.assertRaises(SupervisorApiError):
                run(use_client())

        self.assertTrue(factory.instance.closed)

    def test_session_closes_after_download_exception(self):
        factory = FakeSessionFactory([
            FakeResponse(200, '{"data":{"backups":[]}}'),
            FakeResponse(500, "download failed"),
        ])

        async def use_client():
            async with SupervisorBackupClient("test-token-value") as client:
                await client.download_backup("slug", Path("/tmp/unused-backup.tar"))

        with patch("app.manual_backup.aiohttp.ClientSession", factory):
            with self.assertRaises(SupervisorApiError):
                run(use_client())

        self.assertTrue(factory.instance.closed)


if __name__ == "__main__":
    unittest.main()
