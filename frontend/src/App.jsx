import { Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./hooks/AuthContext";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Clients from "./pages/Clients";
import ClientDetail from "./pages/ClientDetail";
import Instances from "./pages/Instances";
import Backups from "./pages/Backups";
import Support from "./pages/Support";
import Settings from "./pages/Settings";
import Campaigns from "./pages/Campaigns";

function isClientPortal() {
  return window.location.hostname.startsWith("client.");
}

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  if (!user) {
    window.MyBeaconTheme?.clear();
    return <Login />;
  }

  return children;
}

function ClientPortalRedirect() {
  if (isClientPortal()) {
    // Full page reload to hit the backend portal login
    window.location.href = "/portal/login";
    return null;
  }
  return null;
}

function AppRoutes() {
  return (
    <>
      <ClientPortalRedirect />
      <Routes>
        <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="clients" element={<Clients />} />
          <Route path="clients/:id" element={<ClientDetail />} />
          <Route path="instances" element={<Instances />} />
          <Route path="backups" element={<Backups />} />
          <Route path="support" element={<Support />} />
          <Route path="campaigns" element={<Campaigns />} />
          <Route path="settings" element={<Settings />} />
        </Route>
      </Routes>
    </>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}

export default App;
