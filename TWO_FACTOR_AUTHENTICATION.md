# Client two-factor authentication — Phase 1

## Scope and standard

MyBeacon supports optional RFC 6238 TOTP for client portal users. It works with standard authenticator applications that accept an `otpauth://totp` URI, including Google Authenticator, Microsoft Authenticator, 1Password, Authy, and compatible password managers. Enrollment is never forced.

Excluded from Phase 1: email OTP, SMS, trusted devices, passkeys, forced enrollment, and session-management UI. Administrator authentication is unchanged and does not use this client TOTP flow.

## Authentication flow

The existing salted password check runs first. Users without TOTP receive the existing portal session response. A TOTP-enabled user receives no full session after password verification; the server stores a five-minute, hashed, single-use challenge and sets an HttpOnly/Secure/SameSite=Lax challenge cookie. A valid current TOTP or unused recovery code invalidates the challenge and creates a fresh, rotated portal session. Expired, used, reset, inactive-user, malformed, and over-attempted challenges fail closed.

## Enrollment

Open Client Portal → Account & Support → Account Security. Enter the current password, then scan the locally generated SVG QR code or enter the manual key. The issuer is `MyBeacon by Burghscape` and the account label is the portal email address. Pending enrollment expires after ten minutes and cancellation leaves TOTP disabled. The secret is encrypted before database storage and is not returned after verification.

Ten recovery codes are generated after successful verification and displayed once. The client must acknowledge saving them in the UI. Database records contain only independently salted PBKDF2-SHA256 hashes. Codes are single-use; regeneration invalidates every previous code.

## Login and lost-device recovery

After the password, enter the current six-digit authenticator code. Select “Use a recovery code” when the authenticator is unavailable. A recovery code can succeed once. Support must never request an authenticator secret or recovery code.

If all factors are lost, an authorized administrator may use Reset Two-Factor Authentication in Management Portal → Clients → Portal Users. A reason and explicit confirmation are required. The reset removes the encrypted secret, recovery hashes, pending enrollment, and active challenges, and records administrator, affected user/client, time, reason, IP address, and user agent. It creates no bypass code. The client returns to password-only login until voluntarily re-enrolling.

## Client disable

A logged-in client may disable TOTP only with the current password plus a current TOTP or unused recovery code and explicit confirmation. Password alone is insufficient. The current authenticated portal session is preserved; all second-factor material and pending challenges are invalidated.

## Encryption-key management

`TOTP_ENCRYPTION_KEY` is a Fernet key: 32 random bytes encoded with URL-safe base64. It is stored persistently in `/home/kenny/burghscape/.env`, never committed, logged, returned by an API, or regenerated during deployment. Both application startup and `deploy_platform.sh` validate it. A missing or malformed key prevents startup/deployment.

Generate once with:

```bash
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Back up the key using the same protected secret-management process as other production credentials. Losing it makes enrolled TOTP secrets undecryptable; restoring the database without the matching key requires administrator resets for enrolled accounts.

## Migration and rollback

Apply `backend/migrations/20260723_add_client_totp.sql`. It adds nullable secret/timestamp fields, a disabled-by-default flag, recovery codes, pending enrollment, challenges, and security audit tables. It does not alter passwords or existing sessions and does not enroll existing users.

Before rollback, disable or administratively reset every enrolled user. Application rollback while enrolled users remain enabled is unsafe because older code would ignore the second-factor flag and accept password-only login. Retain the additive columns/tables and audit history during an application rollback; do not drop them. Restore the previous application only after all `two_factor_enabled` values are false. Database backups must be paired with the persistent encryption key.

## Rate limits and operational notes

TOTP/recovery challenge attempts, enrollment verification, recovery regeneration, client disable, and administrator reset have separate short-window limits. Generic challenge failures avoid exposing account state. Existing password login behavior and its current controls are unchanged.

Portal sessions and password-reset tokens remain process-memory state in the current architecture. This pre-existing limitation is not expanded by Phase 1. TOTP challenges themselves are database-backed so refresh and process restart do not turn them into authenticated sessions.

## Acceptance status

Automated tests do not complete real-device acceptance. Do not mark Phase 1 COMPLETE until a controlled client scans the QR code with a real authenticator, completes TOTP and one-time recovery login, self-disables, re-enrolls, receives an audited administrator reset, and confirms unrelated portal features remain healthy without secrets in logs.
