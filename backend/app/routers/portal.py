"""Client Portal — public-facing portal served at client.mybeacon.co.za"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from models import Client, SupportTicket, ClientUser, HomeAssistantInstance

router = APIRouter()

# In-memory session store (use JWT or Redis in production)
from routers.portal_state import portal_sessions


PORTAL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{client_name} - Burghscape Portal</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; background: #0a0a1a; margin: 0; }}
        .bg-grid {{
            background-image: linear-gradient(rgba(139,92,246,0.03) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(139,92,246,0.03) 1px, transparent 1px);
            background-size: 60px 60px;
        }}
        .card {{ background: rgba(18,18,42,0.8); border: 1px solid rgba(139,92,246,0.1); backdrop-filter: blur(10px); }}
        .status-dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
        .status-online {{ background: #34d399; box-shadow: 0 0 8px rgba(52,211,153,0.5); }}
        .status-offline {{ background: #f87171; }}
        .progress-bar {{ background: rgba(139,92,246,0.15); border-radius: 999px; overflow: hidden; }}
        .progress-fill {{ background: linear-gradient(90deg, #8b5cf6, #6d28d9); height: 100%; border-radius: 999px; transition: width 1s; }}
        .nav-link {{ transition: all 0.2s; }}
        .nav-link:hover {{ color: #8b5cf6; }}
        .nav-active {{ color: #8b5cf6; border-color: #8b5cf6; }}
        /* Light theme */
        body.light {{ background: #f8fafc; color: #1e293b; }}
        body.light .bg-grid {{ background-image: none; }}
        body.light .card {{ background: #ffffff; border-color: #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
        body.light .text-white {{ color: #1e293b !important; }}
        body.light .text-gray-200 {{ color: #334155 !important; }}
        body.light .text-gray-400 {{ color: #64748b !important; }}
        body.light .text-gray-500 {{ color: #64748b !important; }}
        body.light .bg-gray-900 {{ background: #f1f5f9 !important; }}
        body.light .bg-gray-900\\/50 {{ background: #f1f5f9 !important; }}
        body.light .border-gray-700 {{ border-color: #e2e8f0 !important; }}
        body.light .border-gray-800 {{ border-color: #e2e8f0 !important; }}
    </style>
</head>
<body class="bg-gray-950 text-gray-200 min-h-screen bg-grid" id="app-body">
    <!-- Top Nav -->
    <nav class="card border-b border-purple-500/10 px-4 md:px-6 py-4">
        <div class="max-w-6xl mx-auto flex items-center justify-between">
            <div class="flex items-center gap-2 md:gap-4">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" style="height:40px;width:auto"><defs><linearGradient id="navbg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#1a1a3e"/><stop offset="100%" style="stop-color:#0d0d24"/></linearGradient><linearGradient id="navacc" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" style="stop-color:#a78bfa"/><stop offset="100%" style="stop-color:#7c3aed"/></linearGradient></defs><circle cx="100" cy="100" r="95" fill="url(#navbg)" stroke="url(#navacc)" stroke-width="3"/><path d="M100 30 L150 50 L150 100 Q150 140 100 170 Q50 140 50 100 L50 50 Z" fill="none" stroke="#a78bfa" stroke-width="3"/><path d="M100 60 L130 80 L130 120 L70 120 L70 80 Z" fill="none" stroke="#c4b5fd" stroke-width="2.5"/><rect x="92" y="100" width="16" height="20" fill="#a78bfa" rx="2"/><circle cx="100" cy="45" r="5" fill="#a78bfa"/></svg>
                <span class="hidden md:inline text-sm font-semibold text-purple-400">Burghscape</span>
                <span class="text-sm md:text-lg font-semibold text-white">{client_name}</span>
                <span class="text-xs px-2 py-1 rounded-full {status_class}">{status_text}</span>
            </div>
            <div class="flex items-center gap-2 md:gap-4 text-sm">
                <button onclick="toggleTheme()" class="p-2 rounded-lg hover:bg-gray-800/50 transition" title="Toggle theme">
                    <svg id="theme-icon-sun" class="w-4 h-4 text-gray-400 hidden" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
                    <svg id="theme-icon-moon" class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>
                </button>
                <span class="text-gray-400 hidden sm:inline">{user_name}</span>
                <button onclick="document.getElementById('pw-form-nav').classList.toggle('hidden')" class="text-gray-400 hover:text-purple-400 transition nav-link text-xs md:text-sm">Account</button>
                <a href="/portal/logout" class="text-gray-400 hover:text-purple-400 transition nav-link text-xs md:text-sm">Logout</a>
            </div>
        </div>
        <!-- Password change dropdown -->
        <div id="pw-form-nav" class="hidden mt-3 p-4 bg-gray-900/50 rounded-xl border border-purple-500/10 max-w-sm ml-auto">
            <p class="text-xs text-gray-400 mb-2">Change Password</p>
            <input type="password" id="pw-current-nav" placeholder="Current Password" class="w-full bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-2 mb-2 text-sm text-white focus:border-purple-500 focus:outline-none">
            <input type="password" id="pw-new-nav" placeholder="New Password" class="w-full bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-2 mb-2 text-sm text-white focus:border-purple-500 focus:outline-none">
            <input type="password" id="pw-confirm-nav" placeholder="Confirm Password" class="w-full bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-2 mb-3 text-sm text-white focus:border-purple-500 focus:outline-none">
            <button onclick="changePasswordNav()" class="bg-gradient-to-r from-purple-600 to-violet-700 hover:from-purple-500 hover:to-violet-600 px-4 py-2 rounded-lg text-sm text-white w-full">Update Password</button>
            <p id="pw-msg-nav" class="text-sm mt-2 hidden"></p>
        </div>
    </nav>

    <div class="max-w-6xl mx-auto p-6 mt-4">
        <!-- System Status -->
        <div class="card rounded-2xl p-6 mb-6">
            <div class="flex items-center justify-between mb-5">
                <h2 class="text-lg font-semibold text-white">System Status</h2>
                <div class="flex items-center gap-2">
                    <span class="status-dot {online_dot_class}"></span>
                    <span class="text-sm {online_text_class}">{online_status}</span>
                </div>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
                <div>
                    <p class="text-3xl font-bold text-white">{ha_version}</p>
                    <p class="text-xs text-gray-500 mt-1">HA Version</p>
                </div>
                <div>
                    <p class="text-3xl font-bold text-white">{entity_count}</p>
                    <p class="text-xs text-gray-500 mt-1">Entities</p>
                </div>
                <div>
                    <p class="text-3xl font-bold text-white">{addon_count_display}</p>
                    <p class="text-xs text-gray-500 mt-1">Add-ons{addon_count_suffix}</p>
                </div>
                <div>
                    <p class="text-3xl font-bold text-white">{integration_count}</p>
                    <p class="text-xs text-gray-500 mt-1">Integrations</p>
                </div>
            </div>
        </div>

        <!-- Quick Access + HA Info Row -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <!-- Quick Access -->
            <div class="card rounded-2xl p-6">
                <h2 class="text-lg font-semibold text-white mb-4">Quick Access</h2>
                <a href="https://{subdomain}.mybeacon.co.za" target="_blank"
                   class="inline-flex items-center gap-3 bg-gradient-to-r from-purple-600 to-violet-700 hover:from-purple-500 hover:to-violet-600 text-white px-5 py-3 rounded-xl transition shadow-lg shadow-purple-500/20">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                    Open Home Assistant
                </a>
                <p class="text-xs text-gray-500 mt-3">URL: https://{subdomain}.mybeacon.co.za</p>
            </div>

            <!-- HA Environment Info -->
            <div class="card rounded-2xl p-6">
                <h2 class="text-lg font-semibold text-white mb-4">Environment</h2>
                <div class="space-y-3">
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-500">Database Size</span>
                        <span class="text-white font-medium">{db_size}</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-500">Uptime</span>
                        <span class="text-white font-medium">{uptime}</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-500">Updates Available</span>
                        <span class="font-medium {updates_class}">{updates_count}</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-500">Last Seen</span>
                        <span class="text-white font-medium">{last_seen}</span>
                    </div>
                </div>
            </div>

            <!-- System Stats -->
            <div class="card rounded-2xl p-6">
                <h2 class="text-lg font-semibold text-white mb-4">System Resources</h2>
                <div class="space-y-4">
                    <div>
                        <div class="flex justify-between text-sm mb-1">
                            <span class="text-gray-500">CPU Usage</span>
                            <span class="text-white font-medium">{cpu_percent}%</span>
                        </div>
                        <div class="progress-bar h-2">
                            <div class="progress-fill" style="width:{cpu_percent}%"></div>
                        </div>
                    </div>
                    <div>
                        <div class="flex justify-between text-sm mb-1">
                            <span class="text-gray-500">Memory</span>
                            <span class="text-white font-medium">{memory_used_gb} / {memory_total_gb} GB ({memory_percent}%)</span>
                        </div>
                        <div class="progress-bar h-2">
                            <div class="progress-fill" style="width:{memory_percent}%"></div>
                        </div>
                    </div>
                    <div>
                        <div class="flex justify-between text-sm mb-1">
                            <span class="text-gray-500">Disk Space</span>
                            <span class="text-white font-medium">{disk_used_gb} / {disk_total_gb} GB ({disk_percent}%)</span>
                        </div>
                        <div class="progress-bar h-2">
                            <div class="progress-fill" style="width:{disk_percent}%"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>


        <!-- Backup Status -->
        <div class="card rounded-2xl p-6 mb-6">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-lg font-semibold text-white">Backup Status</h2>
                <span class="text-xs px-3 py-1 rounded-full {backup_badge_class}">{backup_badge_text}</span>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                    <p class="text-sm text-gray-500">Last Backup</p>
                    <p class="text-white font-medium mt-1">{last_backup_str}</p>
                </div>
                <div>
                    <p class="text-sm text-gray-500">Next Backup</p>
                    <p class="text-white font-medium mt-1">{next_backup_str}</p>
                </div>
                <div>
                    <p class="text-sm text-gray-500">OneDrive Sync</p>
                    <p class="font-medium mt-1 {backup_sync_class}">{backup_sync_text}</p>
                </div>
            </div>
        </div>

        <!-- Monthly Hours + Support Tickets Row -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            <!-- Monthly Hours -->
            <div class="card rounded-2xl p-6">
                <h2 class="text-lg font-semibold text-white mb-4">Monthly Hours</h2>
                <div class="flex items-center gap-4 mb-2">
                    <div class="flex-1">
                        <div class="progress-bar h-3">
                            <div class="progress-fill" style="width:{hours_percent}%" title="{hours_used}h / {hours_included}h"></div>
                        </div>
                    </div>
                    <span class="text-sm text-gray-400 font-medium whitespace-nowrap">{hours_used}h / {hours_included}h</span>
                </div>
                <p class="text-xs text-gray-500">{hours_remaining}h remaining this month</p>
            </div>

            <!-- Quick Support Ticket Summary -->
            <div class="card rounded-2xl p-6">
                <div class="flex items-center justify-between mb-4">
                    <h2 class="text-lg font-semibold text-white">Support Tickets</h2>
                    <button onclick="document.getElementById('ticket-form').classList.toggle('hidden')"
                            class="text-sm bg-[#8b5cf6]/20 hover:bg-[#8b5cf6]/30 text-purple-300 px-3 py-1.5 rounded-lg transition">+ New</button>
                </div>
                <div id="ticket-form" class="hidden mb-4 p-3 bg-gray-900/50 rounded-xl border border-purple-500/10">
                    <input type="text" id="ticket-title" placeholder="Title" class="w-full bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-2 mb-2 text-sm text-white focus:border-purple-500 focus:outline-none">
                    <textarea id="ticket-desc" placeholder="Description" rows="2" class="w-full bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-2 mb-2 text-sm text-white focus:border-purple-500 focus:outline-none"></textarea>
                    <div class="flex gap-2">
                        <select id="ticket-priority" class="flex-1 bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:border-purple-500 focus:outline-none">
                            <option value="low">Low</option>
                            <option value="normal" selected>Normal</option>
                            <option value="high">High</option>
                        </select>
                        <button onclick="submitTicket()" class="bg-purple-600 hover:bg-purple-500 px-4 py-2 rounded-lg text-sm text-white">Submit</button>
                    </div>
                </div>
                <div id="tickets-list" class="space-y-2 max-h-48 overflow-y-auto">{tickets_html}</div>
            </div>
        </div>

        <!-- Download Report -->
        <div class="card rounded-2xl p-6 mb-6">
            <div class="flex items-center justify-between">
                <div>
                    <h2 class="text-lg font-semibold text-white">System Report</h2>
                    <p class="text-sm text-gray-500 mt-1">Download a full PDF report of your Home Assistant system</p>
                </div>
                <a href="/api/portal/report" target="_blank"
                   class="inline-flex items-center gap-2 bg-gradient-to-r from-purple-600 to-violet-700 hover:from-purple-500 hover:to-violet-600 text-white px-5 py-2.5 rounded-xl transition shadow-lg shadow-purple-500/20 text-sm font-medium">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
                    Download PDF
                </a>
            </div>
        </div>

        <!-- HA Release Notes -->
        {ha_news_section}
    </div>

    <script>
        // Theme toggle
        function toggleTheme() {{
            const body = document.getElementById('app-body');
            const isLight = body.classList.toggle('light');
            document.getElementById('theme-icon-sun').classList.toggle('hidden', !isLight);
            document.getElementById('theme-icon-moon').classList.toggle('hidden', isLight);
            localStorage.setItem('portal-theme', isLight ? 'light' : 'dark');
        }}
        // Restore theme on load
        if (localStorage.getItem('portal-theme') === 'light') {{
            document.getElementById('app-body').classList.add('light');
            document.getElementById('theme-icon-sun')?.classList.remove('hidden');
            document.getElementById('theme-icon-moon')?.classList.add('hidden');
        }}

        async function submitTicket() {{
            const title = document.getElementById('ticket-title').value;
            const desc = document.getElementById('ticket-desc').value;
            const priority = document.getElementById('ticket-priority').value;
            if (!title) return alert('Title required');
            const res = await fetch('/api/portal/tickets', {{
                method: 'POST', headers: {{'Content-Type': 'application/json'}},
                credentials: 'include',
                body: JSON.stringify({{title, description: desc, priority}})
            }});
            if (res.ok) location.reload();
            else alert('Error: ' + res.status);
        }}
        async function changePassword() {{
            const current = document.getElementById('pw-current').value;
            const newPw = document.getElementById('pw-new').value;
            const confirm = document.getElementById('pw-confirm').value;
            const msgEl = document.getElementById('pw-msg');
            msgEl.classList.remove('hidden');
            if (newPw !== confirm) {{ msgEl.textContent = 'Passwords do not match'; msgEl.className = 'text-sm mt-2 text-red-400'; return; }}
            if (newPw.length < 6) {{ msgEl.textContent = 'Password must be at least 6 characters'; msgEl.className = 'text-sm mt-2 text-red-400'; return; }}
            const res = await fetch('/api/portal/auth/change-password', {{
                method: 'POST', headers: {{'Content-Type': 'application/json'}},
                credentials: 'include',
                body: JSON.stringify({{current_password: current, new_password: newPw}})
            }});
            if (res.ok) {{ msgEl.textContent = 'Password changed!'; msgEl.className = 'text-sm mt-2 text-emerald-400'; }}
            else {{ const data = await res.json(); msgEl.textContent = data.detail || 'Failed'; msgEl.className = 'text-sm mt-2 text-red-400'; }}
        }}
        async function changePasswordNav() {{
            const current = document.getElementById('pw-current-nav').value;
            const newPw = document.getElementById('pw-new-nav').value;
            const confirm = document.getElementById('pw-confirm-nav').value;
            const msgEl = document.getElementById('pw-msg-nav');
            msgEl.classList.remove('hidden');
            msgEl.classList.remove('text-red-400', 'text-emerald-400');
            if (newPw !== confirm) {{ msgEl.textContent = 'Passwords do not match'; msgEl.className = 'text-sm mt-2 text-red-400'; return; }}
            if (newPw.length < 6) {{ msgEl.textContent = 'Password must be at least 6 characters'; msgEl.className = 'text-sm mt-2 text-red-400'; return; }}
            const res = await fetch('/api/portal/auth/change-password', {{
                method: 'POST', headers: {{'Content-Type': 'application/json'}},
                credentials: 'include',
                body: JSON.stringify({{current_password: current, new_password: newPw}})
            }});
            if (res.ok) {{ msgEl.textContent = 'Password changed successfully!'; msgEl.className = 'text-sm mt-2 text-emerald-400'; }}
            else {{ const data = await res.json(); msgEl.textContent = data.detail || 'Failed'; msgEl.className = 'text-sm mt-2 text-red-400'; }}
        }}
    </script>
</body>
</html>
"""


LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Client Portal - Burghscape</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; background: #0a0a1a; overflow: hidden; margin: 0; }}
        .bg-grid {{
            background-image: linear-gradient(rgba(139,92,246,0.04) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(139,92,246,0.04) 1px, transparent 1px);
            background-size: 60px 60px;
        }}
        .glow-orb {{ position: absolute; border-radius: 50%; filter: blur(100px); opacity: 0.35; animation: float 8s ease-in-out infinite; }}
        @keyframes float {{ 0%,100% {{ transform: translateY(0) scale(1); }} 50% {{ transform: translateY(-30px) scale(1.05); }} }}
        @keyframes pulse-glow {{
            0%, 100% {{ box-shadow: 0 0 20px rgba(139,92,246,0.3), 0 0 40px rgba(139,92,246,0.1); border-color: rgba(139,92,246,0.25); }}
            50% {{ box-shadow: 0 0 35px rgba(139,92,246,0.5), 0 0 70px rgba(139,92,246,0.2); border-color: rgba(139,92,246,0.45); }}
        }}
        .logo-badge {{
            animation: logo-pulse 3s ease-in-out infinite;
        }}
        @keyframes pulse-glow {{ 0%,100% {{ box-shadow: 0 0 20px rgba(139,92,246,0.2); }} 50% {{ box-shadow: 0 0 50px rgba(139,92,246,0.35), 0 0 100px rgba(139,92,246,0.1); }} }}
        @keyframes logo-pulse {{
            0%, 100% {{ box-shadow: 0 0 20px rgba(139,92,246,0.5), 0 0 40px rgba(139,92,246,0.2); border-color: rgba(139,92,246,0.4); }}
            50% {{ box-shadow: 0 0 40px rgba(139,92,246,0.8), 0 0 100px rgba(139,92,246,0.35); border-color: rgba(190,160,255,0.7); }}
        }}
        .card-glow {{ animation: pulse-glow 4s ease-in-out infinite; }}
        .input-field {{ background: rgba(255,255,255,0.04); border: 1px solid rgba(139,92,246,0.2); transition: all 0.3s; color: #e2e8f0; }}
        .input-field:focus {{ border-color: #8b5cf6; box-shadow: 0 0 0 3px rgba(139,92,246,0.25); outline: none; }}
        .btn-primary {{ background: linear-gradient(135deg, #8b5cf6, #6d28d9); transition: all 0.3s; box-shadow: 0 4px 20px rgba(139,92,246,0.3); }}
        .btn-primary:hover {{ transform: translateY(-1px); box-shadow: 0 8px 35px rgba(139,92,246,0.5); }}
        .logo-float {{ animation: float 6s ease-in-out infinite; }}
    </style>
</head>
<body class="min-h-screen flex items-center justify-center p-4 bg-grid relative" style="background:#0a0a1a">
    <div class="glow-orb w-96 h-96 bg-purple-600" style="top:-10%;left:-5%"></div>
    <div class="glow-orb w-80 h-80 bg-violet-700" style="bottom:-10%;right:-5%;animation-delay:-4s"></div>
    <div class="glow-orb w-64 h-64 bg-indigo-600" style="top:50%;left:60%;opacity:0.15;animation-delay:-2s"></div>

    <div class="relative z-10 w-full max-w-md">
        <div class="text-center mb-8 logo-float">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" style="height:168px;width:auto;display:block;margin:0 auto 12px">
                <defs>
                    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:#1a1a3e"/>
                        <stop offset="100%" style="stop-color:#0d0d24"/>
                    </linearGradient>
                    <linearGradient id="accent" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:#a78bfa"/>
                        <stop offset="100%" style="stop-color:#7c3aed"/>
                    </linearGradient>
                    <filter id="glow">
                        <feGaussianBlur stdDeviation="2" result="blur"/>
                        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
                    </filter>
                </defs>
                <circle cx="100" cy="100" r="95" fill="url(#bg)" stroke="url(#accent)" stroke-width="2" opacity="0.9"/>
                <path d="M100 30 L150 50 L150 100 Q150 140 100 170 Q50 140 50 100 L50 50 Z" fill="none" stroke="#a78bfa" stroke-width="2.5" filter="url(#glow)"/>
                <path d="M100 60 L130 80 L130 120 L70 120 L70 80 Z" fill="none" stroke="#c4b5fd" stroke-width="2"/>
                <line x1="100" y1="60" x2="100" y1="80" stroke="#c4b5fd" stroke-width="2"/>
                <rect x="92" y="100" width="16" height="20" fill="#a78bfa" rx="2"/>
                <circle cx="100" cy="45" r="4" fill="#a78bfa"/>
                <circle cx="75" cy="100" r="3" fill="#7c3aed"/>
                <circle cx="125" cy="100" r="3" fill="#7c3aed"/>
                <path d="M60 70 Q55 80 60 90" fill="none" stroke="#7c3aed" stroke-width="1.5" opacity="0.6"/>
                <path d="M140 70 Q145 80 140 90" fill="none" stroke="#7c3aed" stroke-width="1.5" opacity="0.6"/>
            </svg>
            <h1 class="text-2xl font-bold text-white mt-3" style="letter-spacing:-0.5px">Burghscape</h1>
            <p class="text-xs text-purple-400 mt-1" style="letter-spacing:2px;text-transform:uppercase">Pty Ltd</p>
        </div>

        <div class="bg-[#12122a]/85 backdrop-blur-xl rounded-2xl p-8 border border-purple-500/10 card-glow">
            <div id="login-section">
                <h1 class="text-xl font-bold text-white mb-1 text-center">Client Portal</h1>
                <p class="text-sm text-gray-500 mb-6 text-center">Sign in to your dashboard</p>
                <form onsubmit="event.preventDefault(); doLogin();">
                    <input type="email" id="login-email" placeholder="Email address" class="input-field w-full rounded-xl px-4 py-3 mb-3 text-sm text-gray-200 placeholder-gray-500">
                    <input type="password" id="login-password" placeholder="Password" class="input-field w-full rounded-xl px-4 py-3 mb-4 text-sm text-gray-200 placeholder-gray-500">
                    <button type="submit" class="btn-primary w-full py-3 rounded-xl font-semibold text-white text-sm tracking-wide">SIGN IN</button>
                </form>
                <p id="login-error" class="text-red-400 text-sm mt-3 text-center hidden"></p>
                <div class="mt-5 text-center">
                    <a href="#" onclick="showSection('forgot'); return false;" class="text-sm text-gray-500 hover:text-purple-400 transition-colors">Forgot password?</a>
                </div>
            </div>

            <div id="forgot-section" class="hidden">
                <h1 class="text-xl font-bold text-white mb-2 text-center">Reset Password</h1>
                <p class="text-sm text-gray-500 mb-6 text-center">Enter your email to receive a reset code</p>
                <form onsubmit="event.preventDefault(); doForgot();">
                    <input type="email" id="forgot-email" placeholder="Email address" class="input-field w-full rounded-xl px-4 py-3 mb-3 text-sm text-gray-200 placeholder-gray-500">
                    <button type="submit" class="btn-primary w-full py-3 rounded-xl font-semibold text-white text-sm">SEND CODE</button>
                </form>
                <p id="forgot-result" class="text-sm mt-3 text-center hidden"></p>
                <div class="mt-5 text-center">
                    <a href="#" onclick="showSection('login'); return false;" class="text-sm text-gray-500 hover:text-purple-400">Back to Login</a>
                </div>
            </div>

            <div id="reset-section" class="hidden">
                <h1 class="text-xl font-bold text-white mb-2 text-center">Enter Code</h1>
                <p class="text-sm text-gray-500 mb-6 text-center">Check your email for the 6-character code</p>
                <form onsubmit="event.preventDefault(); doReset();">
                    <input type="text" id="reset-code" placeholder="CODE" maxlength="6" class="input-field w-full rounded-xl px-4 py-3 mb-3 text-lg text-gray-200 font-mono text-center tracking-[0.3em] uppercase placeholder-gray-600">
                    <input type="password" id="reset-newpw" placeholder="New password" class="input-field w-full rounded-xl px-4 py-3 mb-3 text-sm text-gray-200 placeholder-gray-500">
                    <input type="password" id="reset-confirmpw" placeholder="Confirm new password" class="input-field w-full rounded-xl px-4 py-3 mb-4 text-sm text-gray-200 placeholder-gray-500">
                    <button type="submit" class="w-full py-3 rounded-xl font-semibold text-white text-sm bg-gradient-to-r from-emerald-500 to-teal-600 hover:shadow-lg transition">SET NEW PASSWORD</button>
                </form>
                <p id="reset-error" class="text-red-400 text-sm mt-3 text-center hidden"></p>
                <div class="mt-5 text-center">
                    <a href="#" onclick="showSection('login'); return false;" class="text-sm text-gray-500 hover:text-purple-400">Back to Login</a>
                </div>
            </div>
        </div>
        <p class="text-center text-gray-600 text-xs mt-6">Powered by Burghscape Pty Ltd</p>
    </div>
    <script>
        function showSection(id) {
            ['login','forgot','reset'].forEach(s => {
                document.getElementById(s + '-section').classList.add('hidden');
            });
            document.getElementById(id + '-section').classList.remove('hidden');
        }
        async function doLogin() {
            const email = document.getElementById('login-email').value;
            const password = document.getElementById('login-password').value;
            const res = await fetch('/api/portal/auth/login', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email, password})
            });
            if (res.ok) {
                const data = await res.json();
                document.cookie = 'portal_token=' + data.token + '; path=/';
                if (data.user && data.user.force_password_change) { window.location = '/portal/change-password'; }
                else { window.location = '/portal'; }
            } else {
                const el = document.getElementById('login-error');
                el.textContent = 'Invalid credentials';
                el.classList.remove('hidden');
            }
        }
        async function doForgot() {
            const email = document.getElementById('forgot-email').value;
            const res = await fetch('/api/portal/auth/forgot-password', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email})
            });
            if (res.ok) {
                const data = await res.json();
                const el = document.getElementById('forgot-result');
                el.textContent = data.message;
                el.className = 'text-sm mt-3 text-center text-emerald-400';
                el.classList.remove('hidden');
                if (data.debug_token) { el.textContent += ' (Dev: ' + data.debug_token + ')'; }
                setTimeout(() => showSection('reset'), 2000);
            }
        }
        async function doReset() {
            const email = document.getElementById('forgot-email').value;
            const code = document.getElementById('reset-code').value;
            const newPw = document.getElementById('reset-newpw').value;
            const confirmPw = document.getElementById('reset-confirmpw').value;
            if (newPw !== confirmPw) {
                const el = document.getElementById('reset-error');
                el.textContent = 'Passwords do not match';
                el.classList.remove('hidden');
                return;
            }
            const res = await fetch('/api/portal/auth/reset-password', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email, token: code, new_password: newPw})
            });
            if (res.ok) { alert('Password reset successful! You can now log in.'); showSection('login'); }
            else { const data = await res.json(); const el = document.getElementById('reset-error'); el.textContent = data.detail || 'Reset failed'; el.classList.remove('hidden'); }
        }
    </script>
</body>
</html>
"""
CHANGE_PASSWORD_HTML="""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Change Password - Burghscape Portal</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', sans-serif; background: #0a0a1a; overflow: hidden; margin: 0; }}
        .bg-grid {{
            background-image: linear-gradient(rgba(139,92,246,0.04) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(139,92,246,0.04) 1px, transparent 1px);
            background-size: 60px 60px;
        }}
        .glow-orb {{ position: absolute; border-radius: 50%; filter: blur(100px); opacity: 0.35; animation: float 8s ease-in-out infinite; }}
        @keyframes float {{ 0%,100% {{ transform: translateY(0) scale(1); }} 50% {{ transform: translateY(-30px) scale(1.05); }} }}
        @keyframes pulse-glow {{ 0%,100% {{ box-shadow: 0 0 20px rgba(139,92,246,0.2); }} 50% {{ box-shadow: 0 0 50px rgba(139,92,246,0.35), 0 0 100px rgba(139,92,246,0.1); }} }}
        @keyframes logo-pulse {{
            0%, 100% {{ box-shadow: 0 0 20px rgba(139,92,246,0.5), 0 0 40px rgba(139,92,246,0.2); border-color: rgba(139,92,246,0.4); }}
            50% {{ box-shadow: 0 0 40px rgba(139,92,246,0.8), 0 0 100px rgba(139,92,246,0.35); border-color: rgba(190,160,255,0.7); }}
        }}
        .card-glow {{ animation: pulse-glow 4s ease-in-out infinite; }}
        .input-field {{ background: rgba(255,255,255,0.04); border: 1px solid rgba(139,92,246,0.2); transition: all 0.3s; color: #e2e8f0; }}
        .input-field:focus {{ border-color: #8b5cf6; box-shadow: 0 0 0 3px rgba(139,92,246,0.25); outline: none; }}
        .btn-primary {{ background: linear-gradient(135deg, #8b5cf6, #6d28d9); transition: all 0.3s; box-shadow: 0 4px 20px rgba(139,92,246,0.3); }}
        .btn-primary:hover {{ transform: translateY(-1px); box-shadow: 0 8px 35px rgba(139,92,246,0.5); }}
        .logo-float {{ animation: float 6s ease-in-out infinite; }}
    </style>
</head>
<body class="min-h-screen flex items-center justify-center p-4 bg-grid relative" style="background:#0a0a1a">
    <div class="glow-orb w-96 h-96 bg-purple-600" style="top:-10%;left:-5%"></div>
    <div class="glow-orb w-80 h-80 bg-violet-700" style="bottom:-10%;right:-5%;animation-delay:-4s"></div>

    <div class="relative z-10 w-full max-w-md">
        <div class="text-center mb-8 logo-float">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" style="height:168px;width:auto;display:block;margin:0 auto 12px">
                <defs>
                    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:#1a1a3e"/>
                        <stop offset="100%" style="stop-color:#0d0d24"/>
                    </linearGradient>
                    <linearGradient id="accent" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:#a78bfa"/>
                        <stop offset="100%" style="stop-color:#7c3aed"/>
                    </linearGradient>
                    <filter id="glow">
                        <feGaussianBlur stdDeviation="2" result="blur"/>
                        <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
                    </filter>
                </defs>
                <circle cx="100" cy="100" r="95" fill="url(#bg)" stroke="url(#accent)" stroke-width="2" opacity="0.9"/>
                <path d="M100 30 L150 50 L150 100 Q150 140 100 170 Q50 140 50 100 L50 50 Z" fill="none" stroke="#a78bfa" stroke-width="2.5" filter="url(#glow)"/>
                <path d="M100 60 L130 80 L130 120 L70 120 L70 80 Z" fill="none" stroke="#c4b5fd" stroke-width="2"/>
                <line x1="100" y1="60" x2="100" y1="80" stroke="#c4b5fd" stroke-width="2"/>
                <rect x="92" y="100" width="16" height="20" fill="#a78bfa" rx="2"/>
                <circle cx="100" cy="45" r="4" fill="#a78bfa"/>
                <circle cx="75" cy="100" r="3" fill="#7c3aed"/>
                <circle cx="125" cy="100" r="3" fill="#7c3aed"/>
                <path d="M60 70 Q55 80 60 90" fill="none" stroke="#7c3aed" stroke-width="1.5" opacity="0.6"/>
                <path d="M140 70 Q145 80 140 90" fill="none" stroke="#7c3aed" stroke-width="1.5" opacity="0.6"/>
            </svg>
            <h1 class="text-2xl font-bold text-white mt-3" style="letter-spacing:-0.5px">Burghscape</h1>
            <p class="text-xs text-purple-400 mt-1" style="letter-spacing:2px;text-transform:uppercase">Pty Ltd</p>
        </div>

        <div class="bg-[#12122a]/85 backdrop-blur-xl rounded-2xl p-8 border border-purple-500/10 card-glow">
            <h1 class="text-xl font-bold text-white mb-2 text-center">Change Your Password</h1>
            <p class="text-sm text-gray-500 mb-6 text-center">For security, please set a new password before continuing.</p>
            <form onsubmit="event.preventDefault(); doChangePassword();">
                <input type="password" id="cp-current" placeholder="Current (temporary) password" class="input-field w-full rounded-xl px-4 py-3 mb-3 text-sm text-gray-200 placeholder-gray-500">
                <input type="password" id="cp-new" placeholder="New password (min 6 chars)" class="input-field w-full rounded-xl px-4 py-3 mb-3 text-sm text-gray-200 placeholder-gray-500">
                <input type="password" id="cp-confirm" placeholder="Confirm new password" class="input-field w-full rounded-xl px-4 py-3 mb-4 text-sm text-gray-200 placeholder-gray-500">
                <button type="submit" class="btn-primary w-full py-3 rounded-xl font-semibold text-white text-sm tracking-wide">SET NEW PASSWORD</button>
            </form>
            <p id="cp-msg" class="text-sm mt-3 text-center hidden"></p>
        </div>
        <p class="text-center text-gray-600 text-xs mt-6">Powered by Burghscape Pty Ltd</p>
    </div>
    <script>
        async function doChangePassword() {
            const current = document.getElementById('cp-current').value;
            const newPw = document.getElementById('cp-new').value;
            const confirm = document.getElementById('cp-confirm').value;
            const msgEl = document.getElementById('cp-msg');
            msgEl.classList.remove('hidden');
            msgEl.classList.remove('text-red-400', 'text-emerald-400');
            if (newPw !== confirm) { msgEl.textContent = 'Passwords do not match'; msgEl.classList.add('text-red-400'); return; }
            if (newPw.length < 6) { msgEl.textContent = 'Password must be at least 6 characters'; msgEl.classList.add('text-red-400'); return; }
            const res = await fetch('/api/portal/auth/change-password', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                credentials: 'include',
                body: JSON.stringify({current_password: current, new_password: newPw})
            });
            if (res.ok) {
                msgEl.textContent = 'Password changed successfully! Redirecting...';
                msgEl.classList.add('text-emerald-400');
                setTimeout(() => { window.location = '/portal'; }, 1500);
            } else {
                const data = await res.json();
                msgEl.textContent = data.detail || 'Failed to change password';
                msgEl.classList.add('text-red-400');
            }
        }
    </script>
</body>
</html>
"""


@router.get("/api/portal/report")
async def download_report(request: Request):
    """Generate and download a system report for the client."""
    token = request.cookies.get("portal_token", "")
    if not token:
        raise HTTPException(status_code=401)
    
    async with async_session() as db:
        user_id = portal_sessions.get(token)
        if not user_id:
            raise HTTPException(status_code=401)
        
        result = await db.execute(select(ClientUser).where(ClientUser.id == user_id))
        user = result.scalars().first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401)
        
        client_result = await db.execute(select(Client).where(Client.id == user.client_id))
        client = client_result.scalars().first()
        if not client:
            raise HTTPException(status_code=404)
        
        inst_result = await db.execute(
            select(HomeAssistantInstance).where(
                HomeAssistantInstance.client_id == client.id
            ).order_by(HomeAssistantInstance.last_seen.desc())
        )
        instance = inst_result.scalars().first()
        
        # Build report HTML
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        addons_list = instance.addons if instance and instance.addons else []
        integrations_list = instance.integrations if instance and instance.integrations else []
        updates_list = instance.updates_available if instance and instance.updates_available else []
        
        addons_html = ""
        for a in addons_list[:20]:
            name = a.get("name", "Unknown") if isinstance(a, dict) else str(a)
            version = a.get("version", "") if isinstance(a, dict) else ""
            state = a.get("state", "") if isinstance(a, dict) else ""
            addons_html += f"<tr><td>{name}</td><td>{version}</td><td>{state}</td></tr>"
        if not addons_html:
            addons_html = "<tr><td colspan='3'>No add-ons data available</td></tr>"
        
        integrations_html = ""
        for i_name in integrations_list[:30]:
            integrations_html += f"<tr><td>{i_name}</td></tr>"
        if not integrations_html:
            integrations_html = "<tr><td>No integrations data available</td></tr>"
        
        updates_html = ""
        for u in updates_list[:10]:
            u_name = u.get("name", u) if isinstance(u, dict) else str(u)
            updates_html += f"<li>{u_name}</li>"
        if not updates_html:
            updates_html = "<li>System is up to date</li>"
        
        disk_info = "N/A"
        if instance and instance.disk_used_gb:
            disk_info = f"{instance.disk_used_gb:.1f} GB used"
            if instance.disk_total_gb:
                disk_info += f" / {instance.disk_total_gb:.1f} GB total ({instance.disk_usage_percent:.1f}%)"
        
        report_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>System Report - {client.name}</title>
<style>
body {{ font-family: 'Segoe UI', sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; color: #333; }}
h1 {{ color: #7c3aed; border-bottom: 2px solid #7c3aed; padding-bottom: 10px; }}
h2 {{ color: #6d28d9; margin-top: 30px; }}
.meta {{ color: #666; font-size: 14px; margin-bottom: 30px; }}
table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #eee; }}
th {{ background: #f5f3ff; font-weight: 600; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }}
.card {{ background: #faf5ff; border: 1px solid #e9d5ff; border-radius: 8px; padding: 15px; }}
.card h3 {{ margin: 0 0 5px; color: #7c3aed; font-size: 24px; }}
.card p {{ margin: 0; color: #666; font-size: 12px; }}
.status {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }}
.status-online {{ background: #d1fae5; color: #065f46; }}
.status-offline {{ background: #fee2e2; color: #991b1b; }}
ul {{ padding-left: 20px; }}
li {{ margin: 4px 0; }}
@media print {{ body {{ margin: 0; }} .no-print {{ display: none; }} }}
</style></head>
<body>
<div class="no-print" style="text-align:right;margin-bottom:20px;">
<button onclick="window.print()" style="background:#7c3aed;color:white;border:none;padding:10px 24px;border-radius:8px;cursor:pointer;font-size:14px;">🖨️ Print / Save PDF</button>
</div>
<h1>🏠 Burghscape System Report</h1>
<p class="meta">Generated: {now} SAST &nbsp;|&nbsp; Client: {client.name} &nbsp;|&nbsp; Report Type: System Summary</p>

<div class="grid">
<div class="card"><h3>{instance.ha_version if instance else 'N/A'}</h3><p>HA Version</p></div>
<div class="card"><h3>{'Online' if instance and instance.is_online else 'Offline'}</h3><p>System Status</p></div>
<div class="card"><h3>{instance.entities_count if instance else 0}</h3><p>Entities</p></div>
<div class="card"><h3>{instance.automations_count if instance else 0}</h3><p>Automations</p></div>
<div class="card"><h3>{len(addons_list)}</h3><p>Add-ons</p></div>
<div class="card"><h3>{len(integrations_list)}</h3><p>Integrations</p></div>
</div>

<h2>💾 Storage</h2>
<p>{disk_info}</p>

<h2>📦 Add-ons ({len(addons_list)})</h2>
<table><tr><th>Name</th><th>Version</th><th>State</th></tr>{addons_html}</table>

<h2>🔌 Integrations ({len(integrations_list)})</h2>
<table><tr><th>Integration Name</th></tr>{integrations_html}</table>

<h2>🔄 Updates Available ({len(updates_list)})</h2>
<ul>{updates_html}</ul>

<h2>📋 Notes</h2>
<p style="font-size:13px;color:#666;">This report is auto-generated by Burghscape Pty Ltd's monitoring system. For support, contact support@mybeacon.co.za</p>
</body></html>"""
        
        return HTMLResponse(
            content=report_html,
            headers={
                "Content-Disposition": f'attachment; filename="burghscape-report-{client.subdomain}-{now.replace(":", "-")}.html"'
            }
        )


@router.get("/portal/change-password", response_class=HTMLResponse)
async def portal_change_password_page(request: Request):
    """Force password change page for first-time login."""
    token = request.cookies.get("portal_token", "")
    if not token:
        return HTMLResponse(status_code=302, headers={"Location": "/portal/login"})
    async with async_session() as db:
        user_id = portal_sessions.get(token)
        if not user_id:
            return HTMLResponse(status_code=302, headers={"Location": "/portal/login"})
        result = await db.execute(select(ClientUser).where(ClientUser.id == user_id))
        user = result.scalars().first()
        if not user or not user.is_active:
            return HTMLResponse(status_code=302, headers={"Location": "/portal/login"})
        return CHANGE_PASSWORD_HTML



@router.get("/portal/login", response_class=HTMLResponse)
async def portal_login_page():
    return LOGIN_HTML


@router.get("/portal/logout")
async def portal_logout():
    response = HTMLResponse(status_code=302, headers={"Location": "/portal/login"})
    response.delete_cookie("portal_token")
    return response


@router.get("/portal", response_class=HTMLResponse)
async def client_portal(request: Request):
    token = request.cookies.get("portal_token", "")
    if not token:
        return HTMLResponse(status_code=302, headers={"Location": "/portal/login"})

    async with async_session() as db:
        # Validate token
        user_id = portal_sessions.get(token)
        if not user_id:
            return HTMLResponse(status_code=302, headers={"Location": "/portal/login"})
        
        result = await db.execute(select(ClientUser).where(ClientUser.id == user_id))
        user = result.scalars().first()
        if not user or not user.is_active:
            return HTMLResponse(status_code=302, headers={"Location": "/portal/login"})

        if user.force_password_change:
            return HTMLResponse(status_code=302, headers={"Location": "/portal/change-password"})

        # Get client
        client_result = await db.execute(select(Client).where(Client.id == user.client_id))
        client = client_result.scalars().first()
        if not client:
            return HTMLResponse(status_code=302, headers={"Location": "/portal/login"})

        # Get instance
        inst_result = await db.execute(
            select(HomeAssistantInstance).where(
                HomeAssistantInstance.client_id == client.id
            ).order_by(HomeAssistantInstance.last_seen.desc())
        )
        instance = inst_result.scalars().first()

        # Get tickets
        tickets_result = await db.execute(
            select(SupportTicket).where(
                SupportTicket.client_id == client.id
            ).order_by(SupportTicket.created_at.desc()).limit(10)
        )
        tickets = tickets_result.scalars().all()

        # Get portal users
        users_result = await db.execute(
            select(ClientUser).where(ClientUser.client_id == client.id)
        )
        users = users_result.scalars().all()

        # Build tickets HTML
        tickets_html = ""
        for t in tickets:
            status_colors = {
                "open": "bg-blue-900 text-blue-300",
                "in_progress": "bg-purple-900 text-purple-300",
                "completed": "bg-green-900 text-green-300",
                "closed": "bg-gray-700 text-gray-400",
            }
            priority_colors = {
                "high": "bg-red-900 text-red-300",
                "normal": "bg-yellow-900 text-yellow-300",
                "low": "bg-gray-700 text-gray-400",
            }
            created = t.created_at.strftime('%Y-%m-%d') if t.created_at else 'Unknown'
            tickets_html += f'<div class="bg-gray-900 rounded-lg p-3"><div class="flex items-center justify-between"><span class="font-medium text-sm">{t.title}</span><div class="flex gap-2"><span class="text-xs px-2 py-0.5 rounded-full {priority_colors.get(t.priority, "bg-gray-700 text-gray-400")}">{t.priority}</span><span class="text-xs px-2 py-0.5 rounded-full {status_colors.get(t.status, "bg-gray-700 text-gray-400")}">{t.status}</span></div></div><p class="text-xs text-gray-400 mt-1">{t.hours_used}h used • {created}</p></div>'

        if not tickets:
            tickets_html = '<p class="text-gray-500 text-sm">No tickets yet.</p>'

        # Build users HTML
        users_html = ""
        for u in users:
            users_html += f'<div class="flex items-center justify-between bg-gray-900 rounded-lg p-3"><div><p class="text-sm font-medium">{u.name}</p><p class="text-xs text-gray-400">{u.email}</p></div><button onclick="removeUser({u.id})" class="text-red-400 hover:text-red-300 text-xs">Remove</button></div>'

        if not users:
            users_html = '<p class="text-gray-500 text-sm">No users yet.</p>'

        hours_included = client.monthly_hours_included
        hours_used = client.hours_used_this_month
        hours_remaining = max(0, hours_included - hours_used)
        hours_percent = min(100, (hours_used / hours_included * 100)) if hours_included > 0 else 0
        online = instance.is_online if instance else False

        # Calculate addon/integration counts from JSON
        addons_list = instance.addons if instance and instance.addons else []
        integrations_list = instance.integrations if instance and instance.integrations else []
        addon_count = len(addons_list)
        integration_count = len(integrations_list)

        # DB size (from agent disk usage report)
        db_size = "N/A"
        if instance and instance.disk_used_gb:
            db_size = "{:.1f} GB used".format(instance.disk_used_gb)
            if instance.disk_total_gb:
                db_size += " / {:.1f} GB ({:.0f}%)".format(instance.disk_total_gb, instance.disk_usage_percent or 0)
        elif instance and instance.disk_usage_percent:
            db_size = "{:.0f}% used".format(instance.disk_usage_percent)

        # Uptime from agent (seconds since HA started)
        uptime = "N/A"
        if instance and instance.uptime_seconds and instance.uptime_seconds > 0:
            s = instance.uptime_seconds
            if s < 60:
                uptime = "{} sec".format(s)
            elif s < 3600:
                uptime = "{} min".format(s // 60)
            elif s < 86400:
                uptime = "{}h {}m".format(s // 3600, (s % 3600) // 60)
            else:
                uptime = "{}d {}h".format(s // 86400, (s % 86400) // 3600)
        elif instance and instance.last_seen:
            from datetime import datetime as _dt
            delta = _dt.now() - instance.last_seen
            uptime = "Seen {}m ago".format(int(delta.total_seconds() // 60))

        # Updates available - show individual items
        updates_list = instance.updates_available if instance and instance.updates_available else []
        updates_count = len(updates_list)
        if updates_count == 0:
            updates_html = '<span class="text-emerald-400">✓ Up to date</span>'
        else:
            items = ''
            for u in updates_list[:10]:
                name = u.get("name", u) if isinstance(u, dict) else str(u)
                ver = u.get("version", "") if isinstance(u, dict) else ""
                items += f'<li class="text-amber-300 text-sm py-1">• {name}'
                if ver:
                    items += f' <span class="text-gray-500">→ {ver}</span>'
                items += '</li>'
            updates_html = f'<span class="text-amber-400 font-medium">{updates_count} update(s)</span><ul class="ml-4 mt-2 list-disc">{items}</ul>'

        # HA News section with links to official blog
        latest_ha_version = instance.ha_version if instance else "N/A"
        ha_news_section = f'''
        <div class="card rounded-2xl p-6 mb-6">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-lg font-semibold text-white">Home Assistant</h2>
                <span class="text-xs bg-purple-500/20 text-purple-300 px-3 py-1 rounded-full">Running: {latest_ha_version}</span>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
                <a href="https://www.home-assistant.io/blog/categories/release-notes/" target="_blank" rel="noopener"
                   class="flex items-center gap-3 bg-purple-500/5 hover:bg-purple-500/10 rounded-xl p-4 border border-purple-500/10 transition group">
                    <svg class="w-5 h-5 text-purple-400 group-hover:text-purple-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
                    <div>
                        <p class="text-sm font-medium text-white">Release Notes</p>
                        <p class="text-xs text-gray-500">Monthly HA updates &amp; new features</p>
                    </div>
                    <svg class="w-4 h-4 text-gray-600 ml-auto group-hover:text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                </a>
                <a href="https://www.home-assistant.io/blog/categories/breaking-changes/" target="_blank" rel="noopener"
                   class="flex items-center gap-3 bg-amber-500/5 hover:bg-amber-500/10 rounded-xl p-4 border border-amber-500/10 transition group">
                    <svg class="w-5 h-5 text-amber-400 group-hover:text-amber-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"/></svg>
                    <div>
                        <p class="text-sm font-medium text-white">Breaking Changes</p>
                        <p class="text-xs text-gray-500">Important changes to be aware of</p>
                    </div>
                    <svg class="w-4 h-4 text-gray-600 ml-auto group-hover:text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                </a>
            </div>
        </div>'''


        # Backup status
        backup_enabled = False
        last_backup_str = "Not configured"
        next_backup_str = "N/A"
        if instance and instance.last_backup:
            backup_enabled = True
            from datetime import datetime as _dt
            lb = instance.last_backup
            if isinstance(lb, str):
                last_backup_str = lb
            else:
                delta = _dt.now() - lb
                if delta.days > 0:
                    last_backup_str = "{} day(s) ago".format(delta.days)
                elif delta.seconds > 3600:
                    last_backup_str = "{}h ago".format(delta.seconds // 3600)
                else:
                    last_backup_str = "{}m ago".format(delta.seconds // 60)
            if instance.next_backup:
                nb = instance.next_backup
                if isinstance(nb, str):
                    next_backup_str = nb
                else:
                    next_backup_str = nb.strftime("%Y-%m-%d %H:%M")

        return PORTAL_HTML.format(
            client_name=client.name,
            subdomain=client.subdomain,
            status_class="bg-green-900 text-green-300" if client.status.value == "active" else "bg-red-900 text-red-300",
            status_text=client.status.value.capitalize(),
            online_class="text-green-400" if online else "text-red-400",
            online_dot_class="status-online" if online else "status-offline",
            online_text_class="text-green-400" if online else "text-red-400",
            online_status="Online" if online else "Offline",
            ha_version=instance.ha_version or "N/A",
            entity_count=instance.entities_count or 0,
            addon_count_display="?" if addon_count == 0 and integration_count > 0 else addon_count,
            addon_count_suffix=" (pending)" if addon_count == 0 and integration_count > 0 else "",
            addon_count=addon_count,
            integration_count=integration_count,
            user_name=user.name,
            db_size=db_size,
            uptime=uptime,
            updates_count=updates_html,
            updates_class="text-emerald-400",
            last_seen=instance.last_seen.strftime("%Y-%m-%d %H:%M") if instance and instance.last_seen else "Never",
            ha_news_section=ha_news_section,
            tickets_html=tickets_html,
            hours_used=hours_used,
            hours_included=hours_included,
            hours_remaining=hours_remaining,
            hours_percent=hours_percent,
            cpu_percent=instance.cpu_usage_percent if instance and instance.cpu_usage_percent else 0,
            memory_percent=instance.memory_usage_percent if instance and instance.memory_usage_percent else 0,
            memory_used_gb=instance.memory_used_gb if instance and instance.memory_used_gb else 0,
            memory_total_gb=instance.memory_total_gb if instance and instance.memory_total_gb else 0,
            disk_percent=instance.disk_usage_percent if instance and instance.disk_usage_percent else 0,
            disk_used_gb=instance.disk_used_gb if instance and instance.disk_used_gb else 0,
            disk_total_gb=instance.disk_total_gb if instance and instance.disk_total_gb else 0,
            backup_badge_class="bg-green-900 text-green-300" if backup_enabled else "bg-gray-700 text-gray-400",
            backup_badge_text="Active" if backup_enabled else "Not Configured",
            last_backup_str=last_backup_str,
            next_backup_str=next_backup_str,
            backup_sync_class="text-green-400" if backup_enabled else "text-gray-500",
            backup_sync_text="✓ Synced" if backup_enabled else "—",
        )
