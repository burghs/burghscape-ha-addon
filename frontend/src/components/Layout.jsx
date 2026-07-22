import { Link, useLocation, Outlet } from "react-router-dom";
import { Home, Users, Cpu, Database, LifeBuoy, Megaphone, Settings, Menu, X, LogOut } from "lucide-react";
import { useEffect, useState } from "react";
import { useAuth } from "../hooks/AuthContext";
import { BrandLogo } from "./ui";

const navItems = [
  { path: "/dashboard", icon: Home, label: "Dashboard" },
  { path: "/clients", icon: Users, label: "Clients" },
  { path: "/instances", icon: Cpu, label: "HA Instances" },
  { path: "/backups", icon: Database, label: "Backups" },
  { path: "/support", icon: LifeBuoy, label: "Support" },
  { path: "/campaigns", icon: Megaphone, label: "Campaigns" },
  { path: "/settings", icon: Settings, label: "Settings" },
];

export default function Layout() {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { user, logout } = useAuth();

  useEffect(() => {
    document.documentElement.setAttribute("data-theme-enabled", "");
    window.MyBeaconTheme?.start();
    return () => window.MyBeaconTheme?.clear();
  }, []);

  return (
    <div className="portal-shell flex min-h-dvh overflow-hidden bg-gray-950 text-gray-100">
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      <aside className={`portal-sidebar fixed inset-y-0 left-0 z-50 w-64 max-w-[86vw] transform border-r border-white/10 bg-gray-950/95 shadow-2xl shadow-black/40 transition-transform lg:static lg:translate-x-0 ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="relative border-b border-white/10 px-4 py-4">
          <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary-text/60 to-transparent" />
          <div className="flex min-w-0 items-center gap-3">
            <BrandLogo className="min-w-0 flex-1" imageClassName="h-10 w-10" subtitle="MyBeacon Portal" />
            <button className="ml-auto rounded-lg p-2 text-muted-text transition hover:bg-white/10 hover:text-white lg:hidden" onClick={() => setSidebarOpen(false)}>
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <nav className="space-y-1 px-3 py-4">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-3 rounded-xl border px-3 py-2.5 text-sm font-medium transition duration-200 ${isActive ? "border-primary/30 bg-gradient-to-r from-primary/25 to-purple-600/10 text-white shadow-lg shadow-primary/10" : "border-transparent text-muted-text hover:border-white/10 hover:bg-white/[0.06] hover:text-white"}`}
              >
                <Icon className="h-5 w-5" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="absolute bottom-0 left-0 right-0 border-t border-white/10 p-4">
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-xl border border-transparent px-3 py-2.5 text-sm font-medium text-muted-text transition duration-200 hover:border-white/10 hover:bg-white/[0.06] hover:text-white"
          >
            <LogOut className="h-5 w-5" />
            Sign Out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <header className="portal-header flex min-w-0 flex-wrap items-center gap-3 border-b border-white/10 bg-gray-950/85 px-3 py-3 backdrop-blur sm:gap-4 sm:px-5">
          <button className="rounded-lg p-2 text-muted-text transition hover:bg-white/10 hover:text-white lg:hidden" onClick={() => setSidebarOpen(true)}>
            <Menu className="h-5 w-5" />
          </button>
          <div className="hidden sm:block">
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-text">Burghscape Home Cloud</p>
          </div>
          <div className="flex-1" />
          <div className="portal-account min-w-0 max-w-full flex items-center gap-3 rounded-full border border-white/10 bg-white/[0.04] py-1 pl-3 pr-1">
            <span className="truncate text-sm text-gray-300">{user?.username || 'Admin'}</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-subtle ring-1 ring-primary/30">
              <span className="text-xs font-semibold text-primary-text">{(user?.username || 'A')[0].toUpperCase()}</span>
            </div>
          </div>
        </header>
        <main className="portal-main min-w-0 flex-1 overflow-y-auto overflow-x-hidden bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.12),transparent_34%),#030712] p-3 sm:p-6 lg:p-7">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
