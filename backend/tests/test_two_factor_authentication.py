import asyncio
from datetime import datetime, timedelta
import os
import sys
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

import pyotp
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException, Response
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request

from database import Base
from models import (Client, ClientStatus, ClientUser, SecurityAuditEvent,
                    TwoFactorChallenge, TwoFactorPendingEnrollment, TwoFactorRecoveryCode)
from routers import portal_users, two_factor
from routers.portal_state import portal_sessions
from two_factor_security import decrypt_secret, token_hash, validate_encryption_key


def request(cookie_name=None, cookie_value=None):
    headers = []
    if cookie_name:
        headers.append((b"cookie", f"{cookie_name}={cookie_value}".encode()))
    return Request({"type": "http", "method": "POST", "path": "/", "headers": headers,
                    "client": ("127.0.0.1", 1234)})


def cookie_value(response, name):
    for value in response.headers.getlist("set-cookie"):
        if value.startswith(name + "="):
            return unquote(value.split(";", 1)[0].split("=", 1)[1])
    return None


class TwoFactorAuthenticationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from config import get_settings
        cls.key = Fernet.generate_key().decode()
        get_settings().TOTP_ENCRYPTION_KEY = cls.key
        validate_encryption_key()

    def setUp(self):
        portal_sessions.clear()
        two_factor._attempts.clear()

    def run_flow(self, callback):
        async def run():
            engine = create_async_engine("sqlite+aiosqlite:///:memory:")
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            sessions = async_sessionmaker(engine, expire_on_commit=False)
            try:
                async with sessions() as db:
                    client = Client(name="TOTP Test", email="client@example.test", subdomain="totp-test", status=ClientStatus.ACTIVE)
                    db.add(client)
                    await db.flush()
                    user = ClientUser(client_id=client.id, name="Test User", email="user@example.test",
                                      password_hash=portal_users.hash_password("Password123!"),
                                      force_password_change=False, is_active=True)
                    db.add(user)
                    await db.commit()
                    await callback(db, user)
            finally:
                await engine.dispose()
        asyncio.run(run())

    def test_existing_disabled_user_login_is_unchanged(self):
        async def flow(db, user):
            response = Response()
            result = await portal_users.portal_login(
                portal_users.PortalLogin(email=user.email, password="Password123!"), response, db)
            self.assertIn("token", result)
            self.assertNotIn("requires_two_factor", result)
            self.assertEqual(portal_sessions[result["token"]], user.id)
            with self.assertRaises(HTTPException):
                await portal_users.portal_login(
                    portal_users.PortalLogin(email=user.email, password="wrong"), Response(), db)
        self.run_flow(flow)

    def test_enrollment_qr_secret_storage_and_login_challenge(self):
        async def flow(db, user):
            portal_sessions["existing"] = user.id
            started = await two_factor.start_enrollment(
                two_factor.PasswordRequest(current_password="Password123!"),
                request("portal_token", "existing"), db)
            self.assertEqual(started["issuer"], "MyBeacon by Burghscape")
            self.assertTrue(started["otpauth_uri"].startswith("otpauth://totp/"))
            self.assertTrue(started["qr_code"].startswith("data:image/svg+xml;base64,"))
            secret = started["manual_key"]
            completed = await two_factor.confirm_enrollment(
                two_factor.EnrollmentVerify(code=pyotp.TOTP(secret).now()),
                request("portal_token", "existing"), db)
            self.assertTrue(completed["enabled"])
            self.assertEqual(len(completed["recovery_codes"]), 10)
            await db.commit()
            self.assertTrue(user.two_factor_enabled)
            self.assertNotEqual(user.encrypted_totp_secret, secret)
            self.assertEqual(decrypt_secret(user.encrypted_totp_secret), secret)
            stored = (await db.execute(select(TwoFactorRecoveryCode))).scalars().all()
            self.assertEqual(len(stored), 10)
            for code in completed["recovery_codes"]:
                self.assertNotIn(code, " ".join(row.code_hash for row in stored))

            login_response = Response()
            login = await portal_users.portal_login(
                portal_users.PortalLogin(email=user.email, password="Password123!"), login_response, db)
            self.assertEqual(login, {"requires_two_factor": True, "challenge_url": "/portal/two-factor"})
            raw = cookie_value(login_response, "portal_2fa_challenge")
            self.assertTrue(raw)
            self.assertNotIn(raw, portal_sessions)
            verify_response = Response()
            verified = await two_factor.verify_challenge(
                two_factor.FactorRequest(code=pyotp.TOTP(secret).now()),
                request("portal_2fa_challenge", raw), verify_response, db)
            self.assertTrue(verified["verified"])
            session = cookie_value(verify_response, "portal_token")
            self.assertTrue(session and session != raw)
            self.assertEqual(portal_sessions[session], user.id)
            with self.assertRaises(HTTPException):
                await two_factor.verify_challenge(two_factor.FactorRequest(code=pyotp.TOTP(secret).now()),
                                                  request("portal_2fa_challenge", raw), Response(), db)
        self.run_flow(flow)

    def test_pending_enrollment_expiry_and_cancel_leave_disabled(self):
        async def flow(db, user):
            portal_sessions["existing"] = user.id
            started = await two_factor.start_enrollment(two_factor.PasswordRequest(current_password="Password123!"), request("portal_token", "existing"), db)
            pending = (await db.execute(select(TwoFactorPendingEnrollment))).scalars().one()
            pending.expires_at = datetime.utcnow() - timedelta(seconds=1)
            with self.assertRaises(HTTPException):
                await two_factor.confirm_enrollment(two_factor.EnrollmentVerify(code=pyotp.TOTP(started["manual_key"]).now()), request("portal_token", "existing"), db)
            self.assertFalse(user.two_factor_enabled)
            await two_factor.start_enrollment(two_factor.PasswordRequest(current_password="Password123!"), request("portal_token", "existing"), db)
            result = await two_factor.cancel_enrollment(request("portal_token", "existing"), db)
            self.assertFalse(result["enabled"])
            self.assertFalse((await db.execute(select(TwoFactorPendingEnrollment))).scalars().all())
        self.run_flow(flow)

    def test_recovery_regeneration_invalidates_previous_codes(self):
        async def flow(db, user):
            portal_sessions["existing"] = user.id
            started = await two_factor.start_enrollment(two_factor.PasswordRequest(current_password="Password123!"), request("portal_token", "existing"), db)
            enabled = await two_factor.confirm_enrollment(two_factor.EnrollmentVerify(code=pyotp.TOTP(started["manual_key"]).now()), request("portal_token", "existing"), db)
            old_code = enabled["recovery_codes"][0]
            regenerated = await two_factor.regenerate_codes(two_factor.RegenerateRequest(current_password="Password123!", code=pyotp.TOTP(started["manual_key"]).now()), request("portal_token", "existing"), db)
            self.assertEqual(len(regenerated["recovery_codes"]), 10)
            login_response = Response()
            await portal_users.portal_login(portal_users.PortalLogin(email=user.email, password="Password123!"), login_response, db)
            with self.assertRaises(HTTPException):
                await two_factor.verify_challenge(two_factor.FactorRequest(code=old_code, recovery_code=True), request("portal_2fa_challenge", cookie_value(login_response, "portal_2fa_challenge")), Response(), db)
        self.run_flow(flow)

    def test_invalid_expired_and_skewed_totp_fail(self):
        async def flow(db, user):
            portal_sessions["existing"] = user.id
            started = await two_factor.start_enrollment(two_factor.PasswordRequest(current_password="Password123!"), request("portal_token", "existing"), db)
            with self.assertRaises(HTTPException):
                await two_factor.confirm_enrollment(two_factor.EnrollmentVerify(code="000000"), request("portal_token", "existing"), db)
            secret = started["manual_key"]
            await two_factor.confirm_enrollment(two_factor.EnrollmentVerify(code=pyotp.TOTP(secret).now()), request("portal_token", "existing"), db)
            login_response = Response()
            await portal_users.portal_login(portal_users.PortalLogin(email=user.email, password="Password123!"), login_response, db)
            raw = cookie_value(login_response, "portal_2fa_challenge")
            skewed = pyotp.TOTP(secret).at(datetime.now() - timedelta(minutes=3))
            with self.assertRaises(HTTPException):
                await two_factor.verify_challenge(two_factor.FactorRequest(code=skewed), request("portal_2fa_challenge", raw), Response(), db)
            challenge = (await db.execute(select(TwoFactorChallenge).where(TwoFactorChallenge.token_hash == token_hash(raw)))).scalars().one()
            challenge.expires_at = datetime.utcnow() - timedelta(seconds=1)
            with self.assertRaises(HTTPException):
                await two_factor.verify_challenge(two_factor.FactorRequest(code=pyotp.TOTP(secret).now()), request("portal_2fa_challenge", raw), Response(), db)
        self.run_flow(flow)

    def test_recovery_single_use_disable_and_admin_reset_audit(self):
        async def flow(db, user):
            portal_sessions["existing"] = user.id
            started = await two_factor.start_enrollment(two_factor.PasswordRequest(current_password="Password123!"), request("portal_token", "existing"), db)
            enabled = await two_factor.confirm_enrollment(two_factor.EnrollmentVerify(code=pyotp.TOTP(started["manual_key"]).now()), request("portal_token", "existing"), db)
            recovery = enabled["recovery_codes"][0]
            login_response = Response()
            await portal_users.portal_login(portal_users.PortalLogin(email=user.email, password="Password123!"), login_response, db)
            raw = cookie_value(login_response, "portal_2fa_challenge")
            await two_factor.verify_challenge(two_factor.FactorRequest(code=recovery, recovery_code=True), request("portal_2fa_challenge", raw), Response(), db)
            login_response2 = Response()
            await portal_users.portal_login(portal_users.PortalLogin(email=user.email, password="Password123!"), login_response2, db)
            with self.assertRaises(HTTPException):
                await two_factor.verify_challenge(two_factor.FactorRequest(code=recovery, recovery_code=True), request("portal_2fa_challenge", cookie_value(login_response2, "portal_2fa_challenge")), Response(), db)
            await two_factor.disable(two_factor.DisableRequest(current_password="Password123!", code=pyotp.TOTP(started["manual_key"]).now(), recovery_code=False, confirm=True), request("portal_token", "existing"), db)
            self.assertFalse(user.two_factor_enabled)
            self.assertIsNone(user.encrypted_totp_secret)
            self.assertFalse((await db.execute(select(TwoFactorRecoveryCode))).scalars().all())

            # Re-enable, then prove administrator reset invalidates state and records reason.
            started2 = await two_factor.start_enrollment(two_factor.PasswordRequest(current_password="Password123!"), request("portal_token", "existing"), db)
            await two_factor.confirm_enrollment(two_factor.EnrollmentVerify(code=pyotp.TOTP(started2["manual_key"]).now()), request("portal_token", "existing"), db)
            reset = await two_factor.admin_reset(user.id, two_factor.AdminResetRequest(confirm=True, reason="Lost client device"), request(), {"username": "admin", "role": "superadmin"}, db)
            self.assertTrue(reset["audit_recorded"])
            self.assertFalse(user.two_factor_enabled)
            audit = (await db.execute(select(SecurityAuditEvent).where(SecurityAuditEvent.action == "two_factor_admin_reset"))).scalars().one()
            self.assertEqual(audit.reason, "Lost client device")
            response = Response()
            result = await portal_users.portal_login(portal_users.PortalLogin(email=user.email, password="Password123!"), response, db)
            self.assertIn("token", result)
        self.run_flow(flow)

    def test_admin_reset_requires_auth_confirmation_and_reason(self):
        app = FastAPI()
        app.include_router(two_factor.router)
        client = TestClient(app)
        self.assertEqual(client.post("/api/portal/admin/portal-users/1/two-factor/reset", json={"confirm": True, "reason": "Lost device"}).status_code, 401)
        with self.assertRaises(Exception):
            two_factor.AdminResetRequest(confirm=True, reason="no")
        self.assertFalse(two_factor.AdminResetRequest(confirm=False, reason="Valid support reason").confirm)

    def test_client_and_admin_ui_security_contracts(self):
        router_source = (ROOT / "app/routers/two_factor.py").read_text()
        portal_source = (ROOT / "app/routers/portal.py").read_text()
        admin_source = (ROOT.parent / "frontend/src/pages/Clients.jsx").read_text()
        for value in ("account-security-heading", "Two-Factor Authentication", "account-two-factor-status", "Enable two-factor authentication", "refreshAccountSecurity", "/api/portal/security/two-factor", 'href="/portal/security"'):
            self.assertIn(value, portal_source)
        account_panel = portal_source[portal_source.index('id="pw-form-nav"'):portal_source.index('</nav>')]
        self.assertIn("Theme", account_panel)
        self.assertIn("Change password", account_panel)
        self.assertIn("Security", account_panel)
        login_page = portal_source[portal_source.index('LOGIN_HTML ='):]
        self.assertNotIn("Enable two-factor authentication", login_page)
        for value in ("autocomplete=\"one-time-code\"", "Use a recovery code", "locally generated QR code", "I have saved these recovery codes"):
            self.assertIn(value, router_source)
        for value in ("Reset 2FA", "reason.trim().length < 5", "Two-factor reset audit"):
            self.assertIn(value, admin_source)
        self.assertNotIn("logger.", router_source)
        self.assertNotIn("external QR", router_source)

    def test_missing_or_invalid_encryption_key_fails_closed(self):
        from config import get_settings
        original = get_settings().TOTP_ENCRYPTION_KEY
        try:
            for value in ("", "not-a-fernet-key"):
                get_settings().TOTP_ENCRYPTION_KEY = value
                with self.assertRaises(RuntimeError):
                    validate_encryption_key()
        finally:
            get_settings().TOTP_ENCRYPTION_KEY = original

    def test_migration_is_additive_and_defaults_existing_users_disabled(self):
        sql = (ROOT / "migrations/20260723_add_client_totp.sql").read_text()
        self.assertIn("ADD COLUMN IF NOT EXISTS two_factor_enabled BOOLEAN NOT NULL DEFAULT FALSE", sql)
        self.assertNotIn("DROP TABLE", sql.upper())
        self.assertNotIn("DROP COLUMN", sql.upper())


if __name__ == "__main__":
    unittest.main()
