import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, Card, EmptyState, ErrorState, LiveStatus, LoadingState, Modal, PageHeader, StatusBadge, Textarea } from "../components/ui";

const localDate = value => value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "Africa/Johannesburg" }).format(new Date(value)) : "Unknown";
export const groupTicketsByClient = (tickets, summaries = {}) => {
  const groups = {};
  for (const ticket of tickets) {
    const key = String(ticket.client_id);
    if (!groups[key]) groups[key] = { clientId: ticket.client_id, clientName: ticket.client_name, tickets: [] };
    groups[key].tickets.push(ticket);
  }
  return Object.entries(groups).map(([key, group]) => {
    const closed = group.tickets.filter(ticket => ["completed", "closed"].includes(ticket.status)).length;
    return { ...group, open: group.tickets.length - closed, closed, total: group.tickets.length,
      support: summaries[key] || { included: "0", logged: "0", remaining: "0", potentially_billable: "0" } };
  }).sort((a, b) => a.clientName.localeCompare(b.clientName));
};

export default function Support() {
  const [tickets, setTickets] = useState([]);
  const [summaries, setSummaries] = useState({});
  const [expanded, setExpanded] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [selected, setSelected] = useState(null);
  const [deleteCandidate, setDeleteCandidate] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [message, setMessage] = useState("");

  const fetchTickets = useCallback(async () => {
    try {
      const [ticketResponse, summaryResponse] = await Promise.all([
        fetch("/api/support", { credentials: "include" }),
        fetch("/api/support/hours-summary", { credentials: "include" }),
      ]);
      if (!ticketResponse.ok || !summaryResponse.ok) throw new Error("Unable to load support tickets");
      setTickets(await ticketResponse.json());
      setSummaries((await summaryResponse.json()).clients || {});
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

  const groups = useMemo(() => groupTicketsByClient(tickets, summaries), [tickets, summaries]);

  const openTicket = ticket => {
    setSelected(ticket);
    setForm({ title: ticket.title, status: ticket.status || "open", priority: ticket.priority || "normal",
      hours_used: ticket.hours_used || 0, resolution: ticket.resolution || "" });
    setMessage("");
  };

  const save = async close => {
    setSaving(true);
    setMessage("");
    const payload = { ...form, hours_used: Number(form.hours_used || 0) };
    if (close) payload.status = "completed";
    try {
      const res = await fetch(`/api/support/${selected.id}`, { method: "PUT", headers: { "Content-Type": "application/json" },
        credentials: "include", body: JSON.stringify(payload) });
      if (!res.ok) throw new Error((await res.json()).detail || "Unable to save ticket");
      const updated = await res.json();
      setSelected(updated);
      setForm({ ...form, status: updated.status });
      setMessage(close ? "Ticket closed." : "Ticket saved.");
      await fetchTickets();
    } catch (err) {
      setMessage(err.message);
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteCandidate) return;
    setDeleting(true);
    setMessage("");
    try {
      const res = await fetch(`/api/support/${deleteCandidate.id}`, { method: "DELETE", credentials: "include" });
      if (!res.ok) throw new Error((await res.json()).detail || "Ticket could not be deleted");
      setDeleteCandidate(null);
      if (selected?.id === deleteCandidate.id) setSelected(null);
      await fetchTickets();
    } catch (err) {
      setMessage(err.message);
    } finally {
      setDeleting(false);
    }
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState error={error} />;

  return <div>
    <PageHeader title="Support Tickets" meta={<LiveStatus lastUpdated={lastUpdated} />} />
    {groups.length === 0 ? <EmptyState>No support tickets have been logged.</EmptyState> : <div className="space-y-3">
      {groups.map(group => {
        const open = !!expanded[group.clientId];
        return <Card key={group.clientId} compact>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <h2 className="break-words text-lg font-semibold text-white">{group.clientName}</h2>
              <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
                <div><dt className="text-gray-500">Open tickets</dt><dd className="text-white">{group.open}</dd></div>
                <div><dt className="text-gray-500">Closed tickets</dt><dd className="text-white">{group.closed}</dd></div>
                <div><dt className="text-gray-500">Total tickets</dt><dd className="text-white">{group.total}</dd></div>
                <div><dt className="text-gray-500">Hours logged this month</dt><dd className="text-white">{group.support.logged}h</dd></div>
                <div><dt className="text-gray-500">Included</dt><dd className="text-white">{group.support.included}h</dd></div>
                <div><dt className="text-gray-500">Remaining</dt><dd className="text-white">{group.support.remaining}h</dd></div>
                <div><dt className="text-gray-500">Potentially billable</dt><dd className="text-white">{group.support.potentially_billable}h</dd></div>
              </dl>
            </div>
            <Button variant="secondary" onClick={() => setExpanded({ ...expanded, [group.clientId]: !open })}>{open ? "Hide tickets" : "View tickets"}</Button>
          </div>
          {open && <div className="mt-5 space-y-2 border-t border-white/10 pt-4">
            {group.tickets.map(ticket => <div key={ticket.id} className="rounded-lg bg-black/20 p-3">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <h3 className="break-words font-medium text-white">{ticket.title}</h3>
                  <div className="mt-2 flex flex-wrap gap-2"><StatusBadge status={ticket.status}>{ticket.status}</StatusBadge><StatusBadge status={ticket.priority}>{ticket.priority}</StatusBadge><span className="text-sm text-gray-400">{ticket.hours_used || 0}h</span></div>
                  <p className="mt-2 text-xs text-gray-500">Created {localDate(ticket.created_at)} · Updated {localDate(ticket.updated_at)}</p>
                  <p className="mt-1 text-sm text-gray-400">{ticket.resolution ? "Resolution recorded" : "Resolution not recorded"}</p>
                </div>
                <div className="flex shrink-0 flex-col gap-2 sm:flex-row">
                  <Button variant="secondary" onClick={() => openTicket(ticket)}>Open</Button>
                  <Button variant="danger" onClick={() => { setMessage(""); setDeleteCandidate(ticket); }}>Delete</Button>
                </div>
              </div>
            </div>)}
          </div>}
        </Card>;
      })}
    </div>}

    {selected && <Modal maxWidth="max-w-3xl">
      <div className="max-h-[85vh] overflow-y-auto p-1">
        <div className="flex items-start justify-between gap-4"><div><p className="text-sm text-purple-300">{selected.client_name}</p><h2 className="break-words text-xl font-semibold text-white">{selected.title}</h2></div>
          <button onClick={() => setSelected(null)} className="btn btn-secondary" aria-label="Close ticket detail">Close</button></div>
        <dl className="mt-5 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <div><dt className="text-gray-500">Priority</dt><dd className="text-white">{selected.priority}</dd></div>
          <div><dt className="text-gray-500">Status</dt><dd className="text-white">{selected.status}</dd></div>
          <div><dt className="text-gray-500">Created</dt><dd className="text-white">{localDate(selected.created_at)}</dd></div>
          <div><dt className="text-gray-500">Logged</dt><dd className="text-white">{selected.hours_used || 0}h</dd></div>
        </dl>
        <div className="mt-5"><p className="text-sm text-gray-500">Original description</p><p className="mt-1 whitespace-pre-wrap text-sm text-gray-300">{selected.description || "No description"}</p></div>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <label className="text-sm text-gray-400">Status<select className="form-input-dark mt-1" value={form.status} onChange={event => setForm({ ...form, status: event.target.value })}><option value="open">Open</option><option value="in_progress">In progress</option><option value="completed">Completed</option><option value="closed">Closed</option></select></label>
          <label className="text-sm text-gray-400">Priority<select className="form-input-dark mt-1" value={form.priority} onChange={event => setForm({ ...form, priority: event.target.value })}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></label>
          <label className="text-sm text-gray-400">Time used (hours)<input type="number" min="0" step="0.25" className="form-input-dark mt-1" value={form.hours_used} onChange={event => setForm({ ...form, hours_used: event.target.value })} /></label>
        </div>
        <label className="mt-4 block text-sm text-gray-400">Resolution <span className="text-gray-600">(recommended when closing)</span>
          <Textarea rows="5" className="mt-1" value={form.resolution} onChange={event => setForm({ ...form, resolution: event.target.value })} placeholder="Record what was done to resolve the issue." /></label>
        {message && <p className="mt-3 text-sm text-red-200" role="status">{message}</p>}
        <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-end"><Button variant="secondary" onClick={() => save(false)} disabled={saving}>Save changes</Button><Button variant="success" onClick={() => save(true)} disabled={saving}>Save & close ticket</Button></div>
      </div>
    </Modal>}

    {deleteCandidate && <Modal maxWidth="max-w-lg" className="max-h-[85vh] overflow-y-auto p-6">
      <h2 className="text-xl font-semibold text-white">Delete support ticket?</h2>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div><dt className="text-gray-500">Client</dt><dd className="break-words text-white">{deleteCandidate.client_name}</dd></div>
        <div><dt className="text-gray-500">Status</dt><dd className="text-white">{deleteCandidate.status}</dd></div>
        <div className="col-span-2"><dt className="text-gray-500">Subject</dt><dd className="break-words text-white">{deleteCandidate.title}</dd></div>
        <div><dt className="text-gray-500">Logged time</dt><dd className="text-white">{deleteCandidate.hours_used || 0}h</dd></div>
      </dl>
      <div className="mt-5 rounded-lg border border-red-400/30 bg-red-400/10 p-3 text-sm text-red-100">
        <p>This permanently removes the ticket resolution and history.</p>
        <p className="mt-2 font-semibold">Deleting this ticket permanently removes its recorded time from the client’s support totals.</p>
      </div>
      {message && <p className="mt-3 text-sm text-red-200" role="alert">{message}</p>}
      <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button variant="secondary" onClick={() => { setDeleteCandidate(null); setMessage(""); }} disabled={deleting}>Cancel</Button>
        <Button variant="danger" onClick={confirmDelete} disabled={deleting}>{deleting ? "Deleting…" : "Permanently delete ticket"}</Button>
      </div>
    </Modal>}
  </div>;
}
