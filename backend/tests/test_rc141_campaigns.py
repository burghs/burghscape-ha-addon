import asyncio
import io
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.datastructures import Headers, UploadFile
from starlette.requests import Request

from database import Base
from models import Campaign, CampaignReadState, Client, ClientStatus, ClientUser
from routers import campaigns
from routers.portal_state import portal_sessions


def request_with_token(token):
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"cookie", f"portal_token={token}".encode())]})


def upload(name, content_type, data):
    return UploadFile(io.BytesIO(data), filename=name, headers=Headers({"content-type": content_type}))


class ScalarResult:
    def __init__(self, value): self.value = value
    def scalars(self): return self
    def first(self): return self.value
    def all(self): return [] if self.value is None else [self.value]
    def scalar(self): return self.value


class FailingCommitDB:
    def __init__(self, campaign): self.campaign = campaign; self.rolled_back = False
    async def execute(self, *_args): return ScalarResult(self.campaign)
    async def commit(self): raise RuntimeError("commit failed")
    async def rollback(self): self.rolled_back = True


class RC141CampaignTests(unittest.TestCase):
    def test_campaign_api_normalizes_offset_timestamps_to_utc(self):
        local = datetime(2026, 7, 22, 19, 0, tzinfo=timezone(timedelta(hours=2)))
        self.assertEqual(campaigns.database_datetime(local), datetime(2026, 7, 22, 17, 0))
        self.assertEqual(campaigns.api_datetime(datetime(2026, 7, 22, 17, 0)), "2026-07-22T17:00:00Z")

    def test_validation_rejects_invalid_type_dates_and_empty_selected_targeting(self):
        base = dict(internal_name="release", title="Release", campaign_type="announcement", body_content="Text")
        for values, detail in (
            ({**base, "campaign_type": "script"}, "Invalid campaign type"),
            ({**base, "starts_at": datetime(2026, 7, 22), "ends_at": datetime(2026, 7, 21)}, "End date"),
            ({**base, "target_all_clients": False}, "at least one client"),
        ):
            with self.assertRaises(HTTPException) as raised:
                campaigns.validate_input(campaigns.CampaignInput(**values))
            self.assertIn(detail, raised.exception.detail)

    def test_admin_endpoints_require_authentication(self):
        app = FastAPI()
        app.include_router(campaigns.router)
        client = TestClient(app)
        self.assertEqual(client.post("/api/admin/campaigns", json={}).status_code, 401)
        self.assertEqual(client.post("/api/admin/campaigns/1/image").status_code, 401)

    def test_client_payload_excludes_internal_fields_and_cta(self):
        item = Campaign(id=7, internal_name="internal", title="Safe", campaign_type="tip", body_content="Plain text", status="published", created_by="admin", updated_by="admin", target_all_clients=True)
        data = campaigns.client_payload(item, False)
        for key in ("internal_name", "image_reference", "created_by", "updated_by", "target_all_clients", "target_client_ids", "call_to_action_label"):
            self.assertNotIn(key, data)
        self.assertFalse(data["is_read"])

    def test_visibility_targeting_dates_and_read_state(self):
        async def scenario():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            async with sessions() as db:
                alpha = Client(name="Alpha", email="a@example.test", subdomain="alpha", status=ClientStatus.ACTIVE)
                beta = Client(name="Beta", email="b@example.test", subdomain="beta", status=ClientStatus.ACTIVE)
                db.add_all([alpha, beta]); await db.flush()
                alpha_user = ClientUser(client_id=alpha.id, name="Alpha User", email="a@example.test", password_hash="x", is_active=True)
                beta_user = ClientUser(client_id=beta.id, name="Beta User", email="b@example.test", password_hash="x", is_active=True)
                db.add_all([alpha_user, beta_user]); await db.flush()
                token_a, token_b = "campaign-alpha", "campaign-beta"
                portal_sessions[token_a] = alpha_user.id; portal_sessions[token_b] = beta_user.id
                now = campaigns.now_utc()
                visible = Campaign(internal_name="visible", title="Visible", campaign_type="announcement", body_content="Body", status="published", published_at=now, created_by="admin", updated_by="admin", target_all_clients=True)
                future = Campaign(internal_name="future", title="Future", campaign_type="tip", body_content="Body", status="published", published_at=now, starts_at=now + timedelta(days=1), created_by="admin", updated_by="admin", target_all_clients=True)
                expired = Campaign(internal_name="expired", title="Expired", campaign_type="tip", body_content="Body", status="published", published_at=now, ends_at=now - timedelta(seconds=1), created_by="admin", updated_by="admin", target_all_clients=True)
                draft = Campaign(internal_name="draft", title="Draft", campaign_type="tip", body_content="Body", status="draft", created_by="admin", updated_by="admin", target_all_clients=True)
                targeted = Campaign(internal_name="targeted", title="Targeted", campaign_type="promotion", body_content="Body", status="published", published_at=now, created_by="admin", updated_by="admin", target_all_clients=False)
                db.add_all([visible, future, expired, draft, targeted]); await db.flush()
                db.add(campaigns.CampaignTarget(campaign_id=targeted.id, client_id=alpha.id)); await db.commit()
                first = await campaigns.portal_campaigns(request_with_token(token_a), db)
                self.assertEqual({c["title"] for c in first["campaigns"]}, {"Visible", "Targeted"})
                self.assertEqual(first["unread_count"], 2)
                beta_list = await campaigns.portal_campaigns(request_with_token(token_b), db)
                self.assertEqual([c["title"] for c in beta_list["campaigns"]], ["Visible"])
                with self.assertRaises(HTTPException) as denied:
                    await campaigns.portal_campaign(targeted.id, request_with_token(token_b), db)
                self.assertEqual(denied.exception.status_code, 404)
                await campaigns.mark_read(targeted.id, request_with_token(token_a), db)
                await campaigns.mark_read(targeted.id, request_with_token(token_a), db)
                after = await campaigns.portal_campaigns(request_with_token(token_a), db)
                self.assertEqual(after["unread_count"], 1)
                reads = (await db.execute(select(CampaignReadState).where(CampaignReadState.campaign_id == targeted.id))).scalars().all()
                self.assertEqual(len(reads), 1)
                self.assertEqual((await campaigns.portal_campaigns(request_with_token(token_b), db))["unread_count"], 1)
                portal_sessions.pop(token_a, None); portal_sessions.pop(token_b, None)
            await engine.dispose()
        asyncio.run(scenario())

    def test_image_validation_safe_name_and_limits(self):
        async def scenario(root):
            settings = SimpleNamespace(CAMPAIGN_MEDIA_ROOT=root, CAMPAIGN_MAX_IMAGE_BYTES=32)
            with patch("routers.campaigns.get_settings", return_value=settings):
                path, kind = await campaigns.save_image(upload("../../offer.png", "image/png", b"\x89PNG\r\n\x1a\nvalid"))
                self.assertEqual(kind, "image/png")
                self.assertEqual(path.parent, Path(root).resolve())
                self.assertNotIn("offer", path.name)
                with self.assertRaises(HTTPException) as bad_mime:
                    await campaigns.save_image(upload("offer.png", "application/x-msdownload", b"MZ"))
                self.assertEqual(bad_mime.exception.status_code, 415)
                with self.assertRaises(HTTPException):
                    await campaigns.save_image(upload("offer.jpg", "image/png", b"\x89PNG\r\n\x1a\nvalid"))
                with self.assertRaises(HTTPException) as too_large:
                    await campaigns.save_image(upload("large.png", "image/png", b"\x89PNG\r\n\x1a\n" + b"x" * 40))
                self.assertEqual(too_large.exception.status_code, 413)
        with tempfile.TemporaryDirectory() as root:
            asyncio.run(scenario(root))

    def test_replacement_failure_preserves_old_image(self):
        async def scenario(root):
            old = Path(root) / "old.png"; old.write_bytes(b"old")
            item = Campaign(id=3, internal_name="image", title="Image", campaign_type="announcement", body_content="Body", status="draft", created_by="admin", updated_by="admin", target_all_clients=True, image_reference=old.name, image_content_type="image/png")
            db = FailingCommitDB(item)
            settings = SimpleNamespace(CAMPAIGN_MEDIA_ROOT=root, CAMPAIGN_MAX_IMAGE_BYTES=1024)
            with patch("routers.campaigns.get_settings", return_value=settings):
                with self.assertRaises(HTTPException) as raised:
                    await campaigns.upload_image(3, upload("new.png", "image/png", b"\x89PNG\r\n\x1a\nnew"), {"username":"admin"}, db)
            self.assertEqual(raised.exception.status_code, 500)
            self.assertTrue(old.exists())
            self.assertTrue(db.rolled_back)
            self.assertEqual([p.name for p in Path(root).iterdir()], ["old.png"])
        with tempfile.TemporaryDirectory() as root:
            asyncio.run(scenario(root))

    def test_client_script_marks_read_only_after_detail_load(self):
        script = (ROOT / "app/static/campaigns-client.js").read_text()
        detail_fetch = script.index('fetch("/api/portal/campaigns/"+id,{credentials:"include"})')
        read_fetch = script.index('fetch("/api/portal/campaigns/"+id+"/read"')
        self.assertLess(detail_fetch, read_fetch)
        self.assertNotIn("innerHTML", script)

    def test_navigation_and_management_contracts(self):
        portal = (ROOT / "app/routers/portal.py").read_text()
        page = (ROOT.parent / "frontend/src/pages/Campaigns.jsx").read_text()
        layout = (ROOT.parent / "frontend/src/components/Layout.jsx").read_text()
        self.assertIn("What’s New", portal)
        self.assertIn("campaign-unread-desktop", portal)
        self.assertIn('label: "Campaigns"', layout)
        for label in ("Create campaign", "Preview", "Publish", "Unpublish", "Archive", "Delete draft", "Selected clients"):
            self.assertIn(label, page)


if __name__ == "__main__":
    unittest.main()
