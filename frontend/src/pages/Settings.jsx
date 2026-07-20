import { useState, useEffect } from 'react';
import { Button, Card, Input, PageHeader, StatusDot } from '../components/ui';

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
      <PageHeader title="Settings" />
      
      <Card compact className="mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">Change Password</h2>
        <form onSubmit={handleChangePassword} className="space-y-3 max-w-sm">
          <Input
            type="password"
            placeholder="Current password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
          />
          <Input
            type="password"
            placeholder="New password (min 8 chars)"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
          />
          <Input
            type="password"
            placeholder="Confirm new password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
          />
          
          {passwordMsg && (
            <div className={passwordMsg.type === 'success' ? 'alert-success py-2 text-sm' : 'alert-error py-2 text-sm'}>
              {passwordMsg.text}
            </div>
          )}
          
          <Button type="submit" disabled={passwordLoading}>
            {passwordLoading ? 'Changing...' : 'Change Password'}
          </Button>
        </form>
      </Card>

      <Card compact className="mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">System Status</h2>
        {loading ? (
          <div className="text-gray-400">Checking...</div>
        ) : health ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <StatusDot active={health.status === 'healthy'} size="md" />
              <span className="text-white">Backend: {health.status}</span>
            </div>
          </div>
        ) : (
          <div className="text-danger-text">Unable to connect to backend</div>
        )}
        {error && <div className="text-danger-text text-sm mt-2">Error: {error}</div>}
      </Card>

      <Card compact>
        <h2 className="text-lg font-semibold text-white mb-2">Platform Settings</h2>
        <p className="text-gray-400 text-sm">Cloudflare and OneDrive credentials are configured via the .env file on the server.</p>
      </Card>
    </div>
  );
}
