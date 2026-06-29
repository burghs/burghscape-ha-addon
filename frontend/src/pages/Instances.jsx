import { useState, useEffect, useCallback } from 'react';

export default function Instances() {
  const [instances, setInstances] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchInstances = useCallback(async () => {
    try {
      const res = await fetch('/api/instances', { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setInstances(data);
      }
      setLastUpdated(new Date());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInstances();
    const id = setInterval(fetchInstances, 30000);
    return () => clearInterval(id);
  }, [fetchInstances]);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-gray-400">Loading...</div></div>;
  if (error) return <div className="bg-red-900/50 border border-red-700 rounded-lg p-4 text-red-300">Error: {error}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">HA Instances</h1>
        <div className="flex items-center gap-3">
          {lastUpdated && <span className="text-xs text-gray-500">Updated {lastUpdated.toLocaleTimeString()}</span>}
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
            <span className="text-xs text-gray-500">Live</span>
          </div>
        </div>
      </div>
      {instances.length === 0 ? (
        <div className="text-gray-400">No instances found.</div>
      ) : (
        <div className="space-y-4">
          {instances.map(i => (
            <div key={i.id} className="bg-gray-800 rounded-xl p-5 border border-gray-700">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${i.is_online ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
                  <h3 className="text-lg font-semibold text-white">{i.name || 'Unnamed'}</h3>
                </div>
                <span className="text-sm text-gray-400">{i.ha_version || 'Unknown'}</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <div className="text-gray-500">IP Address</div>
                  <div className="text-white">{i.ip_address || 'N/A'}</div>
                </div>
                <div>
                  <div className="text-gray-500">Disk Usage</div>
                  <div className="text-white">{i.disk_usage_percent != null ? i.disk_usage_percent + '%' : 'N/A'}</div>
                  <div className="w-full bg-gray-700 rounded-full h-1.5 mt-1">
                    <div className="bg-blue-500 h-full rounded-full" style={{width: `${i.disk_usage_percent || 0}%`}}></div>
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">Last Backup</div>
                  <div className="text-white">{i.last_backup || 'Never'}</div>
                </div>
                <div>
                  <div className="text-gray-500">Entities / Automations</div>
                  <div className="text-white">{i.entities_count} / {i.automations_count}</div>
                </div>
              </div>
              {i.updates_available && i.updates_available.length > 0 && (
                <div className="mt-3">
                  <span className="text-xs bg-yellow-900 text-yellow-300 px-2 py-1 rounded-full">
                    Updates: {i.updates_available.join(', ')}
                  </span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
