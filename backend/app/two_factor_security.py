"""Focused security helpers for optional client TOTP authentication."""
import base64
import hashlib
import hmac
import secrets
from io import BytesIO

import pyotp
import qrcode
import qrcode.image.svg
from cryptography.fernet import Fernet, InvalidToken

from config import get_settings

ISSUER = "MyBeacon by Burghscape"
RECOVERY_CODE_COUNT = 10


def _fernet() -> Fernet:
    value = get_settings().TOTP_ENCRYPTION_KEY.strip().encode()
    if not value:
        raise RuntimeError("TOTP_ENCRYPTION_KEY is required")
    try:
        key = base64.urlsafe_b64decode(value)
        if len(key) != 32:
            raise ValueError
        return Fernet(value)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("TOTP_ENCRYPTION_KEY must be a valid Fernet key") from exc


def validate_encryption_key() -> None:
    fernet = _fernet()
    probe = fernet.encrypt(b"totp-key-validation")
    if fernet.decrypt(probe) != b"totp-key-validation":
        raise RuntimeError("TOTP_ENCRYPTION_KEY validation failed")


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Stored TOTP secret cannot be decrypted") from exc


def new_totp_secret() -> str:
    return pyotp.random_base32()


def provisioning_uri(secret: str, account: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=account, issuer_name=ISSUER)


def qr_svg_data_uri(uri: str) -> str:
    image = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    output = BytesIO()
    image.save(output)
    return "data:image/svg+xml;base64," + base64.b64encode(output.getvalue()).decode()


def verify_totp(secret: str, code: str) -> bool:
    return bool(code.isdigit() and len(code) == 6 and pyotp.TOTP(secret).verify(code, valid_window=1))


def new_recovery_codes() -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return ["".join(secrets.choice(alphabet) for _ in range(4)) + "-" + "".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(RECOVERY_CODE_COUNT)]


def normalize_recovery_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def hash_recovery_code(code: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", normalize_recovery_code(code).encode(), salt, 210_000)
    return base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def verify_recovery_code(code: str, stored: str) -> bool:
    try:
        salt_raw, expected_raw = stored.split("$", 1)
        salt = base64.urlsafe_b64decode(salt_raw.encode())
        expected = base64.urlsafe_b64decode(expected_raw.encode())
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", normalize_recovery_code(code).encode(), salt, 210_000)
    return hmac.compare_digest(actual, expected)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
