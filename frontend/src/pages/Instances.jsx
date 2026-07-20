import { useState, useEffect, useCallback } from 'react';
import { Card, EmptyState, ErrorState, LiveStatus, LoadingState, PageHeader, ProgressBar, StatusDot } from '../components/ui';

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

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return (
    <div>
      <PageHeader title="HA Instances" meta={<LiveStatus lastUpdated={lastUpdated} />} />
      {instances.length === 0 ? (
        <EmptyState>No instances found.</EmptyState>
      ) : (
        <div className="space-y-4">
          {instances.map(i => (
            <Card key={i.id} compact>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <StatusDot active={i.is_online} size="md" pulse={i.is_online} />
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
                  <ProgressBar value={i.disk_usage_percent || 0} className="mt-1 h-1.5" />
                </div>
                <div>
                  <div className="text-gray-500">Last Local HA Backup</div>
                  <div className="text-white">{i.last_backup || 'Never'}</div>
                </div>
                <div>
                  <div className="text-gray-500">Entities / Automations</div>
                  <div className="text-white">{i.entities_count} / {i.automations_count}</div>
                </div>
              </div>
              {i.updates_available && i.updates_available.length > 0 && (
                <div className="mt-3">
                  <span className="badge badge-warning">Updates: {i.updates_available.join(', ')}</span>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
