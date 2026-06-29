import { useState, useEffect, useCallback } from 'react';

export default function Support() {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchTickets = useCallback(async () => {
    try {
      const res = await fetch('/api/support', { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setTickets(data);
      }
      setLastUpdated(new Date());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTickets();
    const id = setInterval(fetchTickets, 30000);
    return () => clearInterval(id);
  }, [fetchTickets]);

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-gray-400">Loading...</div></div>;
  if (error) return <div className="bg-red-900/50 border border-red-700 rounded-lg p-4 text-red-300">Error: {error}</div>;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Support Tickets</h1>
        <div className="flex items-center gap-3">
          {lastUpdated && <span className="text-xs text-gray-500">Updated {lastUpdated.toLocaleTimeString()}</span>}
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
            <span className="text-xs text-gray-500">Live</span>
          </div>
        </div>
      </div>
      {tickets.length === 0 ? (
        <div className="text-gray-400">No tickets. 🎉</div>
      ) : (
        <div className="space-y-4">
          {tickets.map(t => (
            <div key={t.id} className="bg-gray-800 rounded-xl p-5 border border-gray-700">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-white font-semibold">{t.title}</h3>
                <div className="flex gap-2">
                  <span className={`text-xs px-2 py-1 rounded-full ${t.priority === 'high' ? 'bg-red-900 text-red-300' : t.priority === 'normal' ? 'bg-yellow-900 text-yellow-300' : 'bg-gray-700 text-gray-400'}`}>{t.priority}</span>
                  <span className={`text-xs px-2 py-1 rounded-full ${t.status === 'open' ? 'bg-blue-900 text-blue-300' : t.status === 'in_progress' ? 'bg-purple-900 text-purple-300' : 'bg-green-900 text-green-300'}`}>{t.status}</span>
                </div>
              </div>
              <div className="text-sm text-gray-400">
                Client #{t.client_id} • {t.hours_used}h used • {new Date(t.created_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
