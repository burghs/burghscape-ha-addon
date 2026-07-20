import { usePolling } from '../hooks/usePolling';
import { Card, ErrorState, LiveStatus, LoadingState, PageHeader, StatCard } from '../components/ui';

export default function Dashboard() {
  const { data, loading, error, lastUpdated } = usePolling(
    () => fetch('/api/dashboard/summary', { credentials: 'include' }).then(res => res.json()),
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
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <h2 className="text-lg font-semibold text-white mb-2">Managed Backup Status</h2>
          <div className="text-sm text-gray-400">Failed today: <span className="text-danger-text">{data.backups_failed}</span></div>
        </Card>
        <Card>
          <h2 className="text-lg font-semibold text-white mb-2">Instances</h2>
          <div className="text-sm text-gray-400">Offline: <span className="text-danger-text">{data.offline_instances}</span></div>
        </Card>
      </div>
    </div>
  );
}
