import assert from "node:assert/strict";
import fs from "node:fs";

const source = fs.readFileSync(new URL("../src/pages/Clients.jsx", import.meta.url), "utf8");
for (const contract of [
  "Two-Factor Authentication",
  "Status: {user.two_factor_enabled ? 'Enabled' : 'Disabled'}",
  "Reset two-factor authentication",
  "reason.length < 5",
  "twoFactorResetConfirmed",
  "all recovery codes will be invalidated",
  "client will return to password-only login",
  "setPortalUsers(current => current.map",
  "fetchPortalUsers();",
]) assert.ok(source.includes(contract), `missing admin 2FA contract: ${contract}`);
assert.ok(source.includes("user.two_factor_enabled && <button"), "reset must only render for enabled users");
assert.ok(source.includes("disabled={twoFactorResetLoading || !twoFactorResetConfirmed || twoFactorResetReason.trim().length < 5}"));
console.log("admin two-factor UI contracts passed");
