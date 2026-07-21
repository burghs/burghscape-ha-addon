import { usePolling } from '../hooks/usePolling';
import { Link } from 'react-router-dom';
import { Card, ErrorState, LiveStatus, LoadingState, PageHeader, ProgressBar, StatCard, StatusBadge } from '../components/ui';

const formatStorage = bytes => bytes == null ? 'Unknown' : bytes >= 1073741824 ? `${(bytes / 1073741824).toFixed(1)} GB` : `${(bytes / 1048576).toFixed(1)} MB`;
const healthTone = value => value === 'healthy' ? 'success' : value === 'attention' ? 'info' : value === 'warning' ? 'warning' : 'danger';

export default function Dashboard() {
  const { data, loading, error, lastUpdated } = usePolling(
    () => fetch('/api/dashboard/summary', { credentials: 'include' }).then(res => res.json()),
    30000
  );
  const { data: storage } = usePolling(
    () => fetch('/api/admin/backup-storage', { credentials: 'include' }).then(res => res.ok ? res.json() : Promise.reject(new Error('Storage unavailable'))),
    30000
  );

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;
  if (!data) return null;

  const stats = [
    { label: 'Total Clients', value: data.total_clients, tone: 'primary' },
    { label: 'Online Instances', value: data.online_instances, tone: 'success' },
    { label: 'Managed Backups Today', value: data.backups_today, tone: 'info' },
    { label: 'Unresolved Alerts', value: data.alerts_unresolved, tone: 'warning' },
    { label: 'Open Tickets', value: data.support_open, tone: 'danger' },
  ];

  return (
    <div>
      <PageHeader
        title="Dashboard"
        meta={<LiveStatus lastUpdated={lastUpdated} />}
      />
      <div className="grid grid-cols-1 gap-4 mb-8 sm:grid-cols-2 xl:grid-cols-[repeat(auto-fit,minmax(12rem,1fr))]">
        {stats.map(s => (
          <StatCard key={s.label} label={s.label} value={s.value} tone={s.tone} />
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <h2 className="text-lg font-semibold text-white mb-2">Managed Backup Status</h2>
          <div className="text-sm text-gray-400">Failed today: <span className="text-danger-text">{data.backups_failed}</span></div>
        </Card>
        <Card>
          <h2 className="text-lg font-semibold text-white mb-2">Instances</h2>
          <div className="text-sm text-gray-400">Offline: <span className="text-danger-text">{data.offline_instances}</span></div>
        </Card>
        <Card>
          <h2 className="text-lg font-semibold text-white mb-2">Backup Storage</h2>
          {storage?.available && storage.volumes?.[0] ? <div className="space-y-3 text-sm">
            <div className="flex items-center justify-between gap-3"><StatusBadge variant={healthTone(storage.volumes[0].health)}>{storage.volumes[0].health}</StatusBadge><span className="text-gray-300">{storage.volumes[0].usage_percent}% used</span></div>
            <ProgressBar value={storage.volumes[0].usage_percent} variant={healthTone(storage.volumes[0].health)} />
            <p className="text-gray-400">{formatStorage(storage.volumes[0].available_bytes)} available</p>
            <p className="text-gray-400">{formatStorage(storage.managed?.size_bytes)} managed backups</p>
            <Link to="/backups" className="action-link text-primary-textLight">View storage</Link>
          </div> : <p className="text-sm text-gray-400">Storage status unavailable</p>}
        </Card>
      </div>
    </div>
  );
}
