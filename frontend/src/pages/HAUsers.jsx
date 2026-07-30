import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshCw, ShieldCheck, Users } from "lucide-react";
import { Card, EmptyState, ErrorState, LoadingState, PageHeader, StatusBadge } from "../components/ui";

const messages = {
  permission_required: "Permission required: the Home Assistant token must belong to an administrator.",
  unsupported: "Not supported by this Agent or Home Assistant version.",
  authentication_required: "A Home Assistant token is required in the Agent configuration.",
  authentication_failed: "The configured Home Assistant token was rejected.",
  malformed_response: "Home Assistant returned an unsupported user-list response.",
  timeout: "The refresh timed out. The last successful inventory is still shown.",
  unavailable: "Home Assistant or the Agent is currently unavailable. The last successful inventory is still shown.",
};

const date = value => value
  ? new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium", timeStyle: "short", timeZone: "Africa/Johannesburg",
    }).format(new Date(value))
  : "Never";

const role = user => user.is_owner ? "Owner" : user.is_admin ? "Administrator" : "User";

const provider = user => {
  if (!user.credential_providers?.length) return "Unavailable";
  return user.credential_providers
    .map(value => value === "homeassistant" ? "Home Assistant local" : value.replaceAll("_", " "))
    .join(", ");
};

export default function HAUsers() {
  const [clients, setClients] = useState([]);
  const [clientId, setClientId] = useState("");
  const [inventory, setInventory] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetch("/api/clients", { credentials: "include" })
      .then(response => {
        if (!response.ok) throw new Error("Unable to load clients");
        return response.json();
      })
      .then(data => {
        setClients(data);
        if (data.length) setClientId(String(data[0].id));
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const loadInventory = useCallback(async (preserveError = false) => {
    if (!clientId) return;
    try {
      const response = await fetch(`/api/ha-users/clients/${clientId}`, { credentials: "include" });
      if (!response.ok) throw new Error("Unable to load Home Assistant users");
      const data = await response.json();
      setInventory(data);
      setRefreshing(["pending", "claimed"].includes(data.request?.state));
      if (!preserveError) setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, [clientId]);

  useEffect(() => {
    setInventory(null);
    setError(null);
    setRefreshing(false);
    loadInventory();
  }, [loadInventory]);

  useEffect(() => {
    if (!refreshing) return undefined;
    const interval = setInterval(() => loadInventory(true), 1500);
    return () => clearInterval(interval);
  }, [loadInventory, refreshing]);

  const refresh = async () => {
    if (!clientId || !inventory?.ha_users_read || refreshing) return;
    setError(null);
    setRefreshing(true);
    try {
      const response = await fetch(`/api/ha-users/clients/${clientId}/refresh`, {
        method: "POST", credentials: "include",
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail || "Unable to request refresh");
      }
      await loadInventory();
    } catch (err) {
      setError(err.message);
      setRefreshing(false);
    }
  };

  const users = useMemo(() => inventory?.users || [], [inventory]);

  if (loading) return <LoadingState />;
  if (error && !inventory) return <ErrorState error={error} />;

  return <div className="space-y-6">
    <PageHeader
      title="Home Assistant Users"
      subtitle="Read-only account inventory from the selected client installation."
    />
    <Card compact>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <label className="block min-w-0 flex-1 text-sm text-gray-300">
          Client
          <select value={clientId} onChange={event => setClientId(event.target.value)}
            className="mt-2 w-full rounded-xl border border-white/10 bg-gray-950 px-3 py-2.5 text-white sm:max-w-md">
            {clients.map(client => <option key={client.id} value={client.id}>{client.name}</option>)}
          </select>
        </label>
        <button type="button" onClick={refresh}
          disabled={!inventory?.ha_users_read || refreshing}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-primary/80 disabled:cursor-not-allowed disabled:opacity-50">
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "Refreshing…" : "Refresh"}
        </button>
      </div>
      <p className="mt-3 text-sm text-gray-500">
        Last successful refresh: {date(inventory?.refreshed_at)}
      </p>
    </Card>

    {!inventory?.ha_users_read ? (
      <Card>
        <div className="flex items-start gap-3">
          <Users className="mt-0.5 h-5 w-5 text-gray-400" />
          <div>
            <h2 className="font-semibold text-white">Not supported</h2>
            <p className="mt-1 text-sm text-gray-400">
              This installation has not advertised read-only Home Assistant user inventory.
              Older Agents continue reporting normally.
            </p>
          </div>
        </div>
      </Card>
    ) : (
      <>
        {(error || inventory.last_error_code) && (
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
            {error || messages[inventory.last_error_code] || "The latest refresh was unavailable."}
          </div>
        )}
        {users.length === 0 ? (
          <EmptyState>No Home Assistant users have been retrieved yet. Select Refresh to request an inventory.</EmptyState>
        ) : (
          <Card className="overflow-hidden" compact>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-white/10 text-left text-sm">
                <thead className="bg-white/[0.03] text-xs uppercase tracking-wide text-gray-500">
                  <tr>
                    <th className="px-4 py-3">Name</th><th className="px-4 py-3">Username</th>
                    <th className="px-4 py-3">Role</th><th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Login / provider type</th><th className="px-4 py-3">System user</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/10">
                  {users.map(user => <tr key={user.id}>
                    <td className="px-4 py-3">
                      <div className="font-medium text-white">{user.name || "Unavailable"}</div>
                      <div className="mt-1 font-mono text-xs text-gray-500">{user.id}</div>
                    </td>
                    <td className="px-4 py-3 text-gray-300">{user.username || "Unavailable"}</td>
                    <td className="px-4 py-3"><div className="flex items-center gap-2 text-white">
                      {(user.is_owner || user.is_admin) && <ShieldCheck className="h-4 w-4 text-purple-300" />}{role(user)}
                    </div></td>
                    <td className="px-4 py-3"><StatusBadge status={user.is_active ? "active" : "inactive"}>
                      {user.is_active ? "Active" : "Inactive"}
                    </StatusBadge></td>
                    <td className="px-4 py-3 text-gray-300"><div>{provider(user)}</div>
                      {user.local_only && <div className="mt-1 text-xs text-gray-500">Local access only</div>}
                    </td>
                    <td className="px-4 py-3 text-gray-300">{user.system_generated ? "System generated" : "No"}</td>
                  </tr>)}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </>
    )}
  </div>;
}
