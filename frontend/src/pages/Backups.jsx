import { useState, useEffect, useCallback } from "react";

export default function Backups() {
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [managedState, setManagedState] = useState([]);

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
      if (stateRes.ok) { const data = await stateRes.json(); setManagedState(data.clients || []); }
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

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-gray-400">Loading...</div></div>;
  if (error) return <div className="bg-red-900/50 border border-red-700 rounded-lg p-4 text-red-300">Error: {error}</div>;

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
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Backups</h1>
        <div className="flex items-center gap-3">
          {lastUpdated && <span className="text-xs text-gray-500">Updated {lastUpdated.toLocaleTimeString()}</span>}
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
            <span className="text-xs text-gray-500">Live</span>
          </div>
        </div>
      </div>

      <h2 className="text-white font-semibold mb-3">Managed Home Assistant Backups</h2>
      <div className="space-y-3 mb-8">
        {managedState.map((item) => { const op = item.current_operation; return (
          <div key={item.client_id} className="bg-gray-800 rounded-xl p-5 border border-gray-700">
            <div className="flex items-center gap-3"><span className="text-white font-semibold">{item.client_name}</span><span className="text-xs px-2 py-1 rounded-full bg-blue-900 text-blue-300">{op?.state || "No operation"}</span></div>
            <div className="text-sm text-gray-500 mt-2">Automatic: {item.automatic_enabled ? "Enabled" : "Disabled"} · Last success: {item.last_success ? formatDate(item.last_success.completed_at) + " (" + formatSize(item.last_success.size_bytes) + ")" : "None"} · Last failure: {item.last_failure ? formatDate(item.last_failure.failed_at) + " (" + (item.last_failure.error_category || "Failed") + ")" : "None"}</div>
          </div>
        ); })}
        {managedState.length === 0 && <div className="text-gray-400">No managed backup state reported.</div>}
      </div>

      {backups.length === 0 ? (
        <div className="text-gray-400">No backups recorded.</div>
      ) : (
        <div className="space-y-4">
          {backups.map((b, i) => (
            <div key={i} className="bg-gray-800 rounded-xl p-5 border border-gray-700">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-3">
                    <span className="text-white font-semibold">{b.name || b.filename}</span>
                    <span className={`text-xs px-2 py-1 rounded-full ${
                      b.status === "completed" || b.status === "available"
                        ? "bg-green-900 text-green-300"
                        : b.status === "failed"
                        ? "bg-red-900 text-red-300"
                        : "bg-blue-900 text-blue-300"
                    }`}>{b.status || "available"}</span>
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
                    <a href={b.download_url} download
                       className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm hover:bg-purple-700">
                      ↓ Download
                    </a>
                  )}
                  {b.client_name && (
                    <span className="text-xs text-gray-500 self-center">{b.client_name}</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-8 bg-gray-800/50 rounded-xl p-5 border border-gray-700">
        <h2 className="text-white font-semibold mb-2">How Backups Work</h2>
        <p className="text-gray-400 text-sm">
          Server backups include: PostgreSQL database, environment configs, Docker setup,
          platform source code, and Cloudflare tunnel configs. Client HA backups include
          Home Assistant snapshots uploaded by the Burghscape Agent add-on.
        </p>
      </div>
    </div>
  );
}
