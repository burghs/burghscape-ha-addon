import { useState, useEffect, useCallback } from "react";
import { ErrorState, LiveStatus, LoadingState, PageHeader, StatusBadge } from "../components/ui";

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

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return (
    <div>
      <PageHeader title="Support Tickets" meta={<LiveStatus lastUpdated={lastUpdated} />} />

      {tickets.length === 0 ? (
        <div className="text-gray-400 text-center py-12">No tickets.</div>
      ) : (
        <div className="space-y-4">
          {tickets.map((t) => (
            <div key={t.id} className="app-card app-card-compact">
              {editingId === t.id ? (
                /* Edit Mode */
                <div className="space-y-3">
                  <input
                    className="form-input-dark"
                    value={editForm.title}
                    onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                  />
                  <div className="flex gap-3">
                    <select
                      className="form-input-dark w-auto text-sm"
                      value={editForm.status}
                      onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                    >
                      <option value="open">Open</option>
                      <option value="in_progress">In Progress</option>
                      <option value="completed">Completed</option>
                      <option value="closed">Closed</option>
                    </select>
                    <select
                      className="form-input-dark w-auto text-sm"
                      value={editForm.priority}
                      onChange={(e) => setEditForm({ ...editForm, priority: e.target.value })}
                    >
                      <option value="low">Low</option>
                      <option value="normal">Normal</option>
                      <option value="high">High</option>
                    </select>
                    <input
                      type="number"
                      className="form-input-dark w-24 text-sm"
                      value={editForm.hours_used}
                      onChange={(e) => setEditForm({ ...editForm, hours_used: e.target.value })}
                      placeholder="Hours"
                    />
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => saveEdit(t.id)} className="btn btn-primary py-1.5">Save</button>
                    <button onClick={() => setEditingId(null)} className="btn btn-secondary py-1.5">Cancel</button>
                  </div>
                </div>
              ) : (
                /* View Mode */
                <>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-white font-semibold text-lg">{t.title}</h3>
                    <div className="flex gap-2">
                      <StatusBadge status={t.priority || "normal"}>{t.priority}</StatusBadge>
                      <StatusBadge status={t.status || "open"}>
                        {t.status === "completed" ? "Done" : t.status}
                      </StatusBadge>
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
                        <button onClick={() => closeTicket(t.id)} className="btn btn-success px-3 py-1 text-xs">
                          Close
                        </button>
                      )}
                      <button onClick={() => startEdit(t)} className="btn btn-primary px-3 py-1 text-xs">
                        Edit
                      </button>
                      <button onClick={() => deleteTicket(t.id)} className="btn btn-danger px-3 py-1 text-xs">
                        Delete
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
