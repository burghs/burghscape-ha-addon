import { useState } from 'react';
import { useAuth } from '../hooks/AuthContext';
import { BrandLogo, Button } from '../components/ui';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
    } catch (err) {
      setError(err.message || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-dvh items-center justify-center overflow-x-hidden bg-[radial-gradient(circle_at_top,rgba(37,99,235,0.18),transparent_34%),#030712] p-4 [padding-bottom:max(1rem,env(safe-area-inset-bottom))] [padding-top:max(1rem,env(safe-area-inset-top))]">
      <div className="brand-shell w-full max-w-sm p-5 sm:p-8">
        <div className="mb-8 flex flex-col items-center text-center">
          <BrandLogo className="flex-col gap-4" imageClassName="h-20 max-w-[8rem] sm:h-24 sm:max-w-[9rem]" subtitle="MyBeacon Management Portal" />
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="form-input-dark-lg"
              required
            />
          </div>
          <div>
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="form-input-dark-lg"
              required
            />
          </div>

          {error && (
            <div className="alert-error py-2 text-sm">
              {error}
            </div>
          )}

          <Button type="submit" disabled={loading} className="w-full py-3">
            {loading ? 'Signing in...' : 'Sign In'}
          </Button>
        </form>
      </div>
    </div>
  );
}
