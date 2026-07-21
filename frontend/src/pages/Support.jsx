import { useCallback, useEffect, useState } from "react";
import { Button, EmptyState, ErrorState, LiveStatus, LoadingState, Modal, PageHeader, StatusBadge, Textarea } from "../components/ui";

const localDate = value => value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "Africa/Johannesburg" }).format(new Date(value)) : "Unknown";

export default function Support() {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const fetchTickets = useCallback(async () => {
    try {
      const res = await fetch("/api/support", { credentials: "include" });
      if (!res.ok) throw new Error("Unable to load support tickets");
      setTickets(await res.json()); setLastUpdated(new Date());
    } catch (err) { setError(err.message); } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchTickets(); const id = setInterval(fetchTickets, 30000); return () => clearInterval(id); }, [fetchTickets]);

  const openTicket = ticket => {
    setSelected(ticket);
    setForm({ title: ticket.title, status: ticket.status || "open", priority: ticket.priority || "normal",
      hours_used: ticket.hours_used || 0, resolution: ticket.resolution || "" });
    setMessage("");
  };

  const save = async close => {
    setSaving(true); setMessage("");
    const payload = { ...form, hours_used: Number(form.hours_used || 0) };
    if (close) payload.status = "completed";
    try {
      const res = await fetch(`/api/support/${selected.id}`, { method: "PUT", headers: { "Content-Type": "application/json" },
        credentials: "include", body: JSON.stringify(payload) });
      if (!res.ok) throw new Error((await res.json()).detail || "Unable to save ticket");
      setMessage(close ? "Ticket closed." : "Ticket saved.");
      await fetchTickets();
      const updated = await res.json(); setSelected(updated); setForm({ ...form, status: updated.status });
    } catch (err) { setMessage(err.message); } finally { setSaving(false); }
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return <div>
    <PageHeader title="Support Tickets" meta={<LiveStatus lastUpdated={lastUpdated} />} />
    {tickets.length === 0 ? <EmptyState>No tickets.</EmptyState> :
      <div className="space-y-3">
        {tickets.map(ticket => <button key={ticket.id} onClick={() => openTicket(ticket)}
          className="app-card app-card-compact block w-full text-left transition hover:border-purple-400/40 focus:outline-none focus:ring-2 focus:ring-purple-400">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div className="min-w-0"><p className="text-xs uppercase tracking-wide text-purple-300">{ticket.client_name}</p>
              <h2 className="mt-1 break-words font-semibold text-white">{ticket.title}</h2>
              <p className="mt-2 line-clamp-2 whitespace-pre-wrap text-sm text-gray-400">{ticket.description || "No description"}</p></div>
            <div className="flex shrink-0 flex-wrap gap-2"><StatusBadge status={ticket.priority}>{ticket.priority}</StatusBadge>
              <StatusBadge status={ticket.status}>{ticket.status}</StatusBadge></div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-500 sm:grid-cols-4">
            <span>Created: {localDate(ticket.created_at)}</span><span>Updated: {localDate(ticket.updated_at)}</span>
            <span>Time logged: {ticket.hours_used || 0}h</span><span>{ticket.resolution ? "Resolution recorded" : ticket.status === "completed" || ticket.status === "closed" ? "Resolution not recorded" : "Open ticket"}</span>
          </div>
        </button>)}
      </div>}
    {selected && <Modal maxWidth="max-w-3xl">
      <div className="max-h-[85vh] overflow-y-auto p-1">
        <div className="flex items-start justify-between gap-4"><div><p className="text-sm text-purple-300">{selected.client_name}</p>
          <h2 className="text-xl font-semibold text-white">{selected.title}</h2></div>
          <button onClick={() => setSelected(null)} className="btn btn-secondary" aria-label="Close ticket detail">Close</button></div>
        <dl className="mt-5 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <div><dt className="text-gray-500">Priority</dt><dd className="text-white">{selected.priority}</dd></div>
          <div><dt className="text-gray-500">Status</dt><dd className="text-white">{selected.status}</dd></div>
          <div><dt className="text-gray-500">Created</dt><dd className="text-white">{localDate(selected.created_at)}</dd></div>
          <div><dt className="text-gray-500">Logged</dt><dd className="text-white">{selected.hours_used || 0}h</dd></div>
        </dl>
        <div className="mt-5"><p className="text-sm text-gray-500">Original description</p><p className="mt-1 whitespace-pre-wrap text-sm text-gray-300">{selected.description || "No description"}</p></div>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <label className="text-sm text-gray-400">Status<select className="form-input-dark mt-1" value={form.status} onChange={e => setForm({...form,status:e.target.value})}><option value="open">Open</option><option value="in_progress">In progress</option><option value="completed">Completed</option><option value="closed">Closed</option></select></label>
          <label className="text-sm text-gray-400">Priority<select className="form-input-dark mt-1" value={form.priority} onChange={e => setForm({...form,priority:e.target.value})}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></label>
          <label className="text-sm text-gray-400">Time used (hours)<input type="number" min="0" step="0.25" className="form-input-dark mt-1" value={form.hours_used} onChange={e => setForm({...form,hours_used:e.target.value})} /></label>
        </div>
        <label className="mt-4 block text-sm text-gray-400">Resolution <span className="text-gray-600">(recommended when closing)</span>
          <Textarea rows="5" className="mt-1" value={form.resolution} onChange={e => setForm({...form,resolution:e.target.value})} placeholder="Record what was done to resolve the issue." /></label>
        {message && <p className="mt-3 text-sm text-purple-200" role="status">{message}</p>}
        <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-end"><Button variant="secondary" onClick={() => save(false)} disabled={saving}>Save changes</Button>
          <Button variant="success" onClick={() => save(true)} disabled={saving}>Save & close ticket</Button></div>
      </div>
    </Modal>}
  </div>;
}
