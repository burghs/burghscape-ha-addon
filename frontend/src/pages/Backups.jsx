import { useState, useEffect, useCallback } from 'react';

export default function Backups() {
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchBackups = useCallback(async () => {
    try {
      const res = await fetch('/api/backups', { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setBackups(data);
      }
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
    if (bytes > 1073741824) return (bytes / 1073741824).toFixed(1) + ' GB';
    return (bytes / 1048576).toFixed(0) + ' MB';
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
      {backups.length === 0 ? (
        <div className="text-gray-400">No backups recorded.</div>
      ) : (
        <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-900">
              <tr>
                <th className="text-left p-3 text-gray-400 font-medium">File</th>
                <th className="text-left p-3 text-gray-400 font-medium">Status</th>
                <th className="text-left p-3 text-gray-400 font-medium">Size</th>
                <th className="text-left p-3 text-gray-400 font-medium">Started</th>
                <th className="text-left p-3 text-gray-400 font-medium">Completed</th>
              </tr>
            </thead>
            <tbody>
              {backups.map(b => (
                <tr key={b.id} className="border-t border-gray-700">
                  <td className="p-3 text-white font-mono text-xs">{b.filename}</td>
                  <td className="p-3">
                    <span className={`text-xs px-2 py-1 rounded-full ${b.status === 'completed' ? 'bg-green-900 text-green-300' : b.status === 'failed' ? 'bg-red-900 text-red-300' : 'bg-blue-900 text-blue-300'}`}>{b.status}</span>
                  </td>
                  <td className="p-3 text-gray-300">{formatSize(b.size_bytes)}</td>
                  <td className="p-3 text-gray-300">{new Date(b.started_at).toLocaleString()}</td>
                  <td className="p-3 text-gray-300">{b.completed_at ? new Date(b.completed_at).toLocaleString() : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
