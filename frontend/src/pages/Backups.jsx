import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, EmptyState, ErrorState, LiveStatus, LoadingState, Modal, PageHeader, ProgressBar, StatusBadge } from "../components/ui";

export const formatSize = bytes => bytes == null ? "Unknown" : bytes >= 1073741824 ? `${(bytes / 1073741824).toFixed(1)} GB` : bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${(bytes / 1024).toFixed(1)} KB`;
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
const toneForHealth = health => health === "healthy" ? "success" : health === "attention" ? "info" : health === "warning" ? "warning" : "danger";

export default function Backups() {
  const [server, setServer] = useState([]);
  const [states, setStates] = useState([]);
  const [managed, setManaged] = useState([]);
  const [storage, setStorage] = useState(null);
  const [expanded, setExpanded] = useState({});
  const [platformOpen, setPlatformOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const load = useCallback(async () => {
    try {
      const [serverResponse, managedResponse, storageResponse] = await Promise.all([
        fetch("/api/admin/backups", { credentials: "include" }),
        fetch("/api/admin/managed-backup-state", { credentials: "include" }),
        fetch("/api/admin/backup-storage", { credentials: "include" }),
      ]);
      if (!serverResponse.ok || !managedResponse.ok || !storageResponse.ok) throw new Error("Unable to load backups");
      const [serverData, managedData, storageData] = await Promise.all([serverResponse.json(), managedResponse.json(), storageResponse.json()]);
      setServer(serverData.backups || []);
      setStates(managedData.clients || []);
      setManaged(managedData.backups || []);
      setStorage(storageData);
      setLastUpdated(new Date());
      setError(null);
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
    const itemsByClient = managed.reduce((result, backup) => {
      (result[backup.client_id] ||= []).push(backup);
      return result;
    }, {});
    return (storage?.groups || []).map(group => ({ ...group, items: itemsByClient[group.client_id] || [] }));
  }, [managed, storage]);
  const platform = useMemo(() => platformBackupSummary(server), [server]);

  const removeBackup = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setFeedback(null);
    try {
      const response = await fetch(`/api/admin/managed-backups/${deleteTarget.id}`, { method: "DELETE", credentials: "include" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "Backup deletion failed");
      const clientId = deleteTarget.client_id;
      setDeleteTarget(null);
      setExpanded(current => ({ ...current, [clientId]: true }));
      setFeedback({ message: `Backup deleted. ${formatSize(payload.recovered_bytes)} recovered.`, error: false });
      await load();
    } catch (err) {
      setFeedback({ message: err.message, error: true });
    } finally {
      setDeleting(false);
    }
  };

  if (loading) return <LoadingState />;
  if (error && !storage) return <ErrorState error={error} />;

  const volume = storage?.volumes?.[0];
  return <div>
    <PageHeader title="Backups" subtitle="Home Assistant customer archives and platform server backups are kept separate." meta={<LiveStatus lastUpdated={lastUpdated} />} />

    <Card compact className="mb-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div><h2 className="text-lg font-semibold text-white">Backup Storage</h2>
          {storage?.available && volume ? <><div className="mt-2 flex flex-wrap items-center gap-3"><StatusBadge variant={toneForHealth(volume.health)}>{volume.health[0].toUpperCase() + volume.health.slice(1)}</StatusBadge><span className="text-sm text-gray-300">{volume.usage_percent}% used</span></div>
          <ProgressBar value={volume.usage_percent} variant={toneForHealth(volume.health)} className="mt-3" /></> : <p className="mt-2 text-sm text-gray-400">Storage status unavailable</p>}
        </div>
        {storage?.refreshed_at && <span className="text-xs text-gray-500">Refreshed {formatBackupDate(storage.refreshed_at)}</span>}
      </div>
      {storage?.available && volume && <div className="mt-5 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
        <div><p className="text-gray-500">Capacity</p><p className="mt-1 font-medium text-white">{formatSize(volume.capacity_bytes)}</p></div>
        <div><p className="text-gray-500">Filesystem used</p><p className="mt-1 font-medium text-white">{formatSize(volume.used_bytes)}</p></div>
        <div><p className="text-gray-500">Available</p><p className="mt-1 font-medium text-white">{formatSize(volume.available_bytes)}</p></div>
        <div><p className="text-gray-500">Usage</p><p className="mt-1 font-medium text-white">{volume.usage_percent}%</p></div>
        <div><p className="text-gray-500">Managed client backups</p><p className="mt-1 font-medium text-white">{formatSize(storage.managed.size_bytes)}</p></div>
        <div><p className="text-gray-500">Platform backups</p><p className="mt-1 font-medium text-white">{formatSize(storage.platform.size_bytes)}</p></div>
        <div><p className="text-gray-500">Managed backup count</p><p className="mt-1 font-medium text-white">{storage.managed.count}</p></div>
        <div><p className="text-gray-500">Platform backup count</p><p className="mt-1 font-medium text-white">{storage.platform.count}</p></div>
      </div>}
    </Card>

    {feedback && <div role="status" className={feedback.error ? "alert-error mb-5" : "alert-success mb-5"}>{feedback.message}</div>}
    <section aria-labelledby="ha-backups">
      <h2 id="ha-backups" className="mb-3 text-lg font-semibold text-white">Home Assistant Backups</h2>
      <div className="space-y-3">
        {groups.length === 0 ? <EmptyState>No managed client backups are currently stored.</EmptyState> : groups.map(group => {
          const state = states.find(item => item.client_id === group.client_id);
          const open = !!expanded[group.client_id];
          return <Card key={group.client_id} compact>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div><p className="font-semibold text-white">{group.client_name}</p><p className="text-purple-300">{group.instance_name}</p>
                <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                  <span className="text-gray-500">Storage used</span><span className="text-white">{formatSize(group.size_bytes)}</span>
                  <span className="text-gray-500">Managed backups</span><span className="text-white">{group.count}</span>
                  <span className="text-gray-500">Oldest backup</span><span className="text-white">{formatBackupDate(group.oldest_at)}</span>
                  <span className="text-gray-500">Newest backup</span><span className="text-white">{formatBackupDate(group.newest_at)}</span>
                  <span className="text-gray-500">Latest status</span><StatusBadge status={group.latest_status || state?.current_operation?.state || "completed"}>{group.latest_status || "Completed"}</StatusBadge>
                </div>
              </div>
              <Button variant="secondary" onClick={() => setExpanded({ ...expanded, [group.client_id]: !open })}>{open ? "Hide backups" : "View backups"}</Button>
            </div>
            {open && <div className="mt-5 space-y-2 border-t border-white/10 pt-4">
              {group.items.map(backup => <div key={backup.id} className="flex flex-col gap-3 rounded-lg bg-black/20 p-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0"><p className="break-words font-medium text-white">{backup.backup_type || "Managed backup"}</p><p className="mt-1 text-sm text-gray-400">{formatBackupDate(backup.completed_at)} · {formatSize(backup.size_bytes)} · {backup.status}</p><p className="mt-1 break-all text-xs text-gray-500">{backup.filename}</p></div>
                <div className="flex flex-col gap-2 sm:flex-row"><Button as="a" href={backup.download_url} download>Download</Button><Button variant="danger" onClick={() => setDeleteTarget(backup)}>Delete</Button></div>
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
              <span className="text-gray-500">Stored backups</span><span className="text-white">{storage?.platform?.count ?? platform.count}</span>
              <span className="text-gray-500">Storage used</span><span className="text-white">{formatSize(storage?.platform?.size_bytes ?? platform.totalBytes)}</span>
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

    {deleteTarget && <Modal maxWidth="max-w-lg">
      <h2 className="text-lg font-semibold text-white">Delete managed backup?</h2>
      <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
        <dt className="text-gray-500">Client</dt><dd className="text-white">{deleteTarget.client_name}</dd>
        <dt className="text-gray-500">Instance</dt><dd className="text-white">{deleteTarget.instance_name}</dd>
        <dt className="text-gray-500">Backup date</dt><dd className="text-white">{formatBackupDate(deleteTarget.completed_at)}</dd>
        <dt className="text-gray-500">Backup type</dt><dd className="text-white">{deleteTarget.backup_type}</dd>
        <dt className="text-gray-500">Filename</dt><dd className="break-all text-white">{deleteTarget.filename}</dd>
        <dt className="text-gray-500">Recorded size</dt><dd className="text-white">{formatSize(deleteTarget.size_bytes)}</dd>
      </dl>
      <p className="mt-4 font-semibold text-warning-text">Estimated space recovered: {formatSize(deleteTarget.size_bytes)}</p>
      <p className="mt-3 text-sm text-gray-300">Deleting this backup permanently removes the stored archive and its download record. This action cannot be undone.</p>
      <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end"><Button variant="secondary" disabled={deleting} onClick={() => setDeleteTarget(null)}>Cancel</Button><Button variant="danger" disabled={deleting} onClick={removeBackup}>{deleting ? "Deleting…" : "Permanently delete"}</Button></div>
    </Modal>}
  </div>;
}
