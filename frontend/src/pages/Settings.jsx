import { useState, useEffect } from 'react';

export default function Settings() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Password change state
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordMsg, setPasswordMsg] = useState(null);
  const [passwordLoading, setPasswordLoading] = useState(false);

  useEffect(() => {
    fetch('/api/health')
      .then(res => res.json())
      .then(data => { setHealth(data); setLoading(false); })
      .catch(err => { setError(err.message); setLoading(false); });
  }, []);

  const handleChangePassword = async (e) => {
    e.preventDefault();
    setPasswordMsg(null);
    
    if (newPassword !== confirmPassword) {
      setPasswordMsg({ type: 'error', text: 'New passwords do not match' });
      return;
    }
    if (newPassword.length < 8) {
      setPasswordMsg({ type: 'error', text: 'Password must be at least 8 characters' });
      return;
    }
    
    setPasswordLoading(true);
    try {
      const res = await fetch('/api/admin/password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      
      if (res.ok) {
        setPasswordMsg({ type: 'success', text: 'Password changed successfully!' });
        setCurrentPassword('');
        setNewPassword('');
        setConfirmPassword('');
      } else {
        const data = await res.json();
        setPasswordMsg({ type: 'error', text: data.detail || 'Failed to change password' });
      }
    } catch (err) {
      setPasswordMsg({ type: 'error', text: 'Network error' });
    } finally {
      setPasswordLoading(false);
    }
  };

  return (
    <div>
      <h1 className="text-2xl font-bold text-white mb-6">Settings</h1>
      
      {/* Change Password */}
      <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">Change Password</h2>
        <form onSubmit={handleChangePassword} className="space-y-3 max-w-sm">
          <input
            type="password"
            placeholder="Current password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
            required
          />
          <input
            type="password"
            placeholder="New password (min 8 chars)"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
            required
          />
          <input
            type="password"
            placeholder="Confirm new password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
            required
          />
          
          {passwordMsg && (
            <div className={`text-sm rounded-lg px-3 py-2 ${passwordMsg.type === 'success' ? 'bg-green-900/50 text-green-300 border border-green-700' : 'bg-red-900/50 text-red-300 border border-red-700'}`}>
              {passwordMsg.text}
            </div>
          )}
          
          <button
            type="submit"
            disabled={passwordLoading}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium px-4 py-2 rounded-lg transition"
          >
            {passwordLoading ? 'Changing...' : 'Change Password'}
          </button>
        </form>
      </div>

      {/* System Status */}
      <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">System Status</h2>
        {loading ? (
          <div className="text-gray-400">Checking...</div>
        ) : health ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${health.status === 'healthy' ? 'bg-green-500' : 'bg-red-500'}`}></div>
              <span className="text-white">Backend: {health.status}</span>
            </div>
          </div>
        ) : (
          <div className="text-red-400">Unable to connect to backend</div>
        )}
        {error && <div className="text-red-400 text-sm mt-2">Error: {error}</div>}
      </div>

      {/* Platform Info */}
      <div className="bg-gray-800 rounded-xl p-5 border border-gray-700">
        <h2 className="text-lg font-semibold text-white mb-2">Platform Settings</h2>
        <p className="text-gray-400 text-sm">Cloudflare and OneDrive credentials are configured via the .env file on the server.</p>
      </div>
    </div>
  );
}
