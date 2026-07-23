import { useState, useEffect, useCallback } from 'react';
import { ActionLink, DataTable, Modal, ProgressBar, StatCard, StatusBadge, StatusDot } from '../components/ui';

const TIERS = {
  basic: { label: 'Basic', price: 'R199', tone: 'muted', hours: 0 },
  standard: { label: 'Standard', price: 'R499', tone: 'primary', hours: 2 },
  premium: { label: 'Premium', price: 'R899', tone: 'info', hours: 5 },
};

export default function Clients() {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [showEditForm, setShowEditForm] = useState(false);
  const [editingClient, setEditingClient] = useState(null);
  const [form, setForm] = useState({ name: '', email: '', phone: '', subdomain: '', tier: 'basic', send_welcome_email: true });
  const [editForm, setEditForm] = useState({ name: '', email: '', phone: '', subdomain: '', tier: 'basic', status: 'active' });
  const [selectedClient, setSelectedClient] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [showTicketForm, setShowTicketForm] = useState(false);
  const [ticketForm, setTicketForm] = useState({ title: '', description: '', priority: 'medium' });
  const [hoursData, setHoursData] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [showReport, setShowReport] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [editingTicket, setEditingTicket] = useState(null);
  const [templateCategory, setTemplateCategory] = useState('all');
  const [lastUpdated, setLastUpdated] = useState(null);
  const [portalUsers, setPortalUsers] = useState([]);
  const [securityAudit, setSecurityAudit] = useState([]);
  const [showPortalUserForm, setShowPortalUserForm] = useState(false);
  const [portalUserForm, setPortalUserForm] = useState({ client_id: '', name: '', email: '', password: '', role: 'viewer' });
  const [editingPortalUser, setEditingPortalUser] = useState(null);
  const [portalUserMsg, setPortalUserMsg] = useState(null);
  const [welcomeEmailSending, setWelcomeEmailSending] = useState(false);
  const [welcomeEmailStatus, setWelcomeEmailStatus] = useState(null);
  const [supportSummaries, setSupportSummaries] = useState({});
  const [tokenClient, setTokenClient] = useState(null);
  const [tokenValue, setTokenValue] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [tokenMsg, setTokenMsg] = useState('');
  const [deleteCandidate, setDeleteCandidate] = useState(null);

  const fetchClients = useCallback(async () => {
    try {
      const res = await fetch("/api/clients", { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setClients(data);
        setLastUpdated(new Date().toLocaleTimeString());
        const summaryRes = await fetch('/api/support/hours-summary', { credentials: 'include' });
        if (summaryRes.ok) setSupportSummaries((await summaryRes.json()).clients || {});
      }
    } catch (err) {
      console.error('Failed to fetch clients:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchTickets = async (clientId) => {
    try {
      const res = await fetch(`/api/clients/${clientId}/tickets`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setTickets(data);
      }
    } catch (err) {
      console.error('Failed to fetch tickets:', err);
    }
  };

  const fetchHours = async (clientId) => {
    try {
      const res = await fetch(`/api/clients/${clientId}/hours`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setHoursData(data);
      }
    } catch (err) {
      console.error('Failed to fetch hours:', err);
    }
  };

  const fetchTemplates = async () => {
    try {
      const res = await fetch('/api/clients/1/tickets/templates', { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setTemplates(data);
      }
    } catch (err) {
      console.error('Failed to fetch templates:', err);
    }
  };

  // --- Portal Users Management ---
  const fetchPortalUsers = async () => {
    try {
      const res = await fetch('/api/portal/admin/portal-users', { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setPortalUsers(data);
      }
      const auditRes = await fetch('/api/portal/admin/security-audit', { credentials: 'include' });
      if (auditRes.ok) setSecurityAudit(await auditRes.json());
    } catch (err) {
      console.error('Failed to fetch portal users:', err);
    }
  };

  const createPortalUser = async (e) => {
    e.preventDefault();
    setPortalUserMsg(null);
    try {
      const res = await fetch('/api/portal/admin/portal-users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          client_id: parseInt(portalUserForm.client_id),
          name: portalUserForm.name,
          email: portalUserForm.email,
          password: portalUserForm.password,
          role: portalUserForm.role,
        }),
      });
      if (res.ok) {
        setPortalUserMsg({ type: 'success', text: 'Portal user created!' });
        setPortalUserForm({ client_id: '', name: '', email: '', password: '', role: 'viewer' });
        setShowPortalUserForm(false);
        fetchPortalUsers();
      } else {
        const data = await res.json();
        setPortalUserMsg({ type: 'error', text: data.detail || 'Failed to create user' });
      }
    } catch (err) {
      setPortalUserMsg({ type: 'error', text: 'Network error' });
    }
  };

  const updatePortalUser = async (userId, updates) => {
    try {
      const res = await fetch('/api/portal/admin/portal-users/' + userId, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(updates),
      });
      if (res.ok) {
        fetchPortalUsers();
      } else {
        const data = await res.json();
        alert(data.detail || 'Failed to update');
      }
    } catch (err) {
      alert('Network error');
    }
  };

  const resetPortalUserTwoFactor = async (user) => {
    if (!user.two_factor_enabled) return;
    const reason = prompt('Reason for resetting two-factor authentication for ' + user.name + ':');
    if (!reason || reason.trim().length < 5) { if (reason !== null) alert('A reason of at least 5 characters is required.'); return; }
    if (!confirm('Reset two-factor authentication for ' + user.name + '? Recovery codes and pending challenges will be invalidated.')) return;
    try {
      const res = await fetch('/api/portal/admin/portal-users/' + user.id + '/two-factor/reset', {
        method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm: true, reason: reason.trim() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Reset failed');
      setPortalUserMsg({ type: 'success', text: 'Two-factor authentication reset and audited for ' + user.name + '.' });
      fetchPortalUsers();
    } catch (err) { setPortalUserMsg({ type: 'error', text: err.message }); }
  };

  const deletePortalUser = async (userId) => {
    if (!confirm('Delete this portal user?')) return;
    try {
      const res = await fetch('/api/portal/admin/portal-users/' + userId, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (res.ok) {
        fetchPortalUsers();
      }
    } catch (err) {
      alert('Network error');
    }
  };


  const fetchReport = async (clientId) => {
    try {
      const res = await fetch(`/api/clients/${clientId}/report`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setReportData(data);
      }
    } catch (err) {
      console.error('Failed to fetch report:', err);
    }
  };

  useEffect(() => {
    fetchClients();
    fetchPortalUsers();
    fetchTemplates();
    const interval = setInterval(() => { fetchClients(); fetchPortalUsers(); }, 30000);
    return () => clearInterval(interval);
  }, [fetchClients]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/clients', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
        credentials: 'include',
      });
      if (res.ok) {
        setShowForm(false);
        setForm({ name: '', email: '', phone: '', subdomain: '', tier: 'basic', send_welcome_email: true });
        fetchClients();
    fetchPortalUsers();
      }
    } catch (err) {
      console.error('Failed to create client:', err);
    }
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`/api/clients/${editingClient.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm),
        credentials: 'include',
      });
      if (res.ok) {
        setShowEditForm(false);
        setEditingClient(null);
        fetchClients();
    fetchPortalUsers();
      }
    } catch (err) {
      console.error('Failed to update client:', err);
    }
  };

  const startEdit = (client) => {
    setEditingClient(client);
    setEditForm({
      name: client.name || '',
      email: client.email || '',
      phone: client.phone || '',
      subdomain: client.subdomain || '',
      tier: client.tier || 'basic',
      status: client.status || 'active',
    });
    setShowEditForm(true);
  };

  const deleteClient = (client) => setDeleteCandidate(client);

  const regenerateToken = async (client) => {
    setTokenClient(client); setShowToken(false); setTokenMsg(''); setTokenValue('');
    try {
      const res = await fetch(`/api/clients/${client.id}/tokens`, { credentials: 'include' });
      if (!res.ok) throw new Error('Unable to load token');
      const tokens = await res.json();
      setTokenValue(tokens.find(token => token.is_active)?.token || '');
    } catch (err) { setTokenMsg(err.message); }
  };

  const rotateToken = async () => {
    if (!tokenClient || !confirm('Regenerate this token? The existing Agent token will stop working immediately.')) return;
    setTokenMsg('Regenerating…');
    const res = await fetch(`/api/clients/${tokenClient.id}/tokens`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify({}) });
    if (res.ok) { const token = await res.json(); setTokenValue(token.token); setShowToken(true); setTokenMsg('Token regenerated. Update the Agent before its next report.'); fetchClients(); }
    else setTokenMsg('Token regeneration failed.');
  };

  const openClientDetails = (client) => {
    setSelectedClient(client);
    setWelcomeEmailStatus(null);
    setWelcomeEmailSending(false);
    fetchTickets(client.id);
    fetchHours(client.id);
    setShowReport(false);
    setReportData(null);
  };

  const openTemplate = (template) => {
    setTicketForm({
      title: template.title || '',
      description: template.description || '',
      priority: template.priority || 'medium',
    });
    setShowTicketForm(true);
  };

  const createTicket = async (e) => {
    e.preventDefault();
    if (!selectedClient) return;
    try {
      const res = await fetch(`/api/clients/${selectedClient.id}/tickets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ticketForm),
        credentials: 'include',
      });
      if (res.ok) {
        setTicketForm({ title: '', description: '', priority: 'medium' });
        setShowTicketForm(false);
        fetchTickets(selectedClient.id);
      }
    } catch (err) {
      console.error('Failed to create ticket:', err);
    }
  };

  const updateTicket = async (ticketId, updates) => {
    if (!selectedClient) return;
    try {
      const res = await fetch(`/api/clients/${selectedClient.id}/tickets/${ticketId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
        credentials: 'include',
      });
      if (res.ok) {
        setEditingTicket(null);
        fetchTickets(selectedClient.id);
      }
    } catch (err) {
      console.error('Failed to update ticket:', err);
    }
  };

  const deleteTicket = async (ticketId) => {
    if (!confirm('Are you sure you want to delete this ticket?')) return;
    if (!selectedClient) return;
    try {
      const res = await fetch(`/api/clients/${selectedClient.id}/tickets/${ticketId}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (res.ok) {
        fetchTickets(selectedClient.id);
      }
    } catch (err) {
      console.error('Failed to delete ticket:', err);
    }
  };

  const downloadPDF = () => {
    if (!reportData) return;
    const lines = [
      `Monthly Report - ${reportData.client?.name || 'Unknown'}`,
      `Period: ${reportData.period || ''}`,
      '',
      'Summary:',
      `  Total Tickets: ${reportData.summary?.total_tickets || 0}`,
      `  Open Tickets: ${reportData.summary?.open_tickets || 0}`,
      `  Closed Tickets: ${reportData.summary?.closed_tickets || 0}`,
      `  Total Hours Used: ${reportData.summary?.total_hours_used || 0}`,
      `  Hours Remaining: ${reportData.summary?.hours_remaining || 0}`,
      '',
      'Tickets:',
    ];
    (reportData.tickets || []).forEach((t) => {
      lines.push(`  [${t.status}] ${t.title} - ${t.hours_used || 0}h`);
    });
    const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `report-${reportData.client?.name || 'client'}-${reportData.period || 'monthly'}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const emailReport = () => {
    if (!reportData) return;
    const subject = encodeURIComponent(`Monthly Report - ${reportData.client?.name || ''}`);
    const body = encodeURIComponent(
      `Monthly Report for ${reportData.client?.name || ''}\n` +
      `Period: ${reportData.period || ''}\n\n` +
      `Total Tickets: ${reportData.summary?.total_tickets || 0}\n` +
      `Open Tickets: ${reportData.summary?.open_tickets || 0}\n` +
      `Closed Tickets: ${reportData.summary?.closed_tickets || 0}\n` +
      `Total Hours Used: ${reportData.summary?.total_hours_used || 0}\n` +
      `Hours Remaining: ${reportData.summary?.hours_remaining || 0}`
    );
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  const filteredTemplates = templateCategory === 'all'
    ? templates
    : templates.filter((t) => t.category === templateCategory);

  const categories = [...new Set(templates.map((t) => t.category).filter(Boolean))];

  const totalClients = clients.length;
  const activeClients = clients.filter((c) => c.status === 'active').length;
  const onlineNow = clients.filter((c) => c.is_online).length;
  const totalSupportTimeLogged = Object.values(supportSummaries).reduce((sum, item) => sum + Number(item.logged || 0), 0);

  const getStatusBadge = (status) => (
    <StatusBadge status={status === 'active' ? 'active' : 'inactive'} light>
      {status === 'active' ? 'Active' : 'Inactive'}
    </StatusBadge>
  );

  const getTierBadge = (tier) => {
    const t = TIERS[tier] || TIERS.basic;
    return <StatusBadge variant={t.tone}>{t.label} ({t.price})</StatusBadge>;
  };

  const getInstanceDot = (isOnline) => (
    <span className="inline-flex items-center">
      <StatusDot active={isOnline} className="mr-1.5" />
      {isOnline ? 'Online' : 'Offline'}
    </span>
  );

  // Resend welcome email
  const resendWelcomeEmail = async () => {
    const clientId = selectedClient?.id;
    if (!clientId || welcomeEmailSending) return;
    setWelcomeEmailStatus(null);
    setWelcomeEmailSending(true);
    try {
      const res = await fetch(`/api/clients/${clientId}/resend-welcome`, {
        method: 'POST',
        credentials: 'include',
      });
      let data = null;
      try {
        data = await res.json();
      } catch (_) {
        data = null;
      }
      if (res.ok) {
        const destination = data?.email ? ` to ${data.email}` : '';
        setWelcomeEmailStatus({ type: 'success', text: `Welcome email sent${destination}.` });
      } else {
        setWelcomeEmailStatus({ type: 'error', text: data?.detail || 'Failed to send welcome email.' });
      }
    } catch (err) {
      console.error('Failed to resend welcome:', err);
      setWelcomeEmailStatus({ type: 'error', text: 'Network error while sending welcome email.' });
    } finally {
      setWelcomeEmailSending(false);
    }
  };

  // Toggle email alerts for first instance
  const toggleAlerts = async () => {
    const clientId = selectedClient?.id;
    if (!clientId) return;
    const msgEl = document.getElementById('client-action-msg');
    try {
      // Get instance IDs for this client
      const instRes = await fetch(`/api/instances`, { credentials: 'include' });
      if (!instRes.ok) throw new Error('Failed to get instances');
      const instances = await instRes.json();
      let toggled = 0;
      for (const inst of instances) {
        if (inst.client_id === clientId || inst.name?.includes(selectedClient.name) || inst.id === clientId) {
          const res = await fetch(`/api/instances/${inst.id}/toggle-alerts`, {
            method: 'POST',
            credentials: 'include',
          });
          if (res.ok) toggled++;
        }
      }
      if (msgEl) {
        if (toggled > 0) { msgEl.textContent = `Alerts toggled for ${toggled} instance(s)`; msgEl.className = 'text-sm text-success-textLight'; }
        else { msgEl.textContent = 'No instances found to toggle'; msgEl.className = 'text-sm text-warning-textLight'; }
        msgEl.classList.remove('hidden');
        setTimeout(() => msgEl.classList.add('hidden'), 5000);
      }
    } catch (err) { console.error('Failed to toggle alerts:', err); }
  };

  return (
    <div className="page-shell">
      <div className="page-toolbar">
        <div>
          <h1 className="page-title">Clients</h1>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <p className="page-subtitle mt-0">Manage client accounts, portal users, tokens, support, and tunnel details.</p>
            {lastUpdated && (
              <span className="live-indicator"><StatusDot variant="success" pulse />Updated {lastUpdated}</span>
            )}
          </div>
        </div>
        <button onClick={() => setShowForm(true)} className="btn btn-primary">+ Add Client</button>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total Clients" value={totalClients} tone="primary" />
        <StatCard label="Active" value={activeClients} tone="success" />
        <StatCard label="Online Now" value={onlineNow} tone="info" />
        <StatCard label="Support Time Logged This Month" value={`${Number(totalSupportTimeLogged.toFixed(2))}h`} tone="warning" />
      </div>

      <div className="space-y-3 md:hidden">
        {clients.map(client => <div key={client.id} className="app-card app-card-compact"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="break-words font-semibold text-white">{client.name}</p><p className="break-all text-sm text-gray-400">{client.email}</p></div>{getStatusBadge(client.status)}</div><div className="mt-3 flex flex-wrap gap-2">{getTierBadge(client.tier)}<span className="text-sm text-gray-400">{getInstanceDot(client.is_online)}</span></div>{supportSummaries[client.id] && <p className="mt-3 text-sm text-gray-400">Support: {supportSummaries[client.id].logged}h logged · {supportSummaries[client.id].included}h included{Number(supportSummaries[client.id].potentially_billable)>0 ? ` · ${supportSummaries[client.id].potentially_billable}h potentially billable` : ` · ${supportSummaries[client.id].remaining}h remaining`}</p>}<div className="mt-4 grid grid-cols-3 gap-2"><button className="btn btn-secondary" onClick={()=>openClientDetails(client)}>Details</button><button className="btn btn-secondary" onClick={()=>startEdit(client)}>Edit</button><button className="btn btn-secondary" onClick={()=>regenerateToken(client)}>Token</button></div><div className="mt-4 border-t border-red-400/20 pt-3"><button className="btn btn-danger w-full" onClick={()=>deleteClient(client)}>Delete client…</button></div></div>)}
      </div>

      <DataTable className="hidden md:block"
        columns={[{ label: 'Client' }, { label: 'Tier' }, { label: 'Status' }, { label: 'Instance' }, { label: 'Token' }, { label: 'Actions' }]}
        colSpan={6}
      >
        {loading ? (
          <tr><td colSpan="6" className="table-empty">Loading...</td></tr>
        ) : clients.length === 0 ? (
          <tr><td colSpan="6" className="table-empty">No clients found</td></tr>
        ) : (
          clients.map((client) => (
            <tr key={client.id} className="transition hover:bg-white/[0.03]">
              <td className="px-4 py-4">
                <div className="font-medium text-white">{client.name}</div>
                <div className="text-sm text-muted-text">{client.email}</div>
                {supportSummaries[client.id] && <div className="mt-1 text-xs text-gray-500">Support: {supportSummaries[client.id].logged}h logged · {supportSummaries[client.id].included}h included{Number(supportSummaries[client.id].potentially_billable) > 0 ? ` · ${supportSummaries[client.id].potentially_billable}h potentially billable` : ` · ${supportSummaries[client.id].remaining}h remaining`}</div>}
              </td>
              <td className="px-4 py-4">{getTierBadge(client.tier)}</td>
              <td className="px-4 py-4">{getStatusBadge(client.status)}</td>
              <td className="px-4 py-4 text-sm text-muted-text">{getInstanceDot(client.is_online)}</td>
              <td className="px-4 py-4 text-sm">
                {client.active_token ? (
                  <ActionLink
                    onClick={() => copyToClipboard(client.active_token)}
                    variant="primary"
                    className="font-mono text-xs"
                    title="Click to copy"
                  >
                    {client.active_token.substring(0, 8)}...
                  </ActionLink>
                ) : (
                  <span className="text-muted-text">No token</span>
                )}
              </td>
              <td className="px-4 py-4 text-sm font-medium">
                <div className="flex flex-wrap gap-3">
                  <ActionLink onClick={() => openClientDetails(client)} variant="primary">Details</ActionLink>
                  <ActionLink onClick={() => startEdit(client)} variant="info">Edit</ActionLink>
                  <ActionLink onClick={() => regenerateToken(client)} variant="success">Token</ActionLink>
                  <ActionLink onClick={() => deleteClient(client)} variant="danger">Delete</ActionLink>
                </div>
              </td>
            </tr>
          ))
        )}
      </DataTable>

      <div className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-xl font-semibold text-white">Portal Users</h2>
          <button onClick={() => setShowPortalUserForm(!showPortalUserForm)} className="btn btn-primary">
            {showPortalUserForm ? 'Cancel' : '+ Add User'}
          </button>
        </div>

        {portalUserMsg && (
          <div className={portalUserMsg.type === 'success' ? 'alert-success py-2 text-sm' : 'alert-error py-2 text-sm'}>
            {portalUserMsg.text}
          </div>
        )}

        {showPortalUserForm && (
          <div className="section-card-light">
            <h3 className="mb-3 font-semibold text-white">Create Portal User</h3>
            <form onSubmit={createPortalUser} className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <select value={portalUserForm.client_id} onChange={(e) => setPortalUserForm({ ...portalUserForm, client_id: e.target.value })} className="form-input" required>
                <option value="">Select Client</option>
                {clients.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <input type="text" placeholder="Full Name" value={portalUserForm.name} onChange={(e) => setPortalUserForm({ ...portalUserForm, name: e.target.value })} className="form-input" required />
              <input type="email" placeholder="Email" value={portalUserForm.email} onChange={(e) => setPortalUserForm({ ...portalUserForm, email: e.target.value })} className="form-input" required />
              <input type="password" placeholder="Password (min 6 chars)" value={portalUserForm.password} onChange={(e) => setPortalUserForm({ ...portalUserForm, password: e.target.value })} className="form-input" required />
              <select value={portalUserForm.role} onChange={(e) => setPortalUserForm({ ...portalUserForm, role: e.target.value })} className="form-input">
                <option value="viewer">Viewer</option>
                <option value="admin">Admin</option>
              </select>
              <button type="submit" className="btn btn-success">Create</button>
            </form>
          </div>
        )}

        <div className="space-y-3 md:hidden">
          {portalUsers.map(user => <div key={user.id} className="app-card app-card-compact"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="font-medium text-white">{user.name}</p><p className="break-all text-sm text-gray-400">{user.email}</p><p className="mt-1 text-sm text-gray-500">{user.client_name || 'No client'}</p><p className="mt-1 text-xs text-gray-400">2FA: {user.two_factor_enabled ? 'Enabled' : 'Disabled'}</p></div><StatusBadge status={user.is_active ? 'active' : 'disabled'}>{user.is_active ? 'Active' : 'Disabled'}</StatusBadge></div><div className="mt-4 grid grid-cols-2 gap-2"><button className="btn btn-secondary" onClick={() => updatePortalUser(user.id, { is_active: !user.is_active })}>{user.is_active ? 'Disable' : 'Enable'}</button>{user.two_factor_enabled && <button className="btn btn-danger" onClick={() => resetPortalUserTwoFactor(user)}>Reset 2FA…</button>}<button className="btn btn-danger" onClick={() => deletePortalUser(user.id)}>Delete user…</button></div></div>)}
        </div>
        <DataTable className="hidden md:block"
          columns={[{ label: 'Name' }, { label: 'Email' }, { label: 'Client' }, { label: 'Role' }, { label: 'Status' }, { label: 'Last Login' }, { label: 'Actions', align: 'right' }]}
          colSpan={7}
        >
          {portalUsers.length === 0 ? (
            <tr><td colSpan="7" className="table-empty">No portal users yet. Click "+ Add User" to create one.</td></tr>
          ) : (
            portalUsers.map(u => (
              <tr key={u.id} className="transition hover:bg-white/[0.03]">
                <td className="px-4 py-3 font-medium text-white">{u.name}</td>
                <td className="px-4 py-3 text-muted-text">{u.email}</td>
                <td className="px-4 py-3 text-muted-text">{u.client_name || '—'}</td>
                <td className="px-4 py-3"><StatusBadge status={u.role} light>{u.role}</StatusBadge></td>
                <td className="px-4 py-3"><StatusBadge status={u.is_active ? 'active' : 'disabled'} light>{u.is_active ? 'Active' : 'Disabled'}</StatusBadge></td>
                <td className="px-4 py-3 text-xs text-muted-text">{u.last_login ? new Date(u.last_login).toLocaleDateString() : 'Never'}</td>
                <td className="px-4 py-3 text-right">
                  <div className="flex flex-wrap justify-end gap-2">
                    <ActionLink onClick={() => updatePortalUser(u.id, { is_active: !u.is_active })} variant={u.is_active ? 'warning' : 'success'} className="text-xs">
                      {u.is_active ? 'Disable' : 'Enable'}
                    </ActionLink>
                    <ActionLink
                      onClick={() => {
                        const newPass = prompt('New password for ' + u.name + ' (min 6 chars):');
                        if (newPass && newPass.length >= 6) updatePortalUser(u.id, { password: newPass });
                        else if (newPass) alert('Password must be at least 6 characters');
                      }}
                      variant="info"
                      className="text-xs"
                    >
                      Reset PW
                    </ActionLink>
                    {u.two_factor_enabled && <ActionLink onClick={() => resetPortalUserTwoFactor(u)} variant="warning" className="text-xs">Reset 2FA</ActionLink>}
                    <ActionLink onClick={() => deletePortalUser(u.id)} variant="danger" className="text-xs">Delete</ActionLink>
                  </div>
                </td>
              </tr>
            ))
          )}
        </DataTable>
        {securityAudit.length > 0 && <div className="section-card-light mt-5"><h3 className="font-semibold text-white">Two-factor reset audit</h3><div className="mt-3 space-y-2">{securityAudit.slice(0, 10).map(event => <div key={event.id} className="rounded-lg border border-white/10 p-3 text-sm"><p className="text-white">Portal user #{event.client_user_id} reset by {event.administrator}</p><p className="mt-1 text-gray-400">{event.reason} · {event.created_at ? new Date(event.created_at).toLocaleString() : 'Unknown time'}</p></div>)}</div></div>}
      </div>


      {tokenClient && (
        <Modal className="max-h-[85vh] overflow-y-auto p-6" maxWidth="max-w-lg">
          <div className="flex items-start justify-between gap-3"><div><h2 className="text-xl font-semibold text-white">Subscription token</h2><p className="text-sm text-gray-400">{tokenClient.name}</p></div><button className="btn btn-secondary" onClick={()=>setTokenClient(null)}>Close</button></div>
          <div className="mt-5 rounded-lg border border-white/10 p-3"><p className="break-all font-mono text-sm text-white">{tokenValue ? (showToken ? tokenValue : '••••••••••••••••••••••••••••••••') : 'No active token'}</p></div>
          <div className="mt-4 flex flex-col gap-2 sm:flex-row"><button className="btn btn-secondary" onClick={()=>setShowToken(!showToken)} disabled={!tokenValue}>{showToken?'Hide token':'Show token'}</button><button className="btn btn-secondary" onClick={()=>copyToClipboard(tokenValue)} disabled={!tokenValue}>Copy token</button><button className="btn btn-danger sm:ml-auto" onClick={rotateToken}>Regenerate token</button></div>
          <p className="mt-3 text-sm text-amber-200">Regeneration invalidates the token currently used by the Agent and always requires confirmation.</p>{tokenMsg&&<p className="mt-2 text-sm text-purple-200" role="status">{tokenMsg}</p>}
        </Modal>
      )}

      {deleteCandidate && (
        <Modal className="p-6" maxWidth="max-w-lg"><h2 className="text-xl font-semibold text-white">Delete {deleteCandidate.name}?</h2><p className="mt-3 text-sm text-gray-300">Client deletion is disabled because the current data relationships would also remove instances, portal users, tokens, support tickets, and backup records. Tunnel cleanup is not transactionally coordinated.</p><p className="mt-3 text-sm text-amber-200">No records have been changed.</p><div className="mt-5 flex justify-end"><button className="btn btn-secondary" onClick={()=>setDeleteCandidate(null)}>Close</button></div></Modal>
      )}
      {showForm && (
        <Modal className="p-6" maxWidth="max-w-md">
          <h2 className="mb-4 text-xl font-semibold text-white">Add New Client</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div><label className="form-label">Name</label><input type="text" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="form-input" /></div>
            <div><label className="form-label">Email</label><input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="form-input" /></div>
            <div><label className="form-label">Phone</label><input type="tel" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="form-input" /></div>
            <div>
              <label className="form-label">Subdomain</label>
              <div className="flex items-center">
                <input type="text" required value={form.subdomain} onChange={(e) => setForm({ ...form, subdomain: e.target.value })} className="form-input-attached-left" />
                <span className="form-addon-right">.mybeacon.co.za</span>
              </div>
            </div>
            <div>
              <label className="form-label">Tier</label>
              <select value={form.tier} onChange={(e) => setForm({ ...form, tier: e.target.value })} className="form-input">
                {Object.entries(TIERS).map(([key, val]) => <option key={key} value={key}>{val.label} - {val.price} ({val.hours}h included)</option>)}
              </select>
            </div>
            <div className="flex items-center">
              <input type="checkbox" id="send-welcome" checked={form.send_welcome_email !== false} onChange={(e) => setForm({ ...form, send_welcome_email: e.target.checked })} className="form-checkbox" />
              <label htmlFor="send-welcome" className="ml-2 text-sm text-muted-text">Send welcome email with credentials</label>
            </div>
            <div className="flex justify-end gap-3 pt-4">
              <button type="button" onClick={() => { setShowForm(false); setForm({ name: '', email: '', phone: '', subdomain: '', tier: 'basic', send_welcome_email: true }); }} className="btn btn-secondary">Cancel</button>
              <button type="submit" className="btn btn-primary">Create Client</button>
            </div>
          </form>
        </Modal>
      )}

      {showEditForm && editingClient && (
        <Modal className="p-6" maxWidth="max-w-md">
          <h2 className="mb-4 text-xl font-semibold text-white">Edit Client</h2>
          <form onSubmit={handleEditSubmit} className="space-y-4">
            <div><label className="form-label">Name</label><input type="text" required value={editForm.name} onChange={(e) => setEditForm({ ...editForm, name: e.target.value })} className="form-input" /></div>
            <div><label className="form-label">Email</label><input type="email" required value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} className="form-input" /></div>
            <div><label className="form-label">Phone</label><input type="tel" value={editForm.phone} onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })} className="form-input" /></div>
            <div>
              <label className="form-label">Subdomain</label>
              <div className="flex items-center">
                <input type="text" required value={editForm.subdomain} onChange={(e) => setEditForm({ ...editForm, subdomain: e.target.value })} className="form-input-attached-left" />
                <span className="form-addon-right">.mybeacon.co.za</span>
              </div>
            </div>
            <div>
              <label className="form-label">Tier</label>
              <select value={editForm.tier} onChange={(e) => setEditForm({ ...editForm, tier: e.target.value })} className="form-input">
                {Object.entries(TIERS).map(([key, val]) => <option key={key} value={key}>{val.label} - {val.price} ({val.hours}h included)</option>)}
              </select>
            </div>
            <div>
              <label className="form-label">Status</label>
              <select value={editForm.status} onChange={(e) => setEditForm({ ...editForm, status: e.target.value })} className="form-input">
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
            <div className="flex justify-end gap-3 pt-4">
              <button type="button" onClick={() => { setShowEditForm(false); setEditingClient(null); }} className="btn btn-secondary">Cancel</button>
              <button type="submit" className="btn btn-primary">Save Changes</button>
            </div>
          </form>
        </Modal>
      )}

      {selectedClient && (
        <Modal className="max-h-[90vh] overflow-y-auto" maxWidth="max-w-5xl">
          <div className="flex items-center justify-between border-b border-white/10 p-6">
            <div className="flex items-center gap-4">
              <h2 className="text-xl font-semibold text-white">{selectedClient.name}</h2>
              <button onClick={() => { setShowReport(!showReport); if (!showReport) fetchReport(selectedClient.id); }} className={`btn px-3 py-1 ${showReport ? 'btn-primary' : 'btn-secondary'}`}>
                {showReport ? 'Tickets' : 'Report'}
              </button>
            </div>
            <button onClick={() => { setSelectedClient(null); setShowReport(false); setReportData(null); }} className="text-2xl leading-none text-muted-text hover:text-white">&times;</button>
          </div>

          <div className="p-6">
            {showReport && reportData && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                  <div className="info-card-light"><p className="text-sm text-muted-text">Total Tickets</p><p className="text-2xl font-semibold text-white">{reportData.summary?.total_tickets || 0}</p></div>
                  <div className="info-card-light"><p className="text-sm text-muted-text">Open Tickets</p><p className="text-2xl font-semibold text-warning-text">{reportData.summary?.open_tickets || 0}</p></div>
                  <div className="info-card-light"><p className="text-sm text-muted-text">Closed Tickets</p><p className="text-2xl font-semibold text-success-text">{reportData.summary?.closed_tickets || 0}</p></div>
                  <div className="info-card-light"><p className="text-sm text-muted-text">Hours Used</p><p className="text-2xl font-semibold text-info-text">{reportData.summary?.total_hours_used || 0}h</p></div>
                  <div className="info-card-light"><p className="text-sm text-muted-text">Hours Remaining</p><p className="text-2xl font-semibold text-primary-text">{reportData.summary?.hours_remaining || 0}h</p></div>
                  <div className="info-card-light"><p className="text-sm text-muted-text">Period</p><p className="text-lg font-semibold text-white">{reportData.period || ''}</p></div>
                </div>

                <div className="flex gap-3">
                  <button onClick={downloadPDF} className="btn btn-primary">Download Report</button>
                  <button onClick={emailReport} className="btn btn-success">Email Report</button>
                </div>

                <div>
                  <h3 className="mb-3 text-lg font-semibold text-white">Tickets</h3>
                  <div className="space-y-2">
                    {(reportData.tickets || []).map((ticket) => (
                      <div key={ticket.id} className="section-card-light flex items-center justify-between gap-4">
                        <div>
                          <p className="font-medium text-white">{ticket.title}</p>
                          <p className="text-sm text-muted-text">{ticket.description}</p>
                        </div>
                        <div className="flex items-center gap-3">
                          <StatusBadge status={ticket.status} light>{ticket.status}</StatusBadge>
                          <span className="text-sm text-muted-text">{ticket.hours_used || 0}h</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {!showReport && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="info-card-light"><p className="text-sm text-muted-text">Email</p><p className="font-medium text-white">{selectedClient.email}</p></div>
                  <div className="info-card-light"><p className="text-sm text-muted-text">Phone</p><p className="font-medium text-white">{selectedClient.phone || 'N/A'}</p></div>
                  <div className="info-card-light"><p className="text-sm text-muted-text">Portal URL</p><p className="font-medium text-primary-text">{selectedClient.portal_url || `https://${selectedClient.subdomain}.mybeacon.co.za`}</p></div>
                  <div className="info-card-light"><p className="text-sm text-muted-text">Tier</p><p>{getTierBadge(selectedClient.tier)}</p></div>
                </div>

                {hoursData && (
                  <div className="section-card-light">
                    <h3 className="mb-3 text-sm font-semibold text-white">Hours Usage</h3>
                    <div className="mb-2 flex items-center justify-between text-sm text-muted-text">
                      <span>{hoursData.monthly_hours_used || 0}h used</span>
                      <span>{hoursData.monthly_hours_total || 0}h total</span>
                    </div>
                    <ProgressBar value={hoursData.monthly_hours_used || 0} max={hoursData.monthly_hours_total || 1} />
                    <p className="mt-2 text-sm text-muted-text">{hoursData.hours_remaining || 0}h remaining</p>
                  </div>
                )}

                <div className="section-card-light">
                  <h3 className="mb-3 text-sm font-semibold text-white">Client Communications</h3>
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      onClick={resendWelcomeEmail}
                      disabled={welcomeEmailSending}
                      className="btn btn-primary px-3 py-1.5 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {welcomeEmailSending ? 'Sending...' : 'Resend Welcome Email'}
                    </button>
                    <button onClick={toggleAlerts} className="btn btn-warning px-3 py-1.5">Toggle Email Alerts</button>
                    {welcomeEmailStatus && (
                      <span className={welcomeEmailStatus.type === 'success' ? 'text-sm text-success-textLight' : 'text-sm text-danger-textLight'}>
                        {welcomeEmailStatus.text}
                      </span>
                    )}
                    <span id="client-action-msg" className="hidden text-sm text-success-textLight"></span>
                  </div>
                </div>

                {selectedClient.active_token && (
                  <div className="section-card-light">
                    <h3 className="mb-2 text-sm font-semibold text-white">Active Token</h3>
                    <div className="flex items-center gap-2">
                      <code className="rounded bg-black/30 px-3 py-1 font-mono text-sm text-gray-200">{selectedClient.active_token}</code>
                      <ActionLink onClick={() => copyToClipboard(selectedClient.active_token)} variant="primary">Copy</ActionLink>
                    </div>
                  </div>
                )}

                <div className="section-card-light">
                  <h3 className="mb-3 text-sm font-semibold text-white">Cloudflare Tunnel</h3>
                  {selectedClient.cloudflare_tunnel_id ? (
                    <div>
                      <div className="mb-2 flex items-center gap-2"><StatusDot active /><span className="text-sm text-gray-300">Tunnel Active</span></div>
                      <p className="mb-2 text-sm text-muted-text">ID: {selectedClient.cloudflare_tunnel_id}</p>
                      <ActionLink onClick={() => { if (confirm('Delete this tunnel?')) { /* API call to delete tunnel */ } }} variant="danger">Delete Tunnel</ActionLink>
                    </div>
                  ) : (
                    <div>
                      <p className="mb-2 text-sm text-muted-text">No tunnel configured</p>
                      <button onClick={() => { /* API call to create tunnel */ }} className="btn btn-primary px-3 py-1">Create Tunnel</button>
                    </div>
                  )}
                </div>

                <div className="section-card-light">
                  <h3 className="mb-3 text-sm font-semibold text-white">Templates</h3>
                  {categories.length > 0 && (
                    <div className="mb-3 flex flex-wrap gap-2">
                      <button onClick={() => setTemplateCategory('all')} className={`badge px-3 py-1 ${templateCategory === 'all' ? 'badge-primary' : 'badge-neutral'}`}>All</button>
                      {categories.map((cat) => (
                        <button key={cat} onClick={() => setTemplateCategory(cat)} className={`badge px-3 py-1 ${templateCategory === cat ? 'badge-primary' : 'badge-neutral'}`}>{cat}</button>
                      ))}
                    </div>
                  )}
                  <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                    {filteredTemplates.map((template) => (
                      <button key={template.id} onClick={() => openTemplate(template)} className="section-card-light text-left transition hover:border-primary/40 hover:bg-white/[0.06]">
                        <p className="text-sm font-medium text-white">{template.title}</p>
                        <p className="text-xs text-muted-text">{template.description}</p>
                        <p className="mt-1 text-xs text-muted-text">{template.hours_used || 0}h</p>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="section-card-light">
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-white">Tickets</h3>
                    <button onClick={() => setShowTicketForm(!showTicketForm)} className="btn btn-primary px-3 py-1">{showTicketForm ? 'Cancel' : '+ New Ticket'}</button>
                  </div>

                  {showTicketForm && (
                    <form onSubmit={createTicket} className="info-card-light mb-4 space-y-3">
                      <div><label className="form-label">Title</label><input type="text" required value={ticketForm.title} onChange={(e) => setTicketForm({ ...ticketForm, title: e.target.value })} className="form-input" /></div>
                      <div><label className="form-label">Description</label><textarea value={ticketForm.description} onChange={(e) => setTicketForm({ ...ticketForm, description: e.target.value })} className="form-input" rows="2" /></div>
                      <div><label className="form-label">Priority</label><select value={ticketForm.priority} onChange={(e) => setTicketForm({ ...ticketForm, priority: e.target.value })} className="form-input"><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></div>
                      <button type="submit" className="btn btn-primary">Create Ticket</button>
                    </form>
                  )}

                  <div className="space-y-2">
                    {tickets.map((ticket) => (
                      <div key={ticket.id} className="section-card-light p-3">
                        {editingTicket && editingTicket.id === ticket.id ? (
                          <div className="space-y-2">
                            <input type="text" value={editingTicket.title} onChange={(e) => setEditingTicket({ ...editingTicket, title: e.target.value })} className="form-input px-2 py-1" />
                            <textarea value={editingTicket.description || ''} onChange={(e) => setEditingTicket({ ...editingTicket, description: e.target.value })} className="form-input px-2 py-1" rows="2" />
                            <div className="flex flex-wrap items-center gap-2">
                              <input type="date" value={editingTicket.completed_at ? editingTicket.completed_at.substring(0, 10) : ''} onChange={(e) => setEditingTicket({ ...editingTicket, completed_at: e.target.value })} className="form-input w-auto px-2 py-1" />
                              <input type="time" value={editingTicket.completed_at ? editingTicket.completed_at.substring(11, 16) : ''} onChange={(e) => { const date = editingTicket.completed_at ? editingTicket.completed_at.substring(0, 10) : new Date().toISOString().substring(0, 10); setEditingTicket({ ...editingTicket, completed_at: `${date}T${e.target.value}` }); }} className="form-input w-auto px-2 py-1" />
                              <input type="number" value={editingTicket.hours_used || 0} onChange={(e) => setEditingTicket({ ...editingTicket, hours_used: parseFloat(e.target.value) || 0 })} className="form-input w-20 px-2 py-1" step="0.5" min="0" />
                              <span className="text-xs text-muted-text">hours</span>
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                              <select value={editingTicket.status} onChange={(e) => setEditingTicket({ ...editingTicket, status: e.target.value })} className="form-input w-auto px-2 py-1"><option value="open">Open</option><option value="in_progress">In Progress</option><option value="closed">Closed</option></select>
                              <button onClick={() => updateTicket(ticket.id, editingTicket)} className="btn btn-success px-3 py-1">Save</button>
                              <button onClick={() => setEditingTicket(null)} className="btn btn-secondary px-3 py-1">Cancel</button>
                            </div>
                          </div>
                        ) : (
                          <div className="flex items-center justify-between gap-4">
                            <div>
                              <p className="text-sm font-medium text-white">{ticket.title}</p>
                              <p className="text-xs text-muted-text">{ticket.description}</p>
                              <div className="mt-1 flex flex-wrap items-center gap-3">
                                <StatusBadge status={ticket.status} light>{ticket.status}</StatusBadge>
                                <span className="text-xs text-muted-text">{ticket.hours_used || 0}h</span>
                                {ticket.created_at && <span className="text-xs text-muted-text">{new Date(ticket.created_at).toLocaleDateString()}</span>}
                                {ticket.completed_at && <span className="text-xs text-muted-text">Done: {new Date(ticket.completed_at).toLocaleDateString()}</span>}
                              </div>
                            </div>
                            <div className="flex items-center gap-2">
                              <ActionLink onClick={() => setEditingTicket({ ...ticket })} variant="primary" className="text-xs">Edit</ActionLink>
                              <ActionLink onClick={() => deleteTicket(ticket.id)} variant="danger" className="text-xs">Delete</ActionLink>
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                    {tickets.length === 0 && <p className="py-4 text-center text-sm text-muted-text">No tickets yet</p>}
                  </div>
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
