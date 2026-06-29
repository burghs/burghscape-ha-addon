import { useState, useEffect, useCallback } from 'react';

const TIERS = {
  basic: { label: 'Basic', price: 'R199', color: 'bg-gray-500', hours: 2 },
  standard: { label: 'Standard', price: 'R499', color: 'bg-blue-500', hours: 2 },
  premium: { label: 'Premium', price: 'R899', color: 'bg-purple-500', hours: 5 },
};

export default function Clients() {
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [showEditForm, setShowEditForm] = useState(false);
  const [editingClient, setEditingClient] = useState(null);
  const [form, setForm] = useState({ name: '', email: '', phone: '', subdomain: '', tier: 'basic' });
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
  const [showPortalUserForm, setShowPortalUserForm] = useState(false);
  const [portalUserForm, setPortalUserForm] = useState({ client_id: '', name: '', email: '', password: '', role: 'viewer' });
  const [editingPortalUser, setEditingPortalUser] = useState(null);
  const [portalUserMsg, setPortalUserMsg] = useState(null);

  const fetchClients = useCallback(async () => {
    try {
      const res = await fetch("/api/clients", { credentials: "include" });
      if (res.ok) {
        const data = await res.json();
        setClients(data);
        setLastUpdated(new Date().toLocaleTimeString());
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
        setForm({ name: '', email: '', phone: '', subdomain: '', tier: 'basic' });
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

  const deleteClient = async (clientId, name) => {
    if (!confirm(`Are you sure you want to delete client "${name}"?`)) return;
    try {
      const res = await fetch(`/api/clients/${clientId}`, { method: 'DELETE',
        credentials: 'include' });
      if (res.ok) {
        fetchClients();
    fetchPortalUsers();
        if (selectedClient && selectedClient.id === clientId) {
          setSelectedClient(null);
        }
      }
    } catch (err) {
      console.error('Failed to delete client:', err);
    }
  };

  const regenerateToken = async (clientId) => {
    try {
      const res = await fetch(`/api/clients/${clientId}/tokens`, { method: 'POST',
        credentials: 'include' });
      if (res.ok) {
        fetchClients();
    fetchPortalUsers();
      }
    } catch (err) {
      console.error('Failed to regenerate token:', err);
    }
  };

  const openClientDetails = (client) => {
    setSelectedClient(client);
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
  const totalHoursRemaining = clients.reduce((sum, c) => sum + (c.hours_remaining || 0), 0);

  const getStatusBadge = (status) => {
    const isActive = status === 'active';
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${isActive ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
        {isActive ? 'Active' : 'Inactive'}
      </span>
    );
  };

  const getTierBadge = (tier) => {
    const t = TIERS[tier] || TIERS.basic;
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium text-white ${t.color}`}>
        {t.label} ({t.price})
      </span>
    );
  };

  const getInstanceDot = (isOnline) => (
    <span className="inline-flex items-center">
      <span className={`h-2.5 w-2.5 rounded-full mr-1.5 ${isOnline ? 'bg-green-500' : 'bg-gray-400'}`}></span>
      {isOnline ? 'Online' : 'Offline'}
    </span>
  );

  const getTicketStatusColor = (status) => {
    switch (status) {
      case 'open': return 'bg-yellow-100 text-yellow-800';
      case 'in_progress': return 'bg-blue-100 text-blue-800';
      case 'closed': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Clients</h1>
          <div className="flex items-center mt-1">
            <p className="text-sm text-gray-500 mr-2">Manage your client instances</p>
            {lastUpdated && (
              <span className="flex items-center text-xs text-gray-400">
                <span className="relative flex h-2 w-2 mr-1">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                </span>
                Updated {lastUpdated}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium transition-colors"
        >
          + Add Client
        </button>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-xl shadow p-6">
          <p className="text-sm font-medium text-gray-500">Total Clients</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">{totalClients}</p>
        </div>
        <div className="bg-white rounded-xl shadow p-6">
          <p className="text-sm font-medium text-gray-500">Active</p>
          <p className="text-3xl font-bold text-green-600 mt-2">{activeClients}</p>
        </div>
        <div className="bg-white rounded-xl shadow p-6">
          <p className="text-sm font-medium text-gray-500">Online Now</p>
          <p className="text-3xl font-bold text-blue-600 mt-2">{onlineNow}</p>
        </div>
        <div className="bg-white rounded-xl shadow p-6">
          <p className="text-sm font-medium text-gray-500">Hours Remaining</p>
          <p className="text-3xl font-bold text-purple-600 mt-2">{totalHoursRemaining}h</p>
        </div>
      </div>

      {/* Client Table */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Client</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tier</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Instance</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Token</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {loading ? (
              <tr>
                <td colSpan="6" className="px-6 py-8 text-center text-gray-500">Loading...</td>
              </tr>
            ) : clients.length === 0 ? (
              <tr>
                <td colSpan="6" className="px-6 py-8 text-center text-gray-500">No clients found</td>
              </tr>
            ) : (
              clients.map((client) => (
                <tr key={client.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{client.name}</div>
                    <div className="text-sm text-gray-500">{client.email}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">{getTierBadge(client.tier)}</td>
                  <td className="px-6 py-4 whitespace-nowrap">{getStatusBadge(client.status)}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{getInstanceDot(client.is_online)}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    {client.active_token ? (
                      <button
                        onClick={() => copyToClipboard(client.active_token)}
                        className="text-indigo-600 hover:text-indigo-900 font-mono text-xs"
                        title="Click to copy"
                      >
                        {client.active_token.substring(0, 8)}...
                      </button>
                    ) : (
                      <span className="text-gray-400">No token</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-2">
                    <button
                      onClick={() => openClientDetails(client)}
                      className="text-indigo-600 hover:text-indigo-900"
                    >
                      Details
                    </button>
                    <button
                      onClick={() => startEdit(client)}
                      className="text-blue-600 hover:text-blue-900"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => regenerateToken(client.id)}
                      className="text-green-600 hover:text-green-900"
                    >
                      Token
                    </button>
                    <button
                      onClick={() => deleteClient(client.id, client.name)}
                      className="text-red-600 hover:text-red-900"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Portal Users Management */}
      <div className="mt-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-gray-900">Portal Users</h2>
          <button
            onClick={() => setShowPortalUserForm(!showPortalUserForm)}
            className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition"
          >
            {showPortalUserForm ? 'Cancel' : '+ Add User'}
          </button>
        </div>

        {portalUserMsg && (
          <div className={`mb-4 text-sm rounded-lg px-3 py-2 ${portalUserMsg.type === 'success' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
            {portalUserMsg.text}
          </div>
        )}

        {showPortalUserForm && (
          <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
            <h3 className="font-semibold text-gray-900 mb-3">Create Portal User</h3>
            <form onSubmit={createPortalUser} className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <select
                value={portalUserForm.client_id}
                onChange={(e) => setPortalUserForm({ ...portalUserForm, client_id: e.target.value })}
                className="bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 text-sm"
                required
              >
                <option value="">Select Client</option>
                {clients.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
              <input
                type="text"
                placeholder="Full Name"
                value={portalUserForm.name}
                onChange={(e) => setPortalUserForm({ ...portalUserForm, name: e.target.value })}
                className="bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 text-sm"
                required
              />
              <input
                type="email"
                placeholder="Email"
                value={portalUserForm.email}
                onChange={(e) => setPortalUserForm({ ...portalUserForm, email: e.target.value })}
                className="bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 text-sm"
                required
              />
              <input
                type="password"
                placeholder="Password (min 6 chars)"
                value={portalUserForm.password}
                onChange={(e) => setPortalUserForm({ ...portalUserForm, password: e.target.value })}
                className="bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 text-sm"
                required
              />
              <select
                value={portalUserForm.role}
                onChange={(e) => setPortalUserForm({ ...portalUserForm, role: e.target.value })}
                className="bg-gray-50 border border-gray-300 rounded-lg px-3 py-2 text-sm"
              >
                <option value="viewer">Viewer</option>
                <option value="admin">Admin</option>
              </select>
              <button type="submit" className="bg-green-600 hover:bg-green-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition">
                Create
              </button>
            </form>
          </div>
        )}

        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Name</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Email</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Client</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Role</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Last Login</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {portalUsers.length === 0 ? (
                <tr><td colSpan="7" className="px-4 py-8 text-center text-gray-400">No portal users yet. Click "+ Add User" to create one.</td></tr>
              ) : (
                portalUsers.map(u => (
                  <tr key={u.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-medium text-gray-900">{u.name}</td>
                    <td className="px-4 py-3 text-gray-600">{u.email}</td>
                    <td className="px-4 py-3 text-gray-600">{u.client_name || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${u.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'}`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${u.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                        {u.is_active ? 'Active' : 'Disabled'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{u.last_login ? new Date(u.last_login).toLocaleDateString() : 'Never'}</td>
                    <td className="px-4 py-3 text-right space-x-2">
                      <button
                        onClick={() => updatePortalUser(u.id, { is_active: !u.is_active })}
                        className={`text-xs px-2 py-1 rounded ${u.is_active ? 'text-orange-600 hover:bg-orange-50' : 'text-green-600 hover:bg-green-50'}`}
                      >
                        {u.is_active ? 'Disable' : 'Enable'}
                      </button>
                      <button
                        onClick={() => {
                          const newPass = prompt('New password for ' + u.name + ' (min 6 chars):');
                          if (newPass && newPass.length >= 6) updatePortalUser(u.id, { password: newPass });
                          else if (newPass) alert('Password must be at least 6 characters');
                        }}
                        className="text-xs px-2 py-1 rounded text-blue-600 hover:bg-blue-50"
                      >
                        Reset PW
                      </button>
                      <button
                        onClick={() => deletePortalUser(u.id)}
                        className="text-xs px-2 py-1 rounded text-red-600 hover:bg-red-50"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Client Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Add New Client</h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  type="text"
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  required
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                <input
                  type="tel"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Subdomain</label>
                <div className="flex items-center">
                  <input
                    type="text"
                    required
                    value={form.subdomain}
                    onChange={(e) => setForm({ ...form, subdomain: e.target.value })}
                    className="w-full border border-gray-300 rounded-l-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                  <span className="bg-gray-100 border border-l-0 border-gray-300 rounded-r-lg px-3 py-2 text-gray-500 text-sm">.mybeacon.co.za</span>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Tier</label>
                <select
                  value={form.tier}
                  onChange={(e) => setForm({ ...form, tier: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                >
                  {Object.entries(TIERS).map(([key, val]) => (
                    <option key={key} value={key}>{val.label} - {val.price} ({val.hours}h included)</option>
                  ))}
                </select>
              </div>
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => { setShowForm(false); setForm({ name: '', email: '', phone: '', subdomain: '', tier: 'basic' }); }}
                  className="px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg"
                >
                  Create Client
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Client Modal */}
      {showEditForm && editingClient && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Edit Client</h2>
            <form onSubmit={handleEditSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  type="text"
                  required
                  value={editForm.name}
                  onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                <input
                  type="email"
                  required
                  value={editForm.email}
                  onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                <input
                  type="tel"
                  value={editForm.phone}
                  onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Subdomain</label>
                <div className="flex items-center">
                  <input
                    type="text"
                    required
                    value={editForm.subdomain}
                    onChange={(e) => setEditForm({ ...editForm, subdomain: e.target.value })}
                    className="w-full border border-gray-300 rounded-l-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  />
                  <span className="bg-gray-100 border border-l-0 border-gray-300 rounded-r-lg px-3 py-2 text-gray-500 text-sm">.mybeacon.co.za</span>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Tier</label>
                <select
                  value={editForm.tier}
                  onChange={(e) => setEditForm({ ...editForm, tier: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                >
                  {Object.entries(TIERS).map(([key, val]) => (
                    <option key={key} value={key}>{val.label} - {val.price} ({val.hours}h included)</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                <select
                  value={editForm.status}
                  onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </div>
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => { setShowEditForm(false); setEditingClient(null); }}
                  className="px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg"
                >
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Client Details Modal */}
      {selectedClient && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-4xl max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <div className="flex items-center space-x-4">
                <h2 className="text-xl font-bold text-gray-900">{selectedClient.name}</h2>
                <button
                  onClick={() => { setShowReport(!showReport); if (!showReport) fetchReport(selectedClient.id); }}
                  className={`px-3 py-1 rounded-lg text-sm font-medium ${showReport ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
                >
                  {showReport ? 'Tickets' : 'Report'}
                </button>
              </div>
              <button
                onClick={() => { setSelectedClient(null); setShowReport(false); setReportData(null); }}
                className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
              >
                &times;
              </button>
            </div>

            <div className="p-6">
              {/* Report View */}
              {showReport && reportData && (
                <div>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-500">Total Tickets</p>
                      <p className="text-2xl font-bold">{reportData.summary?.total_tickets || 0}</p>
                    </div>
                    <div className="bg-yellow-50 rounded-lg p-4">
                      <p className="text-sm text-gray-500">Open Tickets</p>
                      <p className="text-2xl font-bold text-yellow-600">{reportData.summary?.open_tickets || 0}</p>
                    </div>
                    <div className="bg-green-50 rounded-lg p-4">
                      <p className="text-sm text-gray-500">Closed Tickets</p>
                      <p className="text-2xl font-bold text-green-600">{reportData.summary?.closed_tickets || 0}</p>
                    </div>
                    <div className="bg-blue-50 rounded-lg p-4">
                      <p className="text-sm text-gray-500">Hours Used</p>
                      <p className="text-2xl font-bold text-blue-600">{reportData.summary?.total_hours_used || 0}h</p>
                    </div>
                    <div className="bg-purple-50 rounded-lg p-4">
                      <p className="text-sm text-gray-500">Hours Remaining</p>
                      <p className="text-2xl font-bold text-purple-600">{reportData.summary?.hours_remaining || 0}h</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-500">Period</p>
                      <p className="text-lg font-bold">{reportData.period || ''}</p>
                    </div>
                  </div>

                  <div className="flex space-x-3 mb-6">
                    <button
                      onClick={downloadPDF}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium"
                    >
                      Download Report
                    </button>
                    <button
                      onClick={emailReport}
                      className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium"
                    >
                      Email Report
                    </button>
                  </div>

                  <h3 className="text-lg font-semibold mb-3">Tickets</h3>
                  <div className="space-y-2">
                    {(reportData.tickets || []).map((ticket) => (
                      <div key={ticket.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                        <div>
                          <p className="font-medium text-gray-900">{ticket.title}</p>
                          <p className="text-sm text-gray-500">{ticket.description}</p>
                        </div>
                        <div className="flex items-center space-x-3">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getTicketStatusColor(ticket.status)}`}>
                            {ticket.status}
                          </span>
                          <span className="text-sm text-gray-500">{ticket.hours_used || 0}h</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tickets / Info View */}
              {!showReport && (
                <div className="space-y-6">
                  {/* Client Info Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-500">Email</p>
                      <p className="font-medium">{selectedClient.email}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-500">Phone</p>
                      <p className="font-medium">{selectedClient.phone || 'N/A'}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-500">Portal URL</p>
                      <p className="font-medium text-indigo-600">{selectedClient.portal_url || `https://${selectedClient.subdomain}.mybeacon.co.za`}</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <p className="text-sm text-gray-500">Tier</p>
                      <p>{getTierBadge(selectedClient.tier)}</p>
                    </div>
                  </div>

                  {/* Hours Progress */}
                  {hoursData && (
                    <div className="bg-white border border-gray-200 rounded-lg p-4">
                      <h3 className="text-sm font-semibold text-gray-700 mb-3">Hours Usage</h3>
                      <div className="flex items-center justify-between text-sm mb-2">
                        <span className="text-gray-500">{hoursData.monthly_hours_used || 0}h used</span>
                        <span className="text-gray-500">{hoursData.monthly_hours_total || 0}h total</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-3">
                        <div
                          className="bg-indigo-600 h-3 rounded-full transition-all"
                          style={{ width: `${Math.min(100, ((hoursData.monthly_hours_used || 0) / (hoursData.monthly_hours_total || 1)) * 100)}%` }}
                        ></div>
                      </div>
                      <p className="text-sm text-gray-500 mt-2">{hoursData.hours_remaining || 0}h remaining</p>
                    </div>
                  )}

                  {/* Active Token */}
                  {selectedClient.active_token && (
                    <div className="bg-white border border-gray-200 rounded-lg p-4">
                      <h3 className="text-sm font-semibold text-gray-700 mb-2">Active Token</h3>
                      <div className="flex items-center space-x-2">
                        <code className="bg-gray-100 px-3 py-1 rounded text-sm font-mono">{selectedClient.active_token}</code>
                        <button
                          onClick={() => copyToClipboard(selectedClient.active_token)}
                          className="text-indigo-600 hover:text-indigo-800 text-sm"
                        >
                          Copy
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Cloudflare Tunnel */}
                  <div className="bg-white border border-gray-200 rounded-lg p-4">
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Cloudflare Tunnel</h3>
                    {selectedClient.cloudflare_tunnel_id ? (
                      <div>
                        <div className="flex items-center space-x-2 mb-2">
                          <span className="h-2 w-2 rounded-full bg-green-500"></span>
                          <span className="text-sm text-gray-600">Tunnel Active</span>
                        </div>
                        <p className="text-sm text-gray-500 mb-2">ID: {selectedClient.cloudflare_tunnel_id}</p>
                        <button
                          onClick={() => { if (confirm('Delete this tunnel?')) { /* API call to delete tunnel */ } }}
                          className="text-red-600 hover:text-red-800 text-sm"
                        >
                          Delete Tunnel
                        </button>
                      </div>
                    ) : (
                      <div>
                        <p className="text-sm text-gray-500 mb-2">No tunnel configured</p>
                        <button
                          onClick={() => { /* API call to create tunnel */ }}
                          className="px-3 py-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded text-sm"
                        >
                          Create Tunnel
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Templates Section */}
                  <div className="bg-white border border-gray-200 rounded-lg p-4">
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Templates</h3>
                    {categories.length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-3">
                        <button
                          onClick={() => setTemplateCategory('all')}
                          className={`px-3 py-1 rounded-full text-xs font-medium ${templateCategory === 'all' ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700'}`}
                        >
                          All
                        </button>
                        {categories.map((cat) => (
                          <button
                            key={cat}
                            onClick={() => setTemplateCategory(cat)}
                            className={`px-3 py-1 rounded-full text-xs font-medium ${templateCategory === cat ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-700'}`}
                          >
                            {cat}
                          </button>
                        ))}
                      </div>
                    )}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {filteredTemplates.map((template) => (
                        <button
                          key={template.id}
                          onClick={() => openTemplate(template)}
                          className="text-left p-3 bg-gray-50 hover:bg-gray-100 rounded-lg border border-gray-200"
                        >
                          <p className="font-medium text-sm text-gray-900">{template.title}</p>
                          <p className="text-xs text-gray-500">{template.description}</p>
                          <p className="text-xs text-gray-400 mt-1">{template.hours_used || 0}h</p>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Tickets Section */}
                  <div className="bg-white border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-semibold text-gray-700">Tickets</h3>
                      <button
                        onClick={() => setShowTicketForm(!showTicketForm)}
                        className="px-3 py-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded text-sm"
                      >
                        {showTicketForm ? 'Cancel' : '+ New Ticket'}
                      </button>
                    </div>

                    {/* New Ticket Form */}
                    {showTicketForm && (
                      <form onSubmit={createTicket} className="bg-gray-50 rounded-lg p-4 mb-4 space-y-3">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                          <input
                            type="text"
                            required
                            value={ticketForm.title}
                            onChange={(e) => setTicketForm({ ...ticketForm, title: e.target.value })}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                          <textarea
                            value={ticketForm.description}
                            onChange={(e) => setTicketForm({ ...ticketForm, description: e.target.value })}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                            rows="2"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                          <select
                            value={ticketForm.priority}
                            onChange={(e) => setTicketForm({ ...ticketForm, priority: e.target.value })}
                            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                          >
                            <option value="low">Low</option>
                            <option value="medium">Medium</option>
                            <option value="high">High</option>
                          </select>
                        </div>
                        <button
                          type="submit"
                          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm"
                        >
                          Create Ticket
                        </button>
                      </form>
                    )}

                    {/* Ticket List */}
                    <div className="space-y-2">
                      {tickets.map((ticket) => (
                        <div key={ticket.id} className="border border-gray-200 rounded-lg p-3">
                          {editingTicket && editingTicket.id === ticket.id ? (
                            <div className="space-y-2">
                              <input
                                type="text"
                                value={editingTicket.title}
                                onChange={(e) => setEditingTicket({ ...editingTicket, title: e.target.value })}
                                className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                              />
                              <textarea
                                value={editingTicket.description || ''}
                                onChange={(e) => setEditingTicket({ ...editingTicket, description: e.target.value })}
                                className="w-full border border-gray-300 rounded px-2 py-1 text-sm"
                                rows="2"
                              />
                              <div className="flex items-center space-x-2">
                                <input
                                  type="date"
                                  value={editingTicket.completed_at ? editingTicket.completed_at.substring(0, 10) : ''}
                                  onChange={(e) => setEditingTicket({ ...editingTicket, completed_at: e.target.value })}
                                  className="border border-gray-300 rounded px-2 py-1 text-sm"
                                />
                                <input
                                  type="time"
                                  value={editingTicket.completed_at ? editingTicket.completed_at.substring(11, 16) : ''}
                                  onChange={(e) => {
                                    const date = editingTicket.completed_at ? editingTicket.completed_at.substring(0, 10) : new Date().toISOString().substring(0, 10);
                                    setEditingTicket({ ...editingTicket, completed_at: `${date}T${e.target.value}` });
                                  }}
                                  className="border border-gray-300 rounded px-2 py-1 text-sm"
                                />
                                <input
                                  type="number"
                                  value={editingTicket.hours_used || 0}
                                  onChange={(e) => setEditingTicket({ ...editingTicket, hours_used: parseFloat(e.target.value) || 0 })}
                                  className="w-20 border border-gray-300 rounded px-2 py-1 text-sm"
                                  step="0.5"
                                  min="0"
                                />
                                <span className="text-xs text-gray-500">hours</span>
                              </div>
                              <div className="flex items-center space-x-2">
                                <select
                                  value={editingTicket.status}
                                  onChange={(e) => setEditingTicket({ ...editingTicket, status: e.target.value })}
                                  className="border border-gray-300 rounded px-2 py-1 text-sm"
                                >
                                  <option value="open">Open</option>
                                  <option value="in_progress">In Progress</option>
                                  <option value="closed">Closed</option>
                                </select>
                                <button
                                  onClick={() => updateTicket(ticket.id, editingTicket)}
                                  className="px-3 py-1 bg-green-600 text-white rounded text-sm"
                                >
                                  Save
                                </button>
                                <button
                                  onClick={() => setEditingTicket(null)}
                                  className="px-3 py-1 bg-gray-200 text-gray-700 rounded text-sm"
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="flex items-center justify-between">
                              <div>
                                <p className="font-medium text-sm text-gray-900">{ticket.title}</p>
                                <p className="text-xs text-gray-500">{ticket.description}</p>
                                <div className="flex items-center space-x-3 mt-1">
                                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getTicketStatusColor(ticket.status)}`}>
                                    {ticket.status}
                                  </span>
                                  <span className="text-xs text-gray-400">{ticket.hours_used || 0}h</span>
                                  {ticket.created_at && (
                                    <span className="text-xs text-gray-400">{new Date(ticket.created_at).toLocaleDateString()}</span>
                                  )}
                                  {ticket.completed_at && (
                                    <span className="text-xs text-gray-400">Done: {new Date(ticket.completed_at).toLocaleDateString()}</span>
                                  )}
                                </div>
                              </div>
                              <div className="flex items-center space-x-2">
                                <button
                                  onClick={() => setEditingTicket({ ...ticket })}
                                  className="text-indigo-600 hover:text-indigo-800 text-xs"
                                >
                                  Edit
                                </button>
                                <button
                                  onClick={() => deleteTicket(ticket.id)}
                                  className="text-red-600 hover:text-red-800 text-xs"
                                >
                                  Delete
                                </button>
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                      {tickets.length === 0 && (
                        <p className="text-sm text-gray-400 text-center py-4">No tickets yet</p>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
