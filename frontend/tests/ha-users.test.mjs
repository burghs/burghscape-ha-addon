import assert from "node:assert/strict";
import fs from "node:fs";

const source = fs.readFileSync(new URL("../src/pages/HAUsers.jsx", import.meta.url), "utf8");
for (const contract of [
  "Home Assistant Users", "Last successful refresh:", "Not supported", "Permission required:",
  "Older Agents continue reporting normally.", 'user.username || "Unavailable"',
  'user.is_owner ? "Owner" : user.is_admin ? "Administrator" : "User"',
  'user.is_active ? "Active" : "Inactive"', "System generated",
  "credential_providers", "Local access only", "setInventory(data)",
]) assert.ok(source.includes(contract), `missing HA users UI contract: ${contract}`);

for (const forbidden of [
  "Reset password", "Create user", "Delete user", "Disable user",
  "Enable user", "Force logout", "MFA", "Last login",
]) assert.ok(!source.includes(forbidden), `destructive or unsupported control present: ${forbidden}`);

assert.ok(source.includes('method: "POST"'));
assert.ok(!source.includes('method: "DELETE"'));
assert.ok(!source.includes('method: "PUT"'));
console.log("read-only Home Assistant user UI contracts passed");
