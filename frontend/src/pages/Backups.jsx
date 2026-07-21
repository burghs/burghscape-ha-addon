import { useState, useEffect, useCallback } from "react";
import { Button, Card, EmptyState, ErrorState, LiveStatus, LoadingState, PageHeader, StatusBadge } from '../components/ui';

export default function Backups() {
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [managedState, setManagedState] = useState([]);
  const [managedBackups, setManagedBackups] = useState([]);

  const fetchBackups = useCallback(async () => {
    try {
      const [res, stateRes] = await Promise.all([
        fetch("/api/admin/backups", { credentials: "include" }),
        fetch("/api/admin/managed-backup-state", { credentials: "include" }),
      ]);
      if (res.ok) {
        const data = await res.json();
        setBackups(data.backups || []);
      }
      if (stateRes.ok) { const data = await stateRes.json(); setManagedState(data.clients || []); setManagedBackups(data.backups || []); }
      setLastUpdated(new Date());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBackups();
    const id = setInterval(fetchBackups, 30000);
    return () => clearInterval(id);
  }, [fetchBackups]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  const formatSize = (bytes) => {
    if (!bytes) return "Unknown";
    if (bytes > 1073741824) return (bytes / 1073741824).toFixed(1) + " GB";
    return (bytes / 1048576).toFixed(0) + " MB";
  };

  const formatDate = (d) => {
    if (!d) return "-";
    return new Date(d).toLocaleString();
  };

  return (
    <div>
      <PageHeader title="Server Backups" meta={<LiveStatus lastUpdated={lastUpdated} />} />

      <h2 className="text-white font-semibold mb-3">Managed Home Assistant Backups</h2>
      <div className="space-y-3 mb-8">
        {managedState.map((item) => { const op=item.current_operation; return (
          <Card key={item.client_id} compact><div className="flex flex-wrap justify-between gap-4"><div><div className="flex items-center gap-3"><span className="text-white font-semibold">{item.client_name}</span><StatusBadge status={op?.state || "unknown"}>{op?.state || "No operation"}</StatusBadge></div><div className="text-sm text-gray-500 mt-2">Automatic: {item.automatic_enabled ? "Enabled" : "Disabled"} · Last success: {item.last_success ? formatDate(item.last_success.completed_at) + " (" + formatSize(item.last_success.size_bytes) + ")" : "None"} · Last failure: {item.last_failure ? formatDate(item.last_failure.failed_at) + " (" + (item.last_failure.error_category || "Failed") + ")" : "None"}</div></div></div></Card>
        ); })}
        {managedState.length === 0 && <EmptyState>No managed backup state reported.</EmptyState>}
      </div>

      <h2 className="text-white font-semibold mb-3">Stored Managed Backups</h2>
      <div className="space-y-3 mb-8">
        {managedBackups.map((backup) => (
          <Card key={backup.download_url} compact>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-semibold text-white">{backup.filename}</span>
                  <StatusBadge status={backup.status}>{backup.status}</StatusBadge>
                </div>
                <div className="mt-1 text-sm text-gray-500">
                  {backup.client_name} · {backup.instance_name} · {formatSize(backup.size_bytes)} · {formatDate(backup.completed_at)}
                </div>
              </div>
              <Button as="a" href={backup.download_url} download variant="primary">Download</Button>
            </div>
          </Card>
        ))}
        {managedBackups.length === 0 && <EmptyState>No completed managed backups stored.</EmptyState>}
      </div>

      {backups.length === 0 ? (
        <EmptyState>No server backups recorded.</EmptyState>
      ) : (
        <div className="space-y-4">
          {backups.map((b, i) => (
            <Card key={i} compact>
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-3">
                    <span className="text-white font-semibold">{b.name || b.filename}</span>
                    <StatusBadge status={b.status || "available"}>{b.status || "available"}</StatusBadge>
                  </div>
                  <div className="text-sm text-gray-500 mt-1">
                    {b.type && <span className="mr-3">{b.type}</span>}
                    {b.size_bytes && <span className="mr-3">{formatSize(b.size_bytes)}</span>}
                    {b.created_at && <span>{formatDate(b.created_at)}</span>}
                    {b.date && <span>{b.date}</span>}
                  </div>
                </div>
                <div className="flex gap-2">
                  {b.download_url && (
                    <Button as="a" href={b.download_url} download variant="primary">
                      Download
                    </Button>
                  )}
                  {b.client_name && (
                    <span className="text-xs text-gray-500 self-center">{b.client_name}</span>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Card muted className="mt-8">
        <h2 className="text-white font-semibold mb-2">Current Backup Scope</h2>
        <p className="text-gray-400 text-sm">
          Server backups include PostgreSQL database, environment configs, Docker setup,
          platform source code, and Cloudflare tunnel configs. Managed Home Assistant backup state and completed uploads are shown above. Recurring scheduling, retention,
          and restore are not active.
        </p>
      </Card>
    </div>
  );
}
