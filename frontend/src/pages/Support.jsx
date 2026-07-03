import { useState, useEffect, useCallback } from "react";

export default function Support() {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({});

  const fetchTickets = useCallback(async () => {
    try {
      const res = await fetch("/api/support", { credentials: "include" });
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

  const updateTicket = async (id, data) => {
    const res = await fetch(`/api/support/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(data),
    });
    if (res.ok) {
      setEditingId(null);
      fetchTickets();
    }
  };

  const deleteTicket = async (id) => {
    if (!confirm("Delete this support ticket?")) return;
    const res = await fetch(`/api/support/${id}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (res.ok) fetchTickets();
  };

  const closeTicket = (id) => updateTicket(id, { status: "completed" });

  const startEdit = (t) => {
    setEditingId(t.id);
    setEditForm({
      status: t.status || "open",
      priority: t.priority || "normal",
      hours_used: t.hours_used || 0,
      title: t.title,
    });
  };

  const saveEdit = (id) => {
    const data = {};
    if (editForm.status) data.status = editForm.status;
    if (editForm.priority) data.priority = editForm.priority;
    if (editForm.hours_used !== undefined) data.hours_used = parseFloat(editForm.hours_used);
    if (editForm.title) data.title = editForm.title;
    updateTicket(id, data);
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="text-gray-400">Loading...</div></div>;
  if (error) return <div className="bg-red-900/50 border border-red-700 rounded-lg p-4 text-red-300">Error: {error}</div>;

  const statusColors = {
    open: "bg-blue-900 text-blue-300",
    in_progress: "bg-purple-900 text-purple-300",
    completed: "bg-green-900 text-green-300",
    closed: "bg-gray-700 text-gray-400",
  };
  const priorityColors = {
    high: "bg-red-900 text-red-300",
    normal: "bg-yellow-900 text-yellow-300",
    low: "bg-gray-700 text-gray-400",
  };

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
        <div className="text-gray-400 text-center py-12">No tickets. 🎉</div>
      ) : (
        <div className="space-y-4">
          {tickets.map((t) => (
            <div key={t.id} className="bg-gray-800 rounded-xl p-5 border border-gray-700">
              {editingId === t.id ? (
                /* Edit Mode */
                <div className="space-y-3">
                  <input
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    value={editForm.title}
                    onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                  />
                  <div className="flex gap-3">
                    <select
                      className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
                      value={editForm.status}
                      onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                    >
                      <option value="open">Open</option>
                      <option value="in_progress">In Progress</option>
                      <option value="completed">Completed</option>
                      <option value="closed">Closed</option>
                    </select>
                    <select
                      className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm"
                      value={editForm.priority}
                      onChange={(e) => setEditForm({ ...editForm, priority: e.target.value })}
                    >
                      <option value="low">Low</option>
                      <option value="normal">Normal</option>
                      <option value="high">High</option>
                    </select>
                    <input
                      type="number"
                      className="bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm w-24"
                      value={editForm.hours_used}
                      onChange={(e) => setEditForm({ ...editForm, hours_used: e.target.value })}
                      placeholder="Hours"
                    />
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => saveEdit(t.id)} className="px-4 py-1.5 bg-purple-600 text-white rounded-lg text-sm hover:bg-purple-700">Save</button>
                    <button onClick={() => setEditingId(null)} className="px-4 py-1.5 bg-gray-600 text-white rounded-lg text-sm hover:bg-gray-700">Cancel</button>
                  </div>
                </div>
              ) : (
                /* View Mode */
                <>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-white font-semibold text-lg">{t.title}</h3>
                    <div className="flex gap-2">
                      <span className={`text-xs px-2 py-1 rounded-full ${priorityColors[t.priority] || priorityColors.normal}`}>
                        {t.priority}
                      </span>
                      <span className={`text-xs px-2 py-1 rounded-full ${statusColors[t.status] || statusColors.open}`}>
                        {t.status === "completed" ? "✅ Done" : t.status}
                      </span>
                    </div>
                  </div>

                  {t.description && (
                    <p className="text-gray-400 text-sm mb-3 whitespace-pre-wrap">{t.description}</p>
                  )}

                  <div className="flex items-center justify-between">
                    <div className="text-sm text-gray-500">
                      Client #{t.client_id} • {t.hours_used}h used • {new Date(t.created_at).toLocaleDateString()}
                    </div>
                    <div className="flex gap-2">
                      {t.status !== "completed" && t.status !== "closed" && (
                        <button onClick={() => closeTicket(t.id)} className="px-3 py-1 bg-green-700 text-green-200 rounded-lg text-xs hover:bg-green-600">
                          ✓ Close
                        </button>
                      )}
                      <button onClick={() => startEdit(t)} className="px-3 py-1 bg-blue-700 text-blue-200 rounded-lg text-xs hover:bg-blue-600">
                        ✏️ Edit
                      </button>
                      <button onClick={() => deleteTicket(t.id)} className="px-3 py-1 bg-red-700 text-red-200 rounded-lg text-xs hover:bg-red-600">
                        🗑 Delete
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
