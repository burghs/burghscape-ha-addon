import { usePolling } from '../hooks/usePolling';

export default function Dashboard() {
  const { data, loading, error, lastUpdated } = usePolling(
    () => fetch('/api/dashboard/summary', { credentials: 'include' }).then(res => res.json()),
    30000
  );

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-gray-400">Loading...</div></div>;
  if (error) return <div className="bg-red-900/50 border border-red-700 rounded-lg p-4 text-red-300">Error: {error}</div>;
  if (!data) return null;

  const stats = [
    { label: 'Total Clients', value: data.total_clients, color: 'text-blue-400', bg: 'bg-blue-600' },
    { label: 'Online Instances', value: data.online_instances, color: 'text-green-400', bg: 'bg-green-600' },
    { label: 'Backups Today', value: data.backups_today, color: 'text-purple-400', bg: 'bg-purple-600' },
    { label: 'Unresolved Alerts', value: data.alerts_unresolved, color: 'text-yellow-400', bg: 'bg-yellow-600' },
    { label: 'Open Tickets', value: data.support_open, color: 'text-red-400', bg: 'bg-red-600' },
  ];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        {lastUpdated && (
          <span className="text-xs text-gray-500">
            Updated {lastUpdated.toLocaleTimeString()}
            <span className="ml-2 inline-block w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
          </span>
        )}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        {stats.map(s => (
          <div key={s.label} className="bg-gray-800 rounded-xl p-5 border border-gray-700">
            <div className={`text-xs font-semibold uppercase tracking-wider ${s.color} mb-2`}>{s.label}</div>
            <div className="text-3xl font-bold text-white">{s.value}</div>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <h2 className="text-lg font-semibold text-white mb-2">Backup Status</h2>
          <div className="text-sm text-gray-400">Failed today: <span className="text-red-400">{data.backups_failed}</span></div>
        </div>
        <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
          <h2 className="text-lg font-semibold text-white mb-2">Instances</h2>
          <div className="text-sm text-gray-400">Offline: <span className="text-red-400">{data.offline_instances}</span></div>
        </div>
      </div>
    </div>
  );
}
