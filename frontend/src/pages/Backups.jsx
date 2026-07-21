import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, EmptyState, ErrorState, LiveStatus, LoadingState, PageHeader, StatusBadge } from "../components/ui";

export const formatSize = bytes => !bytes ? "Unknown" : bytes >= 1073741824 ? `${(bytes / 1073741824).toFixed(1)} GB` : `${(bytes / 1048576).toFixed(1)} MB`;
export const formatBackupDate = value => value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "Africa/Johannesburg" }).format(new Date(value)) : "Unknown";
export const platformBackupSummary = backups => {
  const items = [...backups].sort((a, b) => new Date(b.created_at || b.date || 0) - new Date(a.created_at || a.date || 0));
  return { items, count: items.length, totalBytes: items.reduce((sum, item) => sum + (item.size_bytes || 0), 0), latest: items[0] || null };
};
const platformDescription = backup => {
  const raw = backup.type || backup.name || "Platform backup";
  if (raw.includes("PostgreSQL + Config + Source")) return "PostgreSQL + Config + Source";
  if (/frontend/i.test(raw)) return "Frontend Static Backup";
  if (/config/i.test(raw)) return "Configuration Backup";
  return raw.replace(/^Server Backup\s*\(|\)$/g, "") || "Platform backup";
};

export default function Backups() {
  const [server, setServer] = useState([]);
  const [states, setStates] = useState([]);
  const [managed, setManaged] = useState([]);
  const [expanded, setExpanded] = useState({});
  const [platformOpen, setPlatformOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const load = useCallback(async () => {
    try {
      const [serverResponse, managedResponse] = await Promise.all([
        fetch("/api/admin/backups", { credentials: "include" }),
        fetch("/api/admin/managed-backup-state", { credentials: "include" }),
      ]);
      if (!serverResponse.ok || !managedResponse.ok) throw new Error("Unable to load backups");
      const serverData = await serverResponse.json();
      const managedData = await managedResponse.json();
      setServer(serverData.backups || []);
      setStates(managedData.clients || []);
      setManaged(managedData.backups || []);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  const groups = useMemo(() => {
    const result = {};
    for (const backup of managed) {
      const key = `${backup.client_name}::${backup.instance_name}`;
      if (!result[key]) result[key] = { client: backup.client_name, instance: backup.instance_name, items: [] };
      result[key].items.push(backup);
    }
    return Object.entries(result);
  }, [managed]);
  const platform = useMemo(() => platformBackupSummary(server), [server]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return <div>
    <PageHeader title="Backups" subtitle="Home Assistant customer archives and platform server backups are kept separate." meta={<LiveStatus lastUpdated={lastUpdated} />} />
    <section aria-labelledby="ha-backups">
      <h2 id="ha-backups" className="mb-3 text-lg font-semibold text-white">Home Assistant Backups</h2>
      <div className="space-y-3">
        {groups.length === 0 ? <EmptyState>No completed managed backups stored.</EmptyState> : groups.map(([key, group]) => {
          const state = states.find(item => item.client_name === group.client);
          const total = group.items.reduce((sum, item) => sum + (item.size_bytes || 0), 0);
          const open = !!expanded[key];
          return <Card key={key} compact>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div><p className="font-semibold text-white">{group.client}</p><p className="text-purple-300">{group.instance}</p>
                <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                  <span className="text-gray-500">Last successful backup</span><span className="text-white">{formatBackupDate(group.items[0]?.completed_at)}</span>
                  <span className="text-gray-500">Stored backups</span><span className="text-white">{group.items.length}</span>
                  <span className="text-gray-500">Storage used</span><span className="text-white">{formatSize(total)}</span>
                  <span className="text-gray-500">Status</span><StatusBadge status={state?.current_operation?.state || "completed"}>{state?.current_operation?.state || "Protected"}</StatusBadge>
                </div>
              </div>
              <Button variant="secondary" onClick={() => setExpanded({ ...expanded, [key]: !open })}>{open ? "Hide backups" : "View backups"}</Button>
            </div>
            {open && <div className="mt-5 space-y-2 border-t border-white/10 pt-4">
              {group.items.map(backup => <div key={backup.download_url} className="flex flex-col gap-3 rounded-lg bg-black/20 p-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0"><p className="break-words font-medium text-white">{group.instance} — {formatBackupDate(backup.completed_at)}</p><p className="mt-1 text-sm text-gray-500">Successful · {formatSize(backup.size_bytes)} · {backup.backup_type}</p></div>
                <Button as="a" href={backup.download_url} download>Download</Button>
              </div>)}
            </div>}
          </Card>;
        })}
      </div>
    </section>

    <section aria-labelledby="server-backups" className="mt-8">
      <h2 id="server-backups" className="mb-3 text-lg font-semibold text-white">Platform Server Backups</h2>
      {platform.count === 0 ? <EmptyState>No platform server backups recorded.</EmptyState> : <Card compact>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div><p className="text-lg font-semibold text-white">Burghscape Platform</p>
            <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <span className="text-gray-500">Last successful backup</span><span className="text-white">{formatBackupDate(platform.latest?.created_at || platform.latest?.date)}</span>
              <span className="text-gray-500">Stored backups</span><span className="text-white">{platform.count}</span>
              <span className="text-gray-500">Storage used</span><span className="text-white">{formatSize(platform.totalBytes)}</span>
              <span className="text-gray-500">Status</span><StatusBadge status={platform.latest?.status || "available"}>{platform.latest?.status || "Available"}</StatusBadge>
            </div>
          </div>
          <Button variant="secondary" onClick={() => setPlatformOpen(!platformOpen)}>{platformOpen ? "Hide backups" : "View backups"}</Button>
        </div>
        {platformOpen && <div className="mt-5 space-y-2 border-t border-white/10 pt-4">
          {platform.items.map((backup, index) => <div key={backup.download_url || index} className="flex flex-col gap-3 rounded-lg bg-black/20 p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0"><p className="break-words font-medium text-white">{platformDescription(backup)}</p><p className="mt-1 break-all text-sm text-gray-500">{formatBackupDate(backup.created_at || backup.date)} · {formatSize(backup.size_bytes)} · {backup.status || "Available"}{backup.filename ? ` · ${backup.filename}` : ""}</p></div>
            {backup.download_url && <Button as="a" href={backup.download_url} download>Download</Button>}
          </div>)}
        </div>}
      </Card>}
    </section>
  </div>;
}
