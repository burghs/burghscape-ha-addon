"""Client Portal — public-facing portal served at client.mybeacon.co.za"""
from datetime import datetime
from html import escape
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from models import Backup, Client, SupportTicket, ClientUser, HomeAssistantInstance, SubscriptionToken
from routers.backups import build_backup_file_response, is_customer_backup_available, meaningful_backup_filename
from support_hours import calculate_support_hours, format_hours, support_ticket_notice

router = APIRouter()

ADDON_REPOSITORY_URL = "https://github.com/burghs/burghscape-ha-addon"

# In-memory session store (use JWT or Redis in production)
from routers.portal_state import portal_sessions


PORTAL_HTML = """<!DOCTYPE html>
<html lang="en" data-theme-enabled>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="/static/theme.js"></script>
    <title>{client_name} - Burghscape Portal</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; }}
        html {{ width: 100%; overflow-x: hidden; }}
        body {{ font-family: 'Inter', sans-serif; background: #030712; margin: 0; overflow-x: hidden; min-width: 0; }}
        .bg-grid {{
            background-color: #030712;
            background-image: radial-gradient(circle at top left, rgba(139,92,246,0.16), transparent 34%),
                              linear-gradient(rgba(139,92,246,0.035) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(139,92,246,0.035) 1px, transparent 1px);
            background-size: auto, 60px 60px, 60px 60px;
        }}
        .card {{ background: rgba(17,24,39,0.86); border: 1px solid rgba(255,255,255,0.10); backdrop-filter: blur(16px); box-shadow: 0 18px 45px rgba(0,0,0,0.24); }}
        .status-dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex: 0 0 auto; }}
        .status-online {{ background: #34d399; box-shadow: 0 0 8px rgba(52,211,153,0.5); }}
        .status-offline {{ background: #f87171; }}
        .progress-bar {{ background: rgba(255,255,255,0.10); border-radius: 999px; overflow: hidden; }}
        .progress-fill {{ background: linear-gradient(90deg, #8b5cf6, #6d28d9); height: 100%; border-radius: 999px; transition: width 1s; }}
        .nav-link {{ transition: all 0.2s; }}
        .nav-link:hover {{ color: #a78bfa; }}
        .campaign-nav-unread {{ color:#c4b5fd !important; text-shadow:0 0 14px rgba(167,139,250,.58); }}
        .campaign-unread-pulse {{ animation:campaignUnreadPulse 2.8s ease-in-out infinite; }}
        .campaign-unread-banner {{ display:flex; align-items:center; justify-content:space-between; gap:14px; border:1px solid rgba(167,139,250,.3); background:rgba(139,92,246,.1); }}
        body.onboarding-active #campaign-unread-banner {{ display:none !important; }}
        @keyframes campaignUnreadPulse {{ 0%,100% {{ box-shadow:0 0 0 rgba(139,92,246,0); }} 50% {{ box-shadow:0 0 14px rgba(139,92,246,.42); }} }}
        .brand-logo {{ height: 40px; width: 40px; object-fit: contain; display: block; flex-shrink: 0; }}
        .portal-card {{ border-radius: 16px; }}
        .detail-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr)); gap: 14px; }}
        .detail-item {{ border: 1px solid rgba(255,255,255,0.10); background: rgba(255,255,255,0.045); border-radius: 14px; padding: 14px; min-width: 0; }}
        .detail-label {{ color: #6b7280; font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; }}
        .detail-value {{ color: #ddd6fe; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; overflow-wrap: anywhere; word-break: break-word; margin-top: 6px; min-width: 0; }}
        .copy-chip {{ display: inline-flex; align-items: center; justify-content: center; border: 1px solid rgba(167,139,250,0.26); background: rgba(139,92,246,0.12); color: #ddd6fe; border-radius: 10px; padding: 9px 11px; min-height: 40px; font-size: 12px; font-weight: 700; transition: background .2s ease; }}
        .copy-chip:hover {{ background: rgba(139,92,246,0.22); }}
        .copy-chip:disabled {{ opacity: .5; cursor: not-allowed; }}
        .action-feedback {{ color: #34d399; font-size: 12px; min-height: 18px; }}
        input, select, textarea {{ font-size: 16px; }}
        .portal-actions {{ display:grid; grid-template-columns: 1fr; gap:10px; margin-top:14px; }}
        .portal-action {{ border:1px solid rgba(167,139,250,0.22); border-radius:14px; background:rgba(255,255,255,0.045); padding:13px; color:#e5e7eb; transition:background .2s ease, border-color .2s ease; min-width:0; overflow:hidden; }}
        .portal-action:hover {{ background:rgba(139,92,246,0.12); border-color:rgba(167,139,250,0.34); }}
        .portal-action-text {{ overflow-wrap:anywhere; word-break:break-word; }}
        .compact-action {{ display:inline-flex; align-items:center; justify-content:center; gap:8px; border-radius:12px; padding:10px 14px; min-height:42px; font-size:13px; font-weight:700; color:#fff; background:linear-gradient(135deg,#8b5cf6,#6d28d9); box-shadow:0 10px 24px rgba(139,92,246,.18); white-space:nowrap; }}
        .compact-action:hover {{ filter:brightness(1.08); }}
        .info-row {{ display:flex; align-items:center; justify-content:space-between; gap:16px; }}
        @media (max-width: 640px) {{
            nav > div {{ flex-direction: column; align-items: stretch; }}
            nav .brand-logo {{ height:34px; width:34px; }}
            nav .shrink-0 {{ flex-wrap: wrap; justify-content: flex-start; }}
            #pw-form-nav {{ max-width: none; margin-left: 0; }}
            .portal-card {{ padding: 16px !important; }}
            .detail-item .mt-2 {{ flex-wrap: wrap; }}
            .detail-value {{ flex-basis: 100%; font-size: 12px; }}
            .copy-chip {{ flex: 1 1 auto; }}
            .portal-actions {{ grid-template-columns: 1fr; }}
        }}

        .dashboard-grid {{ display:grid; grid-template-columns:1fr; gap:1rem; }}
        .metric-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.75rem; }}
        .metric-tile {{ border:1px solid rgba(255,255,255,.08); background:rgba(255,255,255,.035); border-radius:12px; padding:12px; min-width:0; }}
        .touch-action {{ min-height:44px; display:inline-flex; align-items:center; justify-content:center; border-radius:12px; padding:10px 14px; font-size:13px; font-weight:700; }}
        .focusable:focus-visible, button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible {{ outline:2px solid #a78bfa; outline-offset:2px; }}
        body.onboarding-active > *:not(#onboarding-modal):not(script) {{ pointer-events:none; }}
        .onboarding-spotlight {{ position:relative; z-index:60; outline:3px solid #a78bfa; outline-offset:5px; }}
        @media (prefers-reduced-motion: reduce) {{ .onboarding-spotlight, .progress-fill {{ transition:none !important; scroll-behavior:auto !important; }} .campaign-unread-pulse {{ animation:none !important; }} }}
        body.campaign-popup-open {{ overflow:hidden; }}
        .campaign-modal-backdrop {{ position:fixed; inset:0; z-index:80; display:flex; align-items:center; justify-content:center; padding:16px; background:rgba(3,7,18,.84); overscroll-behavior:contain; }}
        .campaign-modal-backdrop.hidden {{ display:none; }}
        .campaign-modal-card {{ width:min(100%,640px); max-height:calc(100dvh - 32px); overflow-y:auto; border-radius:20px; box-shadow:0 28px 80px rgba(0,0,0,.55); }}
        .campaign-modal-image {{ display:block; width:100%; max-height:min(36dvh,320px); object-fit:cover; aspect-ratio:16/8; }}
        .portal-modal {{ position:fixed; inset:0; z-index:50; display:flex; align-items:center; justify-content:center; padding:16px; background:rgba(3,7,18,.78); }}
        .portal-modal.hidden {{ display:none; }}
        .modal-panel {{ width:min(100%,760px); max-height:calc(100dvh - 32px); overflow-y:auto; border-radius:20px; }}
        .backup-row {{ display:flex; align-items:center; justify-content:space-between; gap:16px; border-top:1px solid rgba(255,255,255,.08); padding:14px 0; }}
        @media (min-width:768px) {{ .dashboard-grid {{ grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:1.5rem; }} .metric-grid {{ grid-template-columns:repeat(3,minmax(0,1fr)); }} }}
        @media (max-width:640px) {{ .backup-row {{ align-items:stretch; flex-direction:column; }} .backup-row .compact-action, .mobile-full {{ width:100%; }} .modal-panel {{ max-height:calc(100dvh - 20px); border-radius:16px; }} }}
        @media (max-width:640px) {{ .campaign-unread-banner {{ align-items:stretch; flex-direction:column; }} .campaign-unread-banner .compact-action {{ width:100%; }} }}
        @media (max-width:640px) {{ .campaign-modal-backdrop {{ padding:10px; }} .campaign-modal-card {{ max-height:calc(100dvh - 20px); border-radius:16px; padding:16px !important; }} .campaign-modal-image {{ max-height:30dvh; aspect-ratio:16/9; }} .campaign-modal-actions > * {{ width:100%; }} }}
        @media (max-width:390px) {{ .campaign-modal-backdrop {{ padding:6px; }} .campaign-modal-card {{ max-height:calc(100dvh - 12px); border-radius:14px; }} }}
    </style>
    <link rel="stylesheet" href="/static/theme.css">
</head>
<body class="bg-gray-950 text-gray-200 min-h-screen bg-grid" id="app-body">
    <nav class="card border-b border-white/10 px-4 md:px-6 py-3">
        <div class="max-w-7xl mx-auto flex items-center justify-between gap-3">
            <div class="flex min-w-0 items-center gap-3">
                <img src="/static/brand/burghscape-shield.svg" alt="Burghscape" class="brand-logo">
                <div class="min-w-0 leading-tight"><div class="text-sm font-semibold text-white">Burghscape</div><div class="truncate text-xs uppercase tracking-[0.16em] text-purple-300">Client Portal</div></div>
                <span class="hidden lg:inline text-sm text-gray-400 truncate">{client_name}</span>
            </div>
            <div class="hidden sm:flex shrink-0 items-center gap-4 text-sm">
                <span class="text-gray-400">{user_name}</span><a id="campaign-nav-desktop" data-onboarding-target="campaigns" href="/portal/whats-new" class="nav-link text-gray-400 hover:text-purple-300">What’s New <span id="campaign-unread-desktop" class="hidden badge badge-primary ml-1"></span></a><a data-onboarding-target="getting-started" href="/portal/getting-started" class="{setup_nav_class}">{setup_nav_label}</a>
                <button data-onboarding-target="account" type="button" onclick="toggleAccountPanel()" class="nav-link text-gray-400 hover:text-purple-300">Account</button><a href="/portal/logout" class="nav-link text-gray-400 hover:text-purple-300">Logout</a>
            </div>
            <button type="button" class="sm:hidden touch-action border border-white/10 text-white" aria-controls="mobile-nav" aria-expanded="false" onclick="toggleMobileNav(this)">Menu</button>
        </div>
        <div id="mobile-nav" class="hidden sm:hidden max-w-7xl mx-auto mt-3 grid gap-2 border-t border-white/10 pt-3 text-sm">
            <span class="text-gray-400 px-2">{user_name}</span><a id="campaign-nav-mobile" href="/portal/whats-new" class="touch-action justify-start text-gray-300">What’s New <span id="campaign-unread-mobile" class="hidden badge badge-primary ml-1"></span></a><a href="/portal/getting-started" class="touch-action justify-start text-purple-300">{setup_nav_label}</a>
            <button type="button" onclick="toggleAccountPanel();toggleMobileNav(document.querySelector('[aria-controls=mobile-nav]'))" class="touch-action justify-start text-gray-300">Account</button><a href="/portal/logout" class="touch-action justify-start text-gray-300">Logout</a>
        </div>
        <div id="pw-form-nav" class="hidden max-w-7xl mx-auto mt-3 p-4 bg-gray-900/80 rounded-xl border border-purple-500/10 sm:max-w-sm sm:ml-auto">
            <fieldset class="theme-control mb-5"><legend class="text-sm font-semibold text-white">Theme</legend><p class="text-xs text-gray-500 mt-1">System follows your device appearance.</p><div class="theme-options" role="radiogroup" aria-label="Theme"><button type="button" role="radio" data-theme-choice="system" class="theme-option" onclick="choosePortalTheme('system')">System</button><button type="button" role="radio" data-theme-choice="light" class="theme-option" onclick="choosePortalTheme('light')">Light</button><button type="button" role="radio" data-theme-choice="dark" class="theme-option" onclick="choosePortalTheme('dark')">Dark</button></div></fieldset>
            <p class="text-sm font-semibold text-white mb-3">Change password</p>
            <input type="password" id="pw-current-nav" placeholder="Current password" class="w-full bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-3 mb-2 text-white">
            <input type="password" id="pw-new-nav" placeholder="New password" class="w-full bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-3 mb-2 text-white">
            <input type="password" id="pw-confirm-nav" placeholder="Confirm password" class="w-full bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-3 mb-3 text-white">
            <button type="button" onclick="changePasswordNav()" class="compact-action w-full">Update password</button><p id="pw-msg-nav" class="text-sm mt-2 hidden"></p>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto px-4 py-5 sm:px-6 sm:py-7">
        {onboarding_banner_html}
        <aside id="campaign-unread-banner" class="hidden campaign-unread-banner portal-card mb-4 p-4 sm:mb-6" aria-live="polite"><p id="campaign-unread-message" class="text-sm font-semibold text-purple-100"></p><a href="/portal/whats-new" class="compact-action shrink-0">View What’s New</a></aside>
        <section data-onboarding-target="instance" class="card portal-card p-5 sm:p-6 mb-4 sm:mb-6" aria-labelledby="instance-heading">
            <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div class="min-w-0"><div class="flex flex-wrap items-center gap-3"><h1 id="instance-heading" class="text-xl sm:text-2xl font-bold text-white truncate">{instance_name}</h1><span class="inline-flex items-center gap-2 text-sm {online_text_class}"><span class="status-dot {online_dot_class}"></span>{online_status}</span></div>
                    <div class="mt-4 grid grid-cols-3 gap-3 text-center sm:text-left"><div><strong class="block text-xl text-white">{entity_count}</strong><span class="text-xs text-gray-500">Entities</span></div><div><strong class="block text-xl text-white">{addon_count_display}</strong><span class="text-xs text-gray-500">Add-ons{addon_count_suffix}</span></div><div><strong class="block text-xl text-white">{integration_count}</strong><span class="text-xs text-gray-500">Integrations</span></div></div>
                </div>
                <button type="button" onclick="openPortalModal('setup-modal')" class="compact-action mobile-full">Setup Details</button>
            </div>
        </section>

        <div class="dashboard-grid mb-4 sm:mb-6">
            <section class="card portal-card p-5 sm:p-6" aria-labelledby="overview-heading">
                <h2 id="overview-heading" class="text-lg font-semibold text-white mb-4">System Overview</h2>
                <div class="space-y-4">
                    <div><div class="flex justify-between text-sm mb-1"><span class="text-gray-400">CPU usage</span><span class="text-white">{cpu_percent}%</span></div><div class="progress-bar h-2"><div class="progress-fill" style="width:{cpu_percent}%"></div></div></div>
                    <div><div class="flex justify-between text-sm mb-1"><span class="text-gray-400">Memory usage</span><span class="text-white">{memory_used_gb} / {memory_total_gb} GB ({memory_percent}%)</span></div><div class="progress-bar h-2"><div class="progress-fill" style="width:{memory_percent}%"></div></div></div>
                    <div><div class="flex justify-between text-sm mb-1"><span class="text-gray-400">Disk usage</span><span class="text-white">{disk_used_gb} / {disk_total_gb} GB ({disk_percent}%)</span></div><div class="progress-bar h-2"><div class="progress-fill" style="width:{disk_percent}%"></div></div></div>
                </div>
                <dl class="metric-grid mt-5 text-sm"><div class="metric-tile"><dt class="text-gray-500">Database / storage</dt><dd class="text-white mt-1">{db_size}</dd></div><div class="metric-tile"><dt class="text-gray-500">Home Assistant</dt><dd class="text-white mt-1">{ha_version}</dd></div><div class="metric-tile"><dt class="text-gray-500">Last report</dt><dd class="text-white mt-1">{last_seen}</dd></div></dl>
            </section>

            <section class="card portal-card p-5 sm:p-6" aria-labelledby="environment-heading">
                <div class="flex items-start justify-between gap-3"><div><h2 id="environment-heading" class="text-lg font-semibold text-white">Environment &amp; Updates</h2><p class="text-sm text-gray-500 mt-1">Home Assistant {ha_version}</p></div><span class="text-xs px-3 py-1 rounded-full {online_class}">{online_status}</span></div>
                <div class="mt-5 text-sm"><div class="text-gray-400 mb-2">Available updates</div><div>{updates_count}</div></div>
                <button type="button" onclick="openPortalModal('release-modal')" class="touch-action mt-5 border border-purple-400/25 bg-purple-500/10 text-purple-200 mobile-full">View release information</button>
            </section>
        </div>

        <section data-onboarding-target="backups" class="card portal-card p-5 sm:p-6 mb-4 sm:mb-6" aria-labelledby="backup-heading">
            <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"><div><h2 id="backup-heading" class="text-lg font-semibold text-white">Backup Protection</h2><p id="backup-protection-status" class="text-sm text-gray-400 mt-1">Checking protection status…</p></div><span id="managed-backup-state" class="text-xs text-gray-300">Loading</span></div>
            <div class="metric-grid mt-5 text-sm"><div class="metric-tile"><div class="text-gray-500">Backup method</div><div class="text-white mt-1">On-demand managed backups</div></div><div class="metric-tile"><div class="text-gray-500">Automatic cloud schedule</div><div class="text-white mt-1">Not configured</div></div><div class="metric-tile"><div class="text-gray-500">Retention policy</div><div class="text-white mt-1">Not configured</div></div></div>
            <div class="mt-6"><div class="flex items-center justify-between gap-3"><h3 class="font-semibold text-white">Managed backup history</h3><span id="managed-backup-count" class="text-xs text-gray-500"></span></div><div id="managed-backup-list" data-instance="{instance_name}" class="mt-2 text-sm"><p class="text-gray-500">Loading backups…</p></div><button id="backup-history-toggle" type="button" class="hidden touch-action mt-2 text-purple-300"></button></div>
            <div class="mt-5 rounded-xl border border-white/10 bg-white/[0.025] p-4"><h3 class="font-semibold text-white">Home Assistant local backups</h3>{native_backup_html}</div>
        </section>

        <section data-onboarding-target="support" class="card portal-card p-5 sm:p-6" aria-labelledby="support-heading">
            <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"><div><h2 id="support-heading" class="text-lg font-semibold text-white">Account &amp; Support</h2><p class="text-sm text-gray-500 mt-1">Support usage, tickets and diagnostic report</p></div><a href="/portal/getting-started" class="text-sm text-purple-300">Getting Started</a></div>
            <div class="metric-grid mt-5 text-sm"><div class="metric-tile"><div class="text-gray-500">Included support</div><div class="text-white mt-1">{hours_included}h</div></div><div class="metric-tile"><div class="text-gray-500">Support time logged</div><div class="text-white mt-1">{hours_logged}h</div></div>{support_remaining_html}<div class="metric-tile"><div class="text-gray-500">Potentially billable</div><div class="text-white mt-1">{hours_billable}h</div></div><div class="metric-tile"><div class="text-gray-500">Open tickets</div><div class="text-white mt-1">{open_ticket_count}</div></div><div class="metric-tile"><div class="text-gray-500">Latest ticket</div><div class="text-white mt-1">{latest_ticket_status}</div></div></div>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-5"><button type="button" onclick="document.getElementById('ticket-form').classList.toggle('hidden')" class="compact-action">New Support Ticket</button><a href="mailto:support@mybeacon.co.za" class="touch-action border border-white/10 text-white">Contact Support</a><a href="/api/portal/report" target="_blank" class="touch-action border border-white/10 text-white">Download Report</a></div>
            <div id="ticket-form" class="hidden mt-5 p-4 bg-gray-900/60 rounded-xl border border-purple-500/10">{support_ticket_notice_html}<input type="text" id="ticket-title" placeholder="Ticket title" class="w-full bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-3 mb-2 text-white"><textarea id="ticket-desc" placeholder="How can we help?" rows="3" class="w-full bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-3 mb-2 text-white"></textarea><div class="flex flex-col sm:flex-row gap-2"><select id="ticket-priority" class="flex-1 bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-3 text-white"><option value="low">Low</option><option value="normal" selected>Normal</option><option value="high">High</option></select><button type="button" onclick="submitTicket()" class="compact-action">Submit Ticket</button></div></div>
            <div class="mt-5"><h3 class="font-semibold text-white mb-3">Recent tickets</h3><div id="tickets-list" class="space-y-2 max-h-56 overflow-y-auto">{tickets_html}</div></div>
        </section>
    </main>

    <div id="setup-modal" class="portal-modal hidden" role="dialog" aria-modal="true" aria-labelledby="setup-modal-title" onclick="closeOnBackdrop(event,'setup-modal')">
        <div class="card modal-panel p-5 sm:p-6" tabindex="-1"><div class="flex items-start justify-between gap-4"><div><h2 id="setup-modal-title" class="text-xl font-semibold text-white">Setup Details</h2><p class="text-sm text-gray-500 mt-1">Connection and installation values</p></div><button type="button" aria-label="Close setup details" onclick="closePortalModal('setup-modal')" class="touch-action text-gray-300">Close</button></div><span id="details-feedback" class="action-feedback block mt-2"></span>
            <div class="detail-grid mt-4"><div class="detail-item"><div class="detail-label">Burghscape Add-on Repository URL</div><div class="mt-2 flex flex-wrap items-center gap-2"><span class="detail-value flex-1">{addon_repository_url}</span><button class="copy-chip" onclick="copyPortalValue('{addon_repository_url}','Repository URL copied','details-feedback')">Copy</button></div></div><div class="detail-item"><div class="detail-label">Subscription Token</div><div class="mt-2 flex flex-wrap items-center gap-2"><span id="subscription-token-value" class="detail-value flex-1" data-masked="{subscription_token_masked}" data-secret="{subscription_token_secret}" data-visible="false">{subscription_token_masked}</span><button class="copy-chip" {subscription_token_disabled} onclick="toggleSecret('subscription-token-value',this,'details-feedback')">Show</button><button class="copy-chip" {subscription_token_disabled} onclick="copySecretValue('subscription-token-value','Subscription token copied','details-feedback')">Copy</button></div></div><div class="detail-item"><div class="detail-label">Home Assistant Remote URL</div><div class="mt-2 flex flex-wrap items-center gap-2"><span class="detail-value flex-1">{remote_url}</span><button class="copy-chip" onclick="copyPortalValue('{remote_url}','Remote URL copied','details-feedback')">Copy</button><a href="{remote_url}" target="_blank" rel="noopener" class="copy-chip">Open</a></div></div><div class="detail-item"><div class="detail-label">Client Portal URL</div><div class="mt-2 flex flex-wrap items-center gap-2"><span class="detail-value flex-1">{client_portal_url}</span><button class="copy-chip" onclick="copyPortalValue('{client_portal_url}','Client Portal URL copied','details-feedback')">Copy</button></div></div><div class="detail-item"><div class="detail-label">Instance name</div><div class="detail-value">{instance_name}</div></div><div class="detail-item"><div class="detail-label">Connection status</div><div class="detail-value {online_text_class}">{online_status}</div></div></div>
        </div>
    </div>
    <div id="release-modal" class="portal-modal hidden" role="dialog" aria-modal="true" aria-labelledby="release-modal-title" onclick="closeOnBackdrop(event,'release-modal')"><div class="card modal-panel p-5 sm:p-6" tabindex="-1"><div class="flex items-start justify-between gap-4"><div><h2 id="release-modal-title" class="text-xl font-semibold text-white">Home Assistant release information</h2><p class="text-sm text-gray-500 mt-1">Review changes before updating.</p></div><button type="button" aria-label="Close release information" onclick="closePortalModal('release-modal')" class="touch-action text-gray-300">Close</button></div><div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-5"><a href="https://www.home-assistant.io/blog/categories/release-notes/" target="_blank" rel="noopener" class="portal-action"><span class="block font-semibold text-white">Release Notes</span><span class="block text-sm text-gray-400 mt-1">Monthly Home Assistant updates</span></a><a href="https://www.home-assistant.io/blog/categories/breaking-changes/" target="_blank" rel="noopener" class="portal-action"><span class="block font-semibold text-white">Breaking Changes</span><span class="block text-sm text-gray-400 mt-1">Compatibility information to review</span></a></div></div></div>

    <script>
        const backupDate=v=>new Intl.DateTimeFormat(undefined,{{dateStyle:'medium',timeStyle:'short',timeZone:'Africa/Johannesburg'}}).format(new Date(v));
        fetch('/api/portal/managed-backup-state',{{credentials:'include'}}).then(r=>r.ok?r.json():Promise.reject()).then(data=>{{const op=data.current_operation;document.getElementById('managed-backup-state').textContent=op?op.state:'No active operation';}}).catch(()=>{{document.getElementById('managed-backup-state').textContent='Status unavailable';}});
        fetch('/api/portal/backups',{{credentials:'include'}}).then(r=>r.ok?r.json():Promise.reject()).then(data=>{{const list=document.getElementById('managed-backup-list'),toggle=document.getElementById('backup-history-toggle'),instance=list.dataset.instance;list.textContent='';document.getElementById('managed-backup-count').textContent=data.backups.length+' stored';document.getElementById('backup-protection-status').textContent=data.backups.length?'Protected by '+data.backups.length+' successful managed backup'+(data.backups.length===1?'':'s'):'No successful managed backup stored';if(!data.backups.length){{list.innerHTML='<p class="text-gray-500 py-3">No completed managed backups stored.</p>';return;}}const rows=[];data.backups.forEach((item,index)=>{{const row=document.createElement('div');row.className='backup-row';row.hidden=index>2;const details=document.createElement('div');details.className='min-w-0';const title=document.createElement(index===0?'h3':'p');title.className=index===0?'font-semibold text-white text-base':'font-medium text-white';title.textContent=instance+' — '+backupDate(item.completed_at);const meta=document.createElement('p');meta.className='text-sm text-gray-400 mt-1';meta.textContent='Successful · '+(item.size_bytes/1048576).toFixed(1)+' MB';details.append(title,meta);const link=document.createElement('a');link.className='compact-action';link.href=item.download_url;link.textContent='Download';row.append(details,link);list.appendChild(row);rows.push(row);}});if(rows.length>3){{let expanded=false;toggle.classList.remove('hidden');toggle.textContent='Show all backups';toggle.onclick=()=>{{expanded=!expanded;rows.forEach((row,index)=>row.hidden=!expanded&&index>2);toggle.textContent=expanded?'Show fewer backups':'Show all backups';}};}}}}).catch(()=>{{document.getElementById('managed-backup-list').innerHTML='<p class="text-gray-500 py-3">Backup history unavailable.</p>';}});
    </script>

    <script>
        let activePortalModal = null;
        function toggleMobileNav(button) {{ const nav=document.getElementById('mobile-nav'); const hidden=nav.classList.toggle('hidden'); if(button) button.setAttribute('aria-expanded', String(!hidden)); }}
        function toggleAccountPanel() {{ document.getElementById('pw-form-nav').classList.toggle('hidden'); }}
        function syncThemeControls() {{ const preference=window.MyBeaconTheme.getPreference(); document.querySelectorAll('[data-theme-choice]').forEach(button=>{{ button.setAttribute('aria-checked',String(button.dataset.themeChoice===preference)); }}); }}
        function choosePortalTheme(value) {{ window.MyBeaconTheme.setPreference(value); syncThemeControls(); }}
        window.addEventListener('mybeacon-theme-change',syncThemeControls);
        syncThemeControls();
        const campaignStatusInterval=30000;
        async function refreshCampaignUnread() {{
            const response=await fetch('/api/portal/campaigns/unread-count',{{credentials:'include',cache:'no-store'}});
            if(!response.ok)return;
            const count=(await response.json()).unread_count||0;
            [['campaign-unread-desktop','campaign-nav-desktop'],['campaign-unread-mobile','campaign-nav-mobile']].forEach(([badgeId,navId])=>{{
                const badge=document.getElementById(badgeId),nav=document.getElementById(navId);
                if(!badge||!nav)return;
                badge.textContent=count||'';
                badge.classList.toggle('hidden',!count);
                badge.classList.toggle('campaign-unread-pulse',!!count);
                nav.classList.toggle('campaign-nav-unread',!!count);
                if(count)nav.setAttribute('aria-label','What’s New, '+count+' unread announcement'+(count===1?'':'s'));else nav.removeAttribute('aria-label');
            }});
            const banner=document.getElementById('campaign-unread-banner'),message=document.getElementById('campaign-unread-message');
            if(banner&&message){{message.textContent=count===1?'You have 1 new announcement.':'You have '+count+' new announcements.';banner.classList.toggle('hidden',!count);}}
        }}
        refreshCampaignUnread().catch(()=>{{}});
        setInterval(()=>{{if(!document.hidden)refreshCampaignUnread().catch(()=>{{}});}},campaignStatusInterval);
        document.addEventListener('visibilitychange',()=>{{if(!document.hidden)refreshCampaignUnread().catch(()=>{{}});}});
        function openPortalModal(id) {{ const modal=document.getElementById(id); if(!modal) return; modal.classList.remove('hidden'); document.body.style.overflow='hidden'; activePortalModal=id; const panel=modal.querySelector('[tabindex]'); if(panel) panel.focus(); }}
        function closePortalModal(id) {{ const modal=document.getElementById(id); if(!modal) return; modal.classList.add('hidden'); document.body.style.overflow=''; if(activePortalModal===id) activePortalModal=null; }}
        function closeOnBackdrop(event,id) {{ if(event.target===event.currentTarget) closePortalModal(id); }}
        document.addEventListener('keydown', event => {{ if(event.key==='Escape' && activePortalModal) closePortalModal(activePortalModal); }});
        function setPortalFeedback(id, message, ok) {{
            const el = document.getElementById(id);
            if (!el) return;
            el.textContent = message;
            el.classList.toggle('text-red-300', !ok);
            el.classList.toggle('text-emerald-300', ok);
            setTimeout(() => {{ el.textContent = ''; }}, 1800);
        }}
        async function copyPortalValue(value, successMessage, feedbackId) {{
            if (!value) {{
                setPortalFeedback(feedbackId, 'Nothing to copy', false);
                return;
            }}
            try {{
                await navigator.clipboard.writeText(value);
                setPortalFeedback(feedbackId, successMessage || 'Copied', true);
            }} catch (err) {{
                setPortalFeedback(feedbackId, 'Copy failed', false);
            }}
        }}
        function copySecretValue(elementId, successMessage, feedbackId) {{
            const el = document.getElementById(elementId);
            if (!el || !el.dataset.secret) {{
                setPortalFeedback(feedbackId, 'Token unavailable', false);
                return;
            }}
            copyPortalValue(el.dataset.secret, successMessage, feedbackId);
        }}
        function toggleSecret(elementId, button, feedbackId) {{
            const el = document.getElementById(elementId);
            if (!el || !el.dataset.secret) {{
                setPortalFeedback(feedbackId, 'Token unavailable', false);
                return;
            }}
            const visible = el.dataset.visible === 'true';
            el.textContent = visible ? el.dataset.masked : el.dataset.secret;
            el.dataset.visible = visible ? 'false' : 'true';
            if (button) button.textContent = visible ? 'Show' : 'Hide';
            setPortalFeedback(feedbackId, visible ? 'Token hidden' : 'Token shown', true);
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
    <div id="onboarding-modal" class="portal-modal hidden" role="dialog" aria-modal="true" aria-labelledby="onboarding-title"><div role="document" tabindex="-1" class="card modal-panel p-5 sm:p-7"><p id="onboarding-progress" role="status" class="text-sm text-purple-300"></p><h2 id="onboarding-title" class="mt-3 text-2xl font-bold text-white"></h2><p id="onboarding-text" class="mt-3 text-gray-300 leading-6"></p><div class="mt-6 flex flex-wrap justify-between gap-2"><button id="onboarding-skip" type="button" class="touch-action">Skip tour</button><div class="flex gap-2"><button id="onboarding-back" type="button" class="touch-action">Back</button><button id="onboarding-next" type="button" class="compact-action">Next</button></div></div></div></div>
    <script src="/static/onboarding.js"></script>
    <div id="login-promotion-modal" class="campaign-modal-backdrop modal-backdrop hidden" role="dialog" aria-modal="true" aria-labelledby="login-promotion-title">
        <div role="document" tabindex="-1" class="campaign-modal-card modal-card p-5 sm:p-7">
            <div class="flex justify-end"><button type="button" data-popup-close class="touch-action" aria-label="Dismiss promotion">Close</button></div>
            <img id="login-promotion-image" class="campaign-modal-image hidden mt-2 rounded-xl" alt="">
            <h2 id="login-promotion-title" class="mt-4 text-2xl font-bold text-white"></h2>
            <p id="login-promotion-summary" class="mt-3 whitespace-pre-line text-gray-300"></p>
            <div class="campaign-modal-actions mt-6 flex flex-col gap-2 sm:flex-row sm:justify-end">
                <button id="login-promotion-details" type="button" class="touch-action">View details</button>
                <button id="login-promotion-primary" type="button" class="btn-primary hidden min-h-11 rounded-xl px-5 py-2.5 font-semibold text-white"></button>
            </div>
        </div>
    </div>
    <script src="/static/campaign-popup.js"></script>
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
        * { box-sizing: border-box; }
        html { width:100%; overflow-x:hidden; }
        body { font-family: 'Inter', sans-serif; background: #0a0a1a; overflow-x: hidden; overflow-y: auto; margin: 0; min-width:0; }
        .bg-grid {
            background-image: linear-gradient(rgba(139,92,246,0.04) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(139,92,246,0.04) 1px, transparent 1px);
            background-size: 60px 60px;
        }
        .glow-orb { position: absolute; border-radius: 50%; filter: blur(100px); opacity: 0.35; animation: float 8s ease-in-out infinite; pointer-events:none; }
        @keyframes float { 0%,100% { transform: translateY(0) scale(1); } 50% { transform: translateY(-30px) scale(1.05); } }
        @keyframes pulse-glow {
            0%, 100% { box-shadow: 0 0 20px rgba(139,92,246,0.3), 0 0 40px rgba(139,92,246,0.1); border-color: rgba(139,92,246,0.25); }
            50% { box-shadow: 0 0 35px rgba(139,92,246,0.5), 0 0 70px rgba(139,92,246,0.2); border-color: rgba(139,92,246,0.45); }
        }
        .logo-badge {
            animation: logo-pulse 3s ease-in-out infinite;
        }
        @keyframes pulse-glow { 0%,100% { box-shadow: 0 0 20px rgba(139,92,246,0.2); } 50% { box-shadow: 0 0 50px rgba(139,92,246,0.35), 0 0 100px rgba(139,92,246,0.1); } }
        @keyframes logo-pulse {
            0%, 100% { box-shadow: 0 0 20px rgba(139,92,246,0.5), 0 0 40px rgba(139,92,246,0.2); border-color: rgba(139,92,246,0.4); }
            50% { box-shadow: 0 0 40px rgba(139,92,246,0.8), 0 0 100px rgba(139,92,246,0.35); border-color: rgba(190,160,255,0.7); }
        }
        .card-glow { animation: pulse-glow 4s ease-in-out infinite; }
        .input-field { background: rgba(255,255,255,0.04); border: 1px solid rgba(139,92,246,0.2); transition: all 0.3s; color: #e2e8f0; font-size:16px; }
        .input-field:focus { border-color: #8b5cf6; box-shadow: 0 0 0 3px rgba(139,92,246,0.25); outline: none; }
        .btn-primary { background: linear-gradient(135deg, #8b5cf6, #6d28d9); transition: all 0.3s; box-shadow: 0 4px 20px rgba(139,92,246,0.3); }
        .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 8px 35px rgba(139,92,246,0.5); }
        .logo-float { animation: float 6s ease-in-out infinite; }
        @media (max-width: 768px) {
            body { min-height: 100dvh; padding-left:max(1rem, env(safe-area-inset-left)); padding-right:max(1rem, env(safe-area-inset-right)); }
            .glow-orb { display:none; }
            .login-shell { max-width: none; width: min(94vw, 28rem); }
            .login-logo { height: 72px !important; max-width: 112px !important; }
            .login-brand { margin-bottom: 1rem !important; animation: none; }
            .login-card { width:100%; padding: 1.25rem !important; border-radius: 1.25rem !important; }
            .input-field { font-size:16px !important; min-height:48px; }
            .btn-primary { width:100%; min-height:48px; }
        }
    </style>
</head>
<body class="min-h-screen flex items-center justify-center p-4 bg-grid relative" style="background:#0a0a1a; padding-top:max(1rem, env(safe-area-inset-top)); padding-bottom:max(1rem, env(safe-area-inset-bottom));">
    <div class="glow-orb w-96 h-96 bg-purple-600" style="top:-10%;left:-5%"></div>
    <div class="glow-orb w-80 h-80 bg-violet-700" style="bottom:-10%;right:-5%;animation-delay:-4s"></div>
    <div class="glow-orb w-64 h-64 bg-indigo-600" style="top:50%;left:60%;opacity:0.15;animation-delay:-2s"></div>

    <div class="login-shell relative z-10 w-full max-w-md">
        <div class="login-brand text-center mb-8 logo-float">
            <img src="/static/brand/burghscape-shield.svg" alt="Burghscape" class="login-logo" style="height:112px;width:auto;max-width:168px;object-fit:contain;display:block;margin:0 auto 12px">
            <h1 class="text-2xl font-bold text-white mt-3" style="letter-spacing:-0.5px">Burghscape</h1>
            <p class="text-xs text-purple-400 mt-1" style="letter-spacing:2px;text-transform:uppercase">Pty Ltd</p>
        </div>

        <div class="login-card bg-[#12122a]/85 backdrop-blur-xl rounded-2xl p-8 border border-purple-500/10 card-glow">
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

GETTING_STARTED_HTML = """<!DOCTYPE html>
<html lang="en" data-theme-enabled>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="/static/theme.js"></script>
    <title>Complete Setup - Burghscape Home Cloud</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root { color-scheme: dark; }
        * { box-sizing:border-box; }
        html { width:100%; overflow-x:hidden; }
        body { font-family: 'Inter', sans-serif; background:#030712; margin:0; overflow-x:hidden; min-width:0; }
        .bg-grid { background-color:#030712; background-image:radial-gradient(circle at 14% 0%, rgba(139,92,246,0.22), transparent 32%), radial-gradient(circle at 90% 12%, rgba(59,130,246,0.12), transparent 26%), linear-gradient(rgba(139,92,246,0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(139,92,246,0.035) 1px, transparent 1px); background-size:auto,auto,60px 60px,60px 60px; }
        .card { background:rgba(17,24,39,0.86); border:1px solid rgba(255,255,255,0.10); backdrop-filter:blur(16px); box-shadow:0 18px 45px rgba(0,0,0,0.24); }
        .brand-logo { height:40px; width:40px; object-fit:contain; display:block; flex-shrink:0; }
        .hero { position:relative; overflow:hidden; border-radius:28px; border:1px solid rgba(167,139,250,0.24); background:linear-gradient(135deg, rgba(17,24,39,0.92), rgba(49,46,129,0.48)); box-shadow:0 24px 70px rgba(0,0,0,0.35); }
        .hero:before { content:""; position:absolute; inset:-35% -20% auto auto; width:520px; height:520px; border-radius:999px; background:radial-gradient(circle, rgba(139,92,246,0.26), transparent 62%); pointer-events:none; }
        .pill { display:inline-flex; align-items:center; gap:7px; border-radius:999px; border:1px solid rgba(167,139,250,0.28); background:rgba(139,92,246,0.12); padding:7px 11px; color:#ddd6fe; font-size:12px; line-height:1; }
        .status-dot { width:9px; height:9px; border-radius:999px; display:inline-block; }
        .status-online { background:#34d399; box-shadow:0 0 12px rgba(52,211,153,0.56); }
        .status-pending { background:#fbbf24; box-shadow:0 0 12px rgba(251,191,36,0.42); }
        .btn-primary { display:inline-flex; align-items:center; justify-content:center; gap:8px; border-radius:14px; background:linear-gradient(135deg,#8b5cf6,#6d28d9); color:#fff; font-weight:700; padding:13px 18px; box-shadow:0 16px 38px rgba(109,40,217,0.26); transition:transform .2s ease, box-shadow .2s ease; }
        .btn-primary:hover { transform:translateY(-1px); box-shadow:0 20px 48px rgba(109,40,217,0.34); }
        .btn-secondary { display:inline-flex; align-items:center; justify-content:center; gap:8px; border-radius:14px; border:1px solid rgba(255,255,255,0.12); background:rgba(255,255,255,0.06); color:#e5e7eb; font-weight:650; padding:12px 16px; transition:background .2s ease, border-color .2s ease; }
        .btn-secondary:hover { background:rgba(255,255,255,0.10); border-color:rgba(167,139,250,0.34); }
        .btn-secondary:disabled { opacity:.45; cursor:not-allowed; }
        .copy-button { border-radius:10px; border:1px solid rgba(167,139,250,0.24); background:rgba(139,92,246,0.12); color:#ddd6fe; padding:8px 10px; font-size:12px; font-weight:700; transition:background .2s ease; }
        .copy-button:hover { background:rgba(139,92,246,0.22); }
        .copy-button:disabled { opacity:.45; cursor:not-allowed; }
        .copy-feedback { color:#34d399; font-size:12px; min-height:18px; }
        .stage-shell { display:grid; grid-template-columns:minmax(0, 285px) minmax(0, 1fr); gap:24px; }
        .stage-list { position:sticky; top:20px; align-self:start; }
        .stage-tab { width:100%; display:flex; align-items:center; gap:10px; text-align:left; border-radius:14px; border:1px solid transparent; color:#9ca3af; padding:10px 12px; transition:background .2s ease, color .2s ease, border-color .2s ease; }
        .stage-tab:hover { color:#fff; background:rgba(255,255,255,0.05); }
        .stage-tab.active { color:#fff; border-color:rgba(167,139,250,0.34); background:linear-gradient(135deg, rgba(139,92,246,0.22), rgba(109,40,217,0.10)); }
        .stage-tab.hidden { display:none; }
        .path-choice { text-align:left; border-radius:18px; border:1px solid rgba(255,255,255,0.10); background:rgba(255,255,255,0.045); padding:16px; transition:background .2s ease, border-color .2s ease, transform .2s ease; }
        .path-choice:hover { transform:translateY(-1px); background:rgba(255,255,255,0.07); border-color:rgba(167,139,250,0.28); }
        .path-choice.active { border-color:rgba(167,139,250,0.46); background:linear-gradient(135deg, rgba(139,92,246,0.20), rgba(14,165,233,0.08)); }
        .stage-number { width:28px; height:28px; display:inline-flex; align-items:center; justify-content:center; border-radius:999px; background:rgba(255,255,255,0.07); color:#d1d5db; font-size:12px; font-weight:800; }
        .stage-tab.active .stage-number { background:#8b5cf6; color:white; }
        .stage-panel { display:none; border-radius:24px; background:rgba(17,24,39,0.86); border:1px solid rgba(255,255,255,0.10); box-shadow:0 18px 45px rgba(0,0,0,0.22); }
        .stage-panel.active { display:block; animation:fadeIn .22s ease; }
        @keyframes fadeIn { from { opacity:0; transform:translateY(5px); } to { opacity:1; transform:translateY(0); } }
        .progress-track { height:10px; border-radius:999px; background:rgba(255,255,255,0.10); overflow:hidden; }
        .progress-fill { height:100%; width:0%; border-radius:999px; background:linear-gradient(90deg,#8b5cf6,#22d3ee); transition:width .25s ease; }
        .media-card { min-width:0; width:100%; min-height:260px; border-radius:20px; border:1px dashed rgba(167,139,250,0.32); background:linear-gradient(135deg, rgba(139,92,246,0.10), rgba(15,23,42,0.72)); display:flex; align-items:center; justify-content:center; text-align:center; padding:26px; overflow:hidden; }
        .media-card img { max-width:100%; border-radius:16px; border:1px solid rgba(255,255,255,0.10); box-shadow:0 18px 48px rgba(0,0,0,0.34); }
        .callout { border-radius:16px; padding:15px 16px; font-size:14px; line-height:1.6; }
        .callout strong { display:block; margin-bottom:3px; font-size:12px; letter-spacing:.12em; text-transform:uppercase; }
        .tip { background:rgba(139,92,246,0.10); border:1px solid rgba(167,139,250,0.24); color:#ddd6fe; }
        .note { background:rgba(14,165,233,0.10); border:1px solid rgba(56,189,248,0.22); color:#bae6fd; }
        .important { background:rgba(251,191,36,0.09); border:1px solid rgba(251,191,36,0.25); color:#fde68a; }
        .warning { background:rgba(248,113,113,0.10); border:1px solid rgba(248,113,113,0.25); color:#fecaca; }
        .data-field { border-radius:16px; border:1px solid rgba(255,255,255,0.10); background:rgba(255,255,255,0.05); padding:14px; }
        .field-value { overflow-wrap:anywhere; word-break:break-word; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; color:#ddd6fe; font-size:13px; min-width:0; }
        .mobile-card { border-radius:20px; border:1px solid rgba(255,255,255,0.10); background:rgba(255,255,255,0.045); padding:20px; }
        .completion-card { border-radius:18px; border:1px solid rgba(52,211,153,0.22); background:rgba(16,185,129,0.09); padding:16px; }
        .remote-url { word-break:break-all; color:#c4b5fd; }
        @media (max-width: 900px) { .stage-shell { grid-template-columns:1fr; } .stage-list { position:static; } .stage-nav { display:flex; overflow-x:auto; gap:8px; padding-bottom:6px; -webkit-overflow-scrolling:touch; } .stage-tab { min-width:170px; flex:0 0 auto; } }
        @media (max-width: 640px) { body { min-height:100dvh; } main { padding-left:max(1rem, env(safe-area-inset-left)); padding-right:max(1rem, env(safe-area-inset-right)); } .hero { border-radius:22px; } .hero h1 { font-size:2.25rem; } .stage-panel { border-radius:18px; } .stage-tab { min-width:145px; padding:9px; } .stage-number { width:24px; height:24px; } .media-card { min-height:210px; padding:18px; } .data-field .mt-2, .stage-panel .mt-5.flex { flex-wrap:wrap; } .copy-button, .btn-primary, .btn-secondary { min-height:44px; } .field-value { flex-basis:100%; font-size:12px; } }
    </style>
    <link rel="stylesheet" href="/static/theme.css">
</head>
<body class="bg-gray-950 text-gray-200 min-h-screen bg-grid">
    <nav class="card border-b border-white/10 px-4 md:px-6 py-4">
        <div class="max-w-7xl mx-auto flex items-center justify-between gap-4">
            <div class="flex min-w-0 items-center gap-3">
                <img src="/static/brand/burghscape-shield.svg" alt="Burghscape" class="brand-logo">
                <div class="min-w-0 leading-tight">
                    <div class="text-sm font-semibold text-white">Burghscape</div>
                    <div class="truncate text-xs uppercase tracking-[0.16em] text-purple-300">Home Cloud</div>
                </div>
                <span class="hidden lg:inline text-sm font-medium text-gray-400 truncate">__CLIENT_NAME__</span>
            </div>
            <div class="flex shrink-0 items-center gap-2 md:gap-4 text-sm">
                <a href="/portal" class="text-gray-400 hover:text-purple-400 transition text-xs md:text-sm">Dashboard</a>
                <a href="/portal/logout" class="text-gray-400 hover:text-purple-400 transition text-xs md:text-sm">Logout</a>
            </div>
        </div>
    </nav>

    <main class="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8">
        <section class="hero p-6 sm:p-8 lg:p-10 mb-6">
            <div class="relative grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-8 items-center">
                <div>
                    <span class="pill mb-5"><span class="status-dot __STATUS_DOT_CLASS__"></span>__INSTANCE_STATUS__</span>
                    <h1 class="text-4xl sm:text-5xl font-bold text-white tracking-tight">Burghscape Home Cloud</h1>
                    <p class="mt-4 text-xl sm:text-2xl text-gray-200 leading-snug">Let’s connect your Home Assistant system.</p>
                    <p class="mt-4 max-w-2xl text-gray-400 leading-relaxed">Complete these guided steps to activate secure remote access, monitoring, and mobile connectivity through your Burghscape Client Portal.</p>
                    <div class="mt-6 flex flex-wrap gap-3">
                        <a href="#setup" data-start-action class="btn-primary">__START_ACTION_LABEL__</a>
                        <a href="__REMOTE_URL__" target="_blank" rel="noopener" class="btn-secondary">Open Remote URL</a>
                    </div>
                </div>
                <div class="grid gap-3">
                    <div class="data-field"><div class="text-xs uppercase tracking-[0.16em] text-gray-500">Estimated setup time</div><div class="mt-1 text-lg font-semibold text-white">25-35 minutes</div></div>
                    <div class="data-field"><div class="text-xs uppercase tracking-[0.16em] text-gray-500">Connection status</div><div class="mt-1 font-semibold __STATUS_CLASS__">__INSTANCE_STATUS__</div></div>
                    <div class="data-field"><div class="text-xs uppercase tracking-[0.16em] text-gray-500">Customer Remote URL</div><div class="mt-2 flex items-center gap-2"><span class="field-value flex-1">__REMOTE_URL__</span><button class="copy-button" data-copy="__REMOTE_URL__">Copy</button></div></div>
                </div>
            </div>
        </section>

        <div id="copy-feedback" class="copy-feedback mb-3"></div>
        <section class="card rounded-3xl p-5 sm:p-6 mb-6" aria-label="Choose setup path">
            <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-4">
                <div>
                    <span class="pill mb-3">Setup path</span>
                    <h2 class="text-2xl font-bold text-white">Choose the path that matches your installation</h2>
                    <p class="mt-2 text-sm text-gray-400 max-w-3xl">New customers can follow every installation step. Existing maintenance or migrated customers whose system was already connected by Burghscape can skip the installation-only stages and continue with Remote URL and mobile setup.</p>
                </div>
                <button type="button" class="btn-secondary" data-path-reset>Change path anytime</button>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <button type="button" class="path-choice" data-path-choice="self"><span class="block text-lg font-semibold text-white">I am installing the Burghscape Agent</span><span class="mt-1 block text-sm text-gray-400">Use this if you are setting up Home Assistant, tokens, the repository, and the agent yourself.</span></button>
                <button type="button" class="path-choice" data-path-choice="connected"><span class="block text-lg font-semibold text-white">Burghscape already connected my system</span><span class="mt-1 block text-sm text-gray-400">Use this if Burghscape installed or migrated the agent for you. Continue with Remote URL and mobile app setup.</span></button>
            </div>
            <p id="path-feedback" class="copy-feedback mt-3"></p>
        </section>
        <section id="setup" class="stage-shell">
            <aside class="stage-list card rounded-3xl p-4">
                <div class="mb-4">
                    <div class="flex items-center justify-between gap-3 mb-2"><span class="text-sm font-semibold text-white">Setup progress</span><span id="progress-label" class="text-xs text-purple-300">0%</span></div>
                    <div class="progress-track"><div id="progress-fill" class="progress-fill"></div></div>
                </div>
                <div class="stage-nav" id="stage-nav">
                    <button class="stage-tab active" data-stage-target="0"><span class="stage-number">1</span><span>Welcome</span></button>
                    <button class="stage-tab" data-stage-target="1" data-path="self"><span class="stage-number">2</span><span>Create HA Token</span></button>
                    <button class="stage-tab" data-stage-target="2" data-path="self"><span class="stage-number">3</span><span>Subscription Token</span></button>
                    <button class="stage-tab" data-stage-target="3" data-path="self"><span class="stage-number">4</span><span>Install Agent</span></button>
                    <button class="stage-tab" data-stage-target="4" data-path="self"><span class="stage-number">5</span><span>Configure Agent</span></button>
                    <button class="stage-tab" data-stage-target="5" data-path="self"><span class="stage-number">6</span><span>Start Agent</span></button>
                    <button class="stage-tab" data-stage-target="6"><span class="stage-number">7</span><span>Remote Access</span></button>
                    <button class="stage-tab" data-stage-target="7"><span class="stage-number">8</span><span>Android</span></button>
                    <button class="stage-tab" data-stage-target="8"><span class="stage-number">9</span><span>iPhone / iPad</span></button>
                    <button class="stage-tab" data-stage-target="9"><span class="stage-number">10</span><span>Finish</span></button>
                </div>
            </aside>

            <div class="min-w-0">
                <article class="stage-panel active p-5 sm:p-7" data-stage="0">
                    <div class="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6">
                        <div>
                            <span class="pill mb-4">Welcome</span>
                            <h2 class="text-3xl font-bold text-white">Start with your Burghscape Client Portal</h2>
                            <p class="mt-3 text-gray-300 leading-relaxed">Your portal is the home base for setup, remote access, monitoring, and support.</p>
                            <ol class="mt-5 space-y-3 text-gray-300 list-decimal list-inside"><li>Keep this page open during setup.</li><li>Confirm your Burghscape Client Portal URL below.</li><li>Move through each stage and mark progress as you go.</li></ol>
                            <div class="mt-5 data-field"><div class="text-xs uppercase tracking-[0.16em] text-gray-500">Client Portal URL</div><div class="mt-2 flex items-center gap-2"><span class="field-value flex-1">__CLIENT_PORTAL_URL__</span><button class="copy-button" data-copy="__CLIENT_PORTAL_URL__">Copy</button></div></div>
                            <div class="callout tip mt-5"><strong>Burghscape Tip</strong>No router configuration is required. Burghscape performs the secure tunnel setup automatically after the Burghscape Agent connects.</div>
                        </div>
                        <div class="media-card" data-image="step1-client-portal-login.png"><div><div class="text-lg font-semibold text-white">Client Portal Login</div><p class="mt-2 text-sm text-gray-400">Placeholder for <code>step1-client-portal-login.png</code>. Show the Burghscape logo, email/password fields, and Sign In button.</p></div></div>
                    </div>
                </article>

                <article class="stage-panel p-5 sm:p-7" data-stage="1" data-path="self">
                    <div class="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6">
                        <div><span class="pill mb-4">New / self-install customers only</span><h2 class="text-3xl font-bold text-white">Create a Home Assistant Long-Lived Access Token</h2><p class="mt-3 text-gray-300 leading-relaxed">The Burghscape Agent uses this Home Assistant token to read system health from your own Home Assistant installation. It is different from your Burghscape Subscription Token.</p><ol class="mt-5 space-y-3 text-gray-300 list-decimal list-inside"><li>Open the Home Assistant user profile.</li><li>Open Security.</li><li>Find Long-lived access tokens.</li><li>Select Create token.</li><li>Name it Burghscape Agent.</li><li>Copy it immediately and keep it private.</li></ol><div class="callout important mt-5"><strong>Important</strong>Home Assistant displays a Long-Lived Access Token only once. Enter this token in the Burghscape Agent <code>ha_token</code> field. Existing migrated or maintenance clients should not create another token unless Burghscape specifically requests it.</div></div>
                        <div class="media-card" data-image="step2-generate-token.png"><div><div class="text-lg font-semibold text-white">Generate Home Assistant Token</div><p class="mt-2 text-sm text-gray-400">Placeholder for <code>step2-generate-token.png</code>. Show Profile → Security → Long-Lived Access Tokens and highlight Create Token.</p></div></div>
                    </div>
                </article>

                <article class="stage-panel p-5 sm:p-7" data-stage="2" data-path="self">
                    <div class="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6"><div><span class="pill mb-4">New / self-install customers only</span><h2 class="text-3xl font-bold text-white">Copy your Burghscape Subscription Token</h2><p class="mt-3 text-gray-300 leading-relaxed">This token links your Burghscape Agent to your Burghscape customer account. It is different from your Home Assistant Long-Lived Access Token.</p><div class="mt-5 data-field"><div class="text-xs uppercase tracking-[0.16em] text-gray-500">Subscription Token</div><div class="mt-2 flex items-center gap-2"><span class="field-value flex-1">Available under Your Burghscape Details</span><a href="/portal" class="copy-button">Open Dashboard</a></div><p class="mt-2 text-xs text-gray-500">__SUBSCRIPTION_TOKEN_NOTE__</p></div><div class="callout warning mt-5"><strong>Warning</strong>Do not email full tokens or paste them into support tickets. Use only the approved Burghscape Agent configuration field named <code>subscription_token</code>.</div></div><div class="media-card" data-image="step3-subscription-token.png"><div><div class="text-lg font-semibold text-white">Subscription Token Location</div><p class="mt-2 text-sm text-gray-400">Placeholder for <code>step3-subscription-token.png</code>. Show Your Burghscape Details, the masked Subscription Token, and the Show/Copy controls without exposing the full token.</p></div></div></div>
                </article>

                <article class="stage-panel p-5 sm:p-7" data-stage="3" data-path="self">
                    <div class="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6"><div><span class="pill mb-4">New / self-install customers only</span><h2 class="text-3xl font-bold text-white">Install the Burghscape Agent app</h2><p class="mt-3 text-gray-300 leading-relaxed">The Burghscape Agent runs inside Home Assistant and handles monitoring, secure remote access, and automatic onboarding.</p><ol class="mt-5 space-y-3 text-gray-300 list-decimal list-inside"><li>Open Home Assistant.</li><li>Go to Settings.</li><li>Open Apps.</li><li>Select Install app.</li><li>Open the three-dot menu in the top-right.</li><li>Select Repositories.</li><li>Select + Add.</li><li>Paste the Burghscape App Repository URL shown under Your Burghscape Details.</li><li>Confirm Add.</li><li>Find and install Burghscape Agent.</li></ol><div class="mt-5 data-field"><div class="text-xs uppercase tracking-[0.16em] text-gray-500">Burghscape App Repository URL</div><div class="mt-2 flex items-center gap-2"><span class="field-value flex-1">__ADDON_REPOSITORY_URL__</span><button class="copy-button" data-copy="__ADDON_REPOSITORY_URL__">Copy</button></div></div><div class="callout note mt-5"><strong>Note</strong>If Burghscape already connected your system, do not reinstall the Agent unless support asks you to.</div></div><div class="media-card" data-image="step4-install-agent.png"><div><div class="text-lg font-semibold text-white">Install Burghscape Agent</div><p class="mt-2 text-sm text-gray-400">Placeholder for <code>step4-install-agent.png</code>. Show Settings → Apps → Install app, the three-dot menu, Repositories, + Add, and the Burghscape Agent listing.</p></div></div></div>
                </article>

                <article class="stage-panel p-5 sm:p-7" data-stage="4" data-path="self">
                    <div class="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6"><div><span class="pill mb-4">New / self-install customers only</span><h2 class="text-3xl font-bold text-white">Enter the Burghscape Agent configuration</h2><p class="mt-3 text-gray-300 leading-relaxed">Enter these options in the order shown, then save before starting the Agent.</p><ol class="mt-5 space-y-3 text-gray-300 list-decimal list-inside"><li><code>platform_url</code>: <code>https://api.mybeacon.co.za</code></li><li><code>subscription_token</code>: copy from Your Burghscape Details in the Client Portal.</li><li><code>instance_name</code>: enter a recognizable site name.</li><li><code>heartbeat_interval</code>: <code>60</code>.</li><li>Enable <code>monitor_entities</code>, <code>monitor_disk</code>, <code>monitor_automations</code>, <code>monitor_updates</code>, and <code>monitor_backups</code>.</li><li>Leave <code>monitor_frigate</code> disabled. Frigate monitoring is an upcoming feature and should remain disabled until released.</li><li><code>report_days</code>: <code>30</code>.</li><li><code>ha_token</code>: paste the Home Assistant Long-Lived Access Token created earlier.</li><li>Select Save before starting the Agent.</li></ol><div class="callout warning mt-5"><strong>Troubleshooting</strong>If Save reports an error and <code>heartbeat_interval</code> changed to <code>59</code>, manually change it back to <code>60</code> and save again.</div></div><div class="media-card" data-image="step5-agent-config.png"><div><div class="text-lg font-semibold text-white">Configure Burghscape Agent</div><p class="mt-2 text-sm text-gray-400">Placeholder for <code>step5-agent-config.png</code>. Highlight platform_url, subscription_token, instance_name, heartbeat_interval, monitoring toggles, report_days, ha_token, and the Save button.</p></div></div></div>
                </article>

                <article class="stage-panel p-5 sm:p-7" data-stage="5" data-path="self">
                    <div class="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6"><div><span class="pill mb-4">Start Agent</span><h2 class="text-3xl font-bold text-white">Start the Burghscape Agent</h2><p class="mt-3 text-gray-300 leading-relaxed">Once started, the agent contacts Burghscape, receives your Remote URL, configures Home Assistant, and verifies the secure public connection.</p><ol class="mt-5 space-y-3 text-gray-300 list-decimal list-inside"><li>Enable Start on boot.</li><li>Start the add-on.</li><li>Open Logs and wait for successful connection messages.</li><li>Return to this portal after a few minutes.</li></ol><div class="callout tip mt-5"><strong>Burghscape Tip</strong>During first-time setup, it may take a few minutes before your Home Assistant appears online in the Burghscape Client Portal. This is normal while the secure connection is being established.</div></div><div class="media-card" data-image="step6-start-agent.png"><div><div class="text-lg font-semibold text-white">Start Agent</div><p class="mt-2 text-sm text-gray-400">Placeholder for <code>step6-start-agent.png</code>. Show Start on boot, Start button, and the add-on log panel.</p></div></div></div>
                </article>

                <article class="stage-panel p-5 sm:p-7" data-stage="6">
                    <div class="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6"><div><span class="pill mb-4">Remote Access</span><h2 class="text-3xl font-bold text-white">Confirm your Remote URL works</h2><p class="mt-3 text-gray-300 leading-relaxed">Your Remote URL opens Home Assistant through Burghscape’s secure managed tunnel. It is different from the Burghscape Client Portal login page.</p><ol class="mt-5 space-y-3 text-gray-300 list-decimal list-inside"><li>Copy your customer-specific Remote URL.</li><li>Open it in a browser.</li><li>Sign in with your Home Assistant username and password.</li><li>Use your Burghscape Client Portal username and password only at <code>__CLIENT_PORTAL_URL__</code>.</li><li>Return here when Home Assistant loads successfully.</li></ol><div class="mt-5 grid gap-3"><div class="data-field"><div class="text-xs uppercase tracking-[0.16em] text-gray-500">Client Portal login</div><div class="mt-2 flex items-center gap-2"><span class="field-value flex-1">__CLIENT_PORTAL_URL__</span><button class="copy-button" data-copy="__CLIENT_PORTAL_URL__">Copy</button></div></div><div class="data-field"><div class="text-xs uppercase tracking-[0.16em] text-gray-500">Remote URL for Home Assistant</div><div class="mt-2 flex items-center gap-2"><span class="field-value flex-1">__REMOTE_URL__</span><button class="copy-button" data-copy="__REMOTE_URL__">Copy</button><a href="__REMOTE_URL__" target="_blank" rel="noopener" class="btn-secondary">Open</a></div></div></div><div class="callout note mt-5"><strong>Note</strong>If the portal still shows Offline, wait a few minutes and refresh. The agent reports status automatically.</div></div><div class="media-card" data-image="step7-remote-url-working.png"><div><div class="text-lg font-semibold text-white">Remote URL Active</div><p class="mt-2 text-sm text-gray-400">Placeholder for <code>step7-remote-url-working.png</code>. Show Home Assistant loaded from the customer Remote URL, not the Burghscape Client Portal URL.</p></div></div></div>
                </article>

                <article class="stage-panel p-5 sm:p-7" data-stage="7">
                    <span class="pill mb-4">Android</span><h2 class="text-3xl font-bold text-white">Set up Android mobile access</h2><p class="mt-3 text-gray-300 leading-relaxed">Use the official Home Assistant Companion App and connect with your Burghscape Remote URL.</p><div class="mt-5 grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6"><div class="mobile-card"><h3 class="text-xl font-semibold text-white">Android Companion App</h3><p class="mt-1 text-sm text-purple-300">Google Play Store</p><ol class="mt-4 space-y-3 text-gray-300 list-decimal list-inside"><li>Install the official Home Assistant Companion App.</li><li>Open it.</li><li>Select Connect to my Home Assistant server.</li><li>Select Enter address manually when needed.</li><li>Enter your customer-specific Burghscape Remote URL.</li><li>Sign in with your Home Assistant credentials.</li><li>Choose a device name.</li><li>Enable notifications if wanted.</li><li>For reliable background presence, set Location to Allow all the time and allow Nearby devices when prompted.</li></ol><div class="mt-5 data-field"><div class="text-xs uppercase tracking-[0.16em] text-gray-500">Server address</div><div class="mt-2 flex items-center gap-2"><span class="field-value flex-1">__REMOTE_URL__</span><button class="copy-button" data-copy="__REMOTE_URL__">Copy</button></div></div></div><div class="media-card" data-image="step8-android-companion-app.png"><div><div class="text-lg font-semibold text-white">Android App Setup</div><p class="mt-2 text-sm text-gray-400">Placeholder for <code>step8-android-companion-app.png</code>. Show Connect to my Home Assistant server, Enter address manually, the Remote URL field, device name, notifications, Location, and Nearby devices prompts.</p></div></div></div>
                </article>

                <article class="stage-panel p-5 sm:p-7" data-stage="8">
                    <span class="pill mb-4">iPhone / iPad</span><h2 class="text-3xl font-bold text-white">Set up iPhone or iPad mobile access</h2><p class="mt-3 text-gray-300 leading-relaxed">Use the official Home Assistant Companion App for iOS or iPadOS and connect with your Burghscape Remote URL.</p><div class="mt-5 grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6"><div class="mobile-card"><h3 class="text-xl font-semibold text-white">iPhone / iPad Companion App</h3><p class="mt-1 text-sm text-purple-300">Apple App Store</p><ol class="mt-4 space-y-3 text-gray-300 list-decimal list-inside"><li>Install the official Home Assistant Companion App.</li><li>Open it.</li><li>Select Connect to my Home Assistant server.</li><li>Select Enter address manually when needed.</li><li>Enter your customer-specific Burghscape Remote URL.</li><li>Sign in with Home Assistant credentials.</li><li>Choose a device name.</li><li>Enable notifications if wanted.</li><li>For full presence functionality, choose Allow While Using the App initially, then choose Allow Always when subsequently prompted.</li><li>Critical Notifications are optional and may bypass silent or Focus modes.</li></ol><div class="mt-5 data-field"><div class="text-xs uppercase tracking-[0.16em] text-gray-500">Server address</div><div class="mt-2 flex items-center gap-2"><span class="field-value flex-1">__REMOTE_URL__</span><button class="copy-button" data-copy="__REMOTE_URL__">Copy</button></div></div></div><div class="media-card" data-image="step9-ios-companion-app.png"><div><div class="text-lg font-semibold text-white">iPhone / iPad App Setup</div><p class="mt-2 text-sm text-gray-400">Placeholder for <code>step9-ios-companion-app.png</code>. Show Connect to my Home Assistant server, Enter address manually, the Remote URL field, device name, notifications, Allow While Using the App, Allow Always, and Critical Notifications prompts.</p></div></div></div>
                </article>

                <article class="stage-panel p-5 sm:p-7" data-stage="9">
                    <span class="pill mb-4">Finish</span><h2 class="text-4xl font-bold text-white">You’re Connected</h2><p class="mt-3 text-gray-300 leading-relaxed">Your Burghscape Home Cloud setup is complete when the agent is online, remote access opens Home Assistant, and monitoring is active.</p><div class="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4"><div class="completion-card"><div class="text-sm text-emerald-200">Agent status</div><div class="mt-1 font-semibold text-white">__INSTANCE_STATUS__</div></div><div class="completion-card"><div class="text-sm text-emerald-200">Remote access status</div><div class="mt-1 font-semibold text-white">Use __REMOTE_URL__</div></div><div class="completion-card"><div class="text-sm text-emerald-200">Monitoring status</div><div class="mt-1 font-semibold text-white">Reports automatically after the agent connects</div></div><div class="completion-card"><div class="text-sm text-emerald-200">Mobile access</div><div class="mt-1 font-semibold text-white">Use the same Remote URL in the app</div></div></div><div class="mt-6 flex flex-wrap gap-3"><a href="/portal" class="btn-primary">Go to Dashboard</a><button type="button" class="btn-secondary" onclick="fetch('/api/portal/onboarding/replay',{method:'POST',credentials:'include'}).then(function(r){if(!r.ok)throw new Error();window.location.href='/portal'})">Replay portal tour</button><a href="__REMOTE_URL__" target="_blank" rel="noopener" class="btn-secondary">Open Home Assistant</a></div><div class="callout tip mt-5"><strong>Burghscape Tip</strong>Keep your Burghscape Remote URL bookmarked. It is the address you will use for browser and mobile access.</div>
                </article>

                <div class="mt-5 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                    <button id="prev-stage" class="btn-secondary" type="button">Previous</button>
                    <button id="mark-stage" class="btn-secondary" type="button">Mark this stage complete</button>
                    <button id="next-stage" class="btn-primary" type="button">Next</button>
                </div>
            </div>
        </section>
    </main>

    <script>
        (function() {
            const stageCount = 10;
            const storageKey = 'burghscape-onboarding-progress-__CLIENT_ID__';
            const pathKey = storageKey + '-setup-path';
            let setupPath = localStorage.getItem(pathKey) || 'self';
            let current = Math.min(stageCount - 1, Math.max(0, parseInt(localStorage.getItem(storageKey + '-current') || '0', 10)));
            let completed = new Set(JSON.parse(localStorage.getItem(storageKey) || '[]'));
            const panels = Array.from(document.querySelectorAll('[data-stage]'));
            const tabs = Array.from(document.querySelectorAll('[data-stage-target]'));
            const pathButtons = Array.from(document.querySelectorAll('[data-path-choice]'));
            const pathFeedback = document.getElementById('path-feedback');
            const fill = document.getElementById('progress-fill');
            const label = document.getElementById('progress-label');
            const prev = document.getElementById('prev-stage');
            const next = document.getElementById('next-stage');
            const mark = document.getElementById('mark-stage');

            function stageAllowed(index) {
                const panel = panels[index];
                return !panel || panel.dataset.path !== 'self' || setupPath === 'self';
            }
            function firstAllowed() {
                for (let i = 0; i < stageCount; i += 1) if (stageAllowed(i)) return i;
                return 0;
            }
            function nextAllowedIndex(from, direction) {
                let index = from + direction;
                while (index >= 0 && index < stageCount) {
                    if (stageAllowed(index)) return index;
                    index += direction;
                }
                return from;
            }
            function visibleCompletedCount() {
                return Array.from(completed).filter((index) => stageAllowed(index)).length;
            }
            function visibleStageCount() {
                return panels.filter((_, index) => stageAllowed(index)).length || stageCount;
            }
            function save() {
                localStorage.setItem(storageKey, JSON.stringify(Array.from(completed)));
                localStorage.setItem(storageKey + '-current', String(current));
                localStorage.setItem(pathKey, setupPath);
            }
            function render() {
                if (!stageAllowed(current)) current = setupPath === 'connected' ? 6 : firstAllowed();
                panels.forEach((panel, index) => panel.classList.toggle('active', index === current && stageAllowed(index)));
                tabs.forEach((tab, index) => {
                    const allowed = stageAllowed(index);
                    tab.classList.toggle('hidden', !allowed);
                    tab.classList.toggle('active', allowed && index === current);
                    const number = tab.querySelector('.stage-number');
                    if (number) number.textContent = completed.has(index) ? '✓' : String(index + 1);
                });
                pathButtons.forEach((button) => button.classList.toggle('active', button.dataset.pathChoice === setupPath));
                const percent = Math.round((visibleCompletedCount() / visibleStageCount()) * 100);
                fill.style.width = percent + '%';
                label.textContent = percent + '%';
                prev.disabled = current === firstAllowed();
                next.textContent = nextAllowedIndex(current, 1) === current ? 'Finish' : 'Next';
                mark.textContent = completed.has(current) ? 'Stage complete' : 'Mark this stage complete';
                mark.disabled = completed.has(current);
                tabs[current]?.scrollIntoView({block:'nearest', inline:'nearest'});
            }
            function go(index) {
                const target = Math.min(stageCount - 1, Math.max(0, index));
                current = stageAllowed(target) ? target : (target > current ? nextAllowedIndex(current, 1) : nextAllowedIndex(current, -1));
                save(); render();
            }
            tabs.forEach((tab) => tab.addEventListener('click', () => go(parseInt(tab.dataset.stageTarget, 10))));
            pathButtons.forEach((button) => button.addEventListener('click', () => {
                setupPath = button.dataset.pathChoice;
                if (setupPath === 'connected' && current < 6) current = 6;
                if (pathFeedback) pathFeedback.textContent = setupPath === 'connected' ? 'Installation-only stages are collapsed. Continue with Remote URL and mobile setup.' : 'Full self-install setup path selected.';
                save(); render();
            }));
            document.querySelector('[data-path-reset]')?.addEventListener('click', () => {
                setupPath = 'self';
                if (pathFeedback) pathFeedback.textContent = 'Full self-install setup path selected.';
                save(); render();
            });
            prev.addEventListener('click', () => go(nextAllowedIndex(current, -1)));
            next.addEventListener('click', () => {
                completed.add(current);
                current = nextAllowedIndex(current, 1);
                save(); render();
            });
            mark.addEventListener('click', () => { completed.add(current); save(); render(); });
            document.querySelectorAll('[data-start-action]').forEach((el) => el.addEventListener('click', () => setTimeout(() => go(current), 0)));
            document.querySelectorAll('[data-copy]').forEach((button) => {
                button.addEventListener('click', async () => {
                    const value = button.getAttribute('data-copy');
                    try {
                        await navigator.clipboard.writeText(value);
                        const previous = button.textContent;
                        button.textContent = 'Copied';
                        const feedback = document.getElementById('copy-feedback');
                        if (feedback) feedback.textContent = 'Copied successfully';
                        setTimeout(() => { button.textContent = previous; if (feedback) feedback.textContent = ''; }, 1600);
                    } catch (err) {
                        button.textContent = 'Copy failed';
                        const feedback = document.getElementById('copy-feedback');
                        if (feedback) feedback.textContent = 'Copy failed';
                    }
                });
            });
            document.querySelectorAll('.media-card[data-image]').forEach((card) => {
                const filename = card.getAttribute('data-image');
                const img = new Image();
                img.onload = () => { card.innerHTML = ''; img.alt = card.textContent || filename; card.appendChild(img); };
                img.onerror = () => {};
                img.src = '/static/docs/onboarding/' + filename;
            });
            render();
        })();
    </script>
</body>
</html>
"""

CHANGE_PASSWORD_HTML="""<!DOCTYPE html>
<html lang="en" data-theme-enabled>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="/static/theme.js"></script>
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
    <link rel="stylesheet" href="/static/theme.css">
</head>
<body class="min-h-screen flex items-center justify-center p-4 bg-grid relative" style="background:#0a0a1a">
    <div class="glow-orb w-96 h-96 bg-purple-600" style="top:-10%;left:-5%"></div>
    <div class="glow-orb w-80 h-80 bg-violet-700" style="bottom:-10%;right:-5%;animation-delay:-4s"></div>

    <div class="relative z-10 w-full max-w-md">
        <div class="text-center mb-8 logo-float">
            <img src="/static/brand/burghscape-shield.svg" alt="Burghscape" style="height:112px;width:auto;max-width:168px;object-fit:contain;display:block;margin:0 auto 12px">
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


@router.get("/api/portal/backups")
async def portal_backups(request: Request):
    """Return backup records for the logged-in client."""
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
        from models import Backup
        from sqlalchemy import desc
        bresults = await db.execute(
            select(Backup).where(Backup.client_id == user.client_id, Backup.status == "completed")
            .order_by(desc(Backup.started_at))
            .limit(20)
        )
        candidates = bresults.scalars().all()
        client = (await db.execute(select(Client).where(Client.id == user.client_id))).scalars().first()
        backups = [b for b in candidates if client and await is_customer_backup_available(b, client)]
        return {
            "backups": [{
                "id": b.id,
                "filename": b.filename or ("backup_" + str(b.id) + ".tar.gz"),
                "size_bytes": b.size_bytes or 0,
                "status": b.status or "unknown",
                "started_at": b.started_at.isoformat() if b.started_at else None,
                "completed_at": b.completed_at.isoformat() if b.completed_at else None,
                "download_url": ("/api/portal/backups/download/" + str(b.id)) if b.status == "completed" else None,
            } for b in backups]
        }


from fastapi.responses import FileResponse
from models import Backup
from sqlalchemy import desc


@router.get("/api/portal/backups/download/{backup_id}")
async def portal_backup_download(backup_id: int, request: Request):
    """Download a completed backup owned by the logged-in client."""
    token = request.cookies.get("portal_token", "")
    if not token:
        raise HTTPException(status_code=401)
    async with async_session() as db:
        user_id = portal_sessions.get(token)
        if not user_id:
            raise HTTPException(status_code=401)
        user = (await db.execute(select(ClientUser).where(ClientUser.id == user_id))).scalars().first()
        if not user or not user.is_active:
            raise HTTPException(status_code=401)
        backup = (await db.execute(
            select(Backup).where(Backup.id == backup_id, Backup.client_id == user.client_id)
        )).scalars().first()
        if not backup:
            raise HTTPException(status_code=404, detail="Backup not found")
        client = (await db.execute(select(Client).where(Client.id == user.client_id))).scalars().first()
        if not client:
            raise HTTPException(status_code=404, detail="Backup not found")
        instance = (await db.execute(select(HomeAssistantInstance).where(HomeAssistantInstance.client_id == client.id))).scalars().first()
        return await build_backup_file_response(backup, client, meaningful_backup_filename(backup, client, instance.name if instance else client.name))


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
        
        logo_svg = """<img src="/static/brand/burghscape-shield.svg" alt="Burghscape" style="height:50px;width:auto;max-width:84px;object-fit:contain;vertical-align:middle;margin-right:12px;">"""

        report_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>System Report - {client.name}</title>
<style>
@page {{ margin: 20mm; }}
body {{ font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #1e293b; line-height: 1.5; }}
.header {{ display: flex; align-items: center; gap: 16px; border-bottom: 3px solid #7c3aed; padding-bottom: 16px; margin-bottom: 10px; }}
.header-text h1 {{ margin: 0; color: #1e293b; font-size: 24px; }}
.header-text p {{ margin: 2px 0 0; color: #7c3aed; font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase; }}
h2 {{ color: #6d28d9; margin-top: 28px; margin-bottom: 12px; font-size: 16px; border-left: 4px solid #7c3aed; padding-left: 10px; }}
.meta {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }}
th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #e2e8f0; }}
th {{ background: #f8fafc; font-weight: 600; color: #475569; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
tr:nth-child(even) {{ background: #fafafa; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin: 16px 0; }}
.card {{ background: #faf5ff; border: 1px solid #e9d5ff; border-radius: 8px; padding: 14px; text-align: center; }}
.card h3 {{ margin: 0 0 4px; color: #7c3aed; font-size: 22px; }}
.card p {{ margin: 0; color: #64748b; font-size: 11px; }}
.status {{ display: inline-block; padding: 3px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; }}
.status-online {{ background: #dcfce7; color: #166534; }}
.status-offline {{ background: #fee2e2; color: #991b1b; }}
ul {{ padding-left: 20px; }}
li {{ margin: 4px 0; font-size: 13px; }}
.footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8; text-align: center; }}
@media print {{ body {{ margin: 0; padding: 0; }} .no-print {{ display: none; }} }}
</style></head>
<body>
<div class="no-print" style="text-align:right;margin-bottom:20px;">
<button onclick="window.print()" style="background:#7c3aed;color:white;border:none;padding:10px 24px;border-radius:8px;cursor:pointer;font-size:14px;font-weight:600;">Print / Save PDF</button>
</div>
<div class="header">
    {logo_svg}
    <div class="header-text">
        <h1>Burghscape System Report</h1>
        <p>Pty Ltd  |  Smart Home Management Platform</p>
    </div>
</div>
<p class="meta">Generated: {now} SAST  |  Client: {client.name}  |  Confidential</p>

<div class="grid">
<div class="card"><h3>{instance.ha_version if instance else 'N/A'}</h3><p>HA Version</p></div>
<div class="card"><h3>{'Online' if instance and instance.is_online else 'Offline'}</h3><p>System Status</p></div>
<div class="card"><h3>{instance.entities_count if instance else 0}</h3><p>Entities</p></div>
<div class="card"><h3>{instance.automations_count if instance else 0}</h3><p>Automations</p></div>
<div class="card"><h3>{len(addons_list)}</h3><p>Add-ons</p></div>
<div class="card"><h3>{len(integrations_list)}</h3><p>Integrations</p></div>
</div>

<h2>Storage</h2>
<p>{disk_info}</p>

<h2>Add-ons ({len(addons_list)})</h2>
<table><tr><th>Name</th><th>Version</th><th>State</th></tr>{addons_html}</table>

<h2>Integrations ({len(integrations_list)})</h2>
<table><tr><th>Integration Name</th></tr>{integrations_html}</table>

<h2>Updates Available ({len(updates_list)})</h2>
<ul>{updates_html}</ul>

<h2>📋 Notes</h2>
<p style="font-size:13px;color:#666;">This report is auto-generated by Burghscape Pty Ltd's monitoring system. For support, contact support@mybeacon.co.za</p>
</body></html>"""
        
        # Generate PDF
        from weasyprint import HTML as WHTML
        from io import BytesIO
        pdf_buffer = BytesIO()
        WHTML(string=report_html).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        
        return Response(
            content=pdf_buffer.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="burghscape-report-{client.subdomain}-{now.replace(":", "-")}.pdf"'
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



@router.get("/portal/getting-started", response_class=HTMLResponse)
async def portal_getting_started(request: Request):
    """Authenticated Getting Started guide for client onboarding."""
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

        if user.force_password_change:
            return HTMLResponse(status_code=302, headers={"Location": "/portal/change-password"})

        client_result = await db.execute(select(Client).where(Client.id == user.client_id))
        client = client_result.scalars().first()
        if not client:
            return HTMLResponse(status_code=302, headers={"Location": "/portal/login"})

        inst_result = await db.execute(
            select(HomeAssistantInstance).where(
                HomeAssistantInstance.client_id == client.id
            ).order_by(HomeAssistantInstance.last_seen.desc())
        )
        instance = inst_result.scalars().first()

        remote_url = f"https://{client.subdomain}.mybeacon.co.za"
        client_portal_url = "https://client.mybeacon.co.za/portal/login"
        online = bool(instance and instance.is_online)
        status_text = "Online" if online else "Setup incomplete"
        status_class = "text-emerald-300" if online else "text-amber-300"
        status_dot_class = "status-online" if online else "status-pending"
        start_action_label = "Continue Setup" if not online else "Review Setup"
        subscription_note = "Your Burghscape Subscription Token is masked by default under Your Burghscape Details on the dashboard. Use Show only when you are ready to paste it into the Agent configuration."

        replacements = {
            "__CLIENT_ID__": str(client.id),
            "__CLIENT_NAME__": escape(client.name or "Client", quote=True),
            "__USER_NAME__": escape(user.name or client.name or "there", quote=True),
            "__REMOTE_URL__": escape(remote_url, quote=True),
            "__CLIENT_PORTAL_URL__": escape(client_portal_url, quote=True),
            "__INSTANCE_STATUS__": escape(status_text, quote=True),
            "__STATUS_CLASS__": status_class,
            "__STATUS_DOT_CLASS__": status_dot_class,
            "__START_ACTION_LABEL__": start_action_label,
            "__SUBSCRIPTION_TOKEN_NOTE__": escape(subscription_note, quote=True),
            "__ADDON_REPOSITORY_URL__": escape(ADDON_REPOSITORY_URL, quote=True),
        }
        html = GETTING_STARTED_HTML
        for key, value in replacements.items():
            html = html.replace(key, value)
        return html


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

        token_result = await db.execute(
            select(SubscriptionToken).where(
                SubscriptionToken.client_id == client.id,
                SubscriptionToken.is_active == True
            ).order_by(SubscriptionToken.created_at.desc())
        )
        active_subscription_token = token_result.scalars().first()
        subscription_token_secret = active_subscription_token.token if active_subscription_token else ""
        subscription_token_masked = "••••••••••••••••" if subscription_token_secret else "Not available"
        subscription_token_disabled = "" if subscription_token_secret else "disabled"
        remote_url = f"https://{client.subdomain}.mybeacon.co.za"
        client_portal_url = "https://client.mybeacon.co.za/portal/login"

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
            ).order_by(SupportTicket.created_at.desc())
        )
        all_tickets = tickets_result.scalars().all()
        tickets = all_tickets[:10]

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
            safe_title = escape(t.title or "Untitled ticket")
            safe_priority = escape(t.priority or "normal")
            safe_status = escape(t.status or "open")
            resolution_html = f'<div class="mt-2 border-t border-white/10 pt-2"><span class="text-xs text-gray-500">Resolution</span><p class="mt-1 whitespace-pre-wrap text-sm text-gray-300">{escape(t.resolution)}</p></div>' if t.resolution else ""
            tickets_html += f'<div class="bg-gray-900 rounded-lg p-3"><div class="flex items-center justify-between"><span class="font-medium text-sm">{safe_title}</span><div class="flex gap-2"><span class="text-xs px-2 py-0.5 rounded-full {priority_colors.get(t.priority, "bg-gray-700 text-gray-400")}">{safe_priority}</span><span class="text-xs px-2 py-0.5 rounded-full {status_colors.get(t.status, "bg-gray-700 text-gray-400")}">{safe_status}</span></div></div><p class="text-xs text-gray-400 mt-1">{t.hours_used}h used • {created}</p>{resolution_html}</div>'

        if not tickets:
            tickets_html = '<p class="text-gray-500 text-sm">No tickets yet.</p>'
        open_ticket_count = sum(1 for ticket in tickets if ticket.status in ("open", "in_progress"))
        latest_ticket_status = tickets[0].status.replace("_", " ").title() if tickets else "No tickets"

        # Build users HTML
        users_html = ""
        for u in users:
            users_html += f'<div class="flex items-center justify-between bg-gray-900 rounded-lg p-3"><div><p class="text-sm font-medium">{u.name}</p><p class="text-xs text-gray-400">{u.email}</p></div><button onclick="removeUser({u.id})" class="text-red-400 hover:text-red-300 text-xs">Remove</button></div>'

        if not users:
            users_html = '<p class="text-gray-500 text-sm">No users yet.</p>'

        support_hours = calculate_support_hours(client.monthly_hours_included, (ticket.hours_used for ticket in all_tickets))
        hours_included = format_hours(support_hours["included"])
        hours_logged = format_hours(support_hours["logged"])
        hours_billable = format_hours(support_hours["potentially_billable"])
        support_remaining_html = ""
        if support_hours["included"] > 0:
            support_remaining_html = '<div class="metric-tile"><div class="text-gray-500">Remaining included support</div><div class="text-white mt-1">{}h</div></div>'.format(format_hours(support_hours["remaining"]))
        tier_value = client.tier.value if hasattr(client.tier, "value") else str(client.tier or "")
        support_ticket_notice_html = support_ticket_notice(tier_value)
        online = instance.is_online if instance else False
        if online:
            onboarding_banner_html = ""
            setup_nav_label = "Getting Started"
            setup_nav_class = "text-gray-400 hover:text-purple-400 transition nav-link text-xs md:text-sm"
        else:
            onboarding_banner_html = """
        <div class="mb-6 rounded-3xl border border-amber-400/25 bg-gradient-to-br from-amber-500/12 via-purple-500/10 to-gray-900/80 p-5 sm:p-6 shadow-2xl shadow-black/20">
            <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div class="min-w-0">
                    <div class="inline-flex items-center gap-2 rounded-full border border-amber-300/25 bg-amber-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-amber-200">Setup incomplete</div>
                    <h2 class="mt-3 text-2xl font-bold text-white">Complete your Burghscape Home Cloud setup</h2>
                    <p class="mt-2 max-w-3xl text-sm leading-6 text-gray-300">Your Home Assistant instance is not online in the Burghscape Client Portal yet. Follow the guided setup to connect the Burghscape Agent and activate your Remote URL.</p>
                </div>
                <a href="/portal/getting-started" class="inline-flex shrink-0 items-center justify-center rounded-xl bg-gradient-to-r from-purple-600 to-violet-700 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-purple-500/20 transition hover:from-purple-500 hover:to-violet-600">Complete Setup</a>
            </div>
        </div>"""
            setup_nav_label = "Complete Setup"
            setup_nav_class = "rounded-full border border-amber-300/25 bg-amber-400/10 px-3 py-1.5 text-amber-200 hover:bg-amber-400/15 transition nav-link text-xs md:text-sm font-semibold"

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
        <div class="card portal-card p-5 sm:p-6 min-w-0">
            <div class="info-row mb-4">
                <h2 class="text-lg font-semibold text-white">Home Assistant</h2>
                <span class="text-xs bg-purple-500/20 text-purple-300 px-3 py-1 rounded-full">Version {latest_ha_version}</span>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <a href="https://www.home-assistant.io/blog/categories/release-notes/" target="_blank" rel="noopener"
                   class="portal-action">
                    <span class="block text-sm font-semibold text-white">Release Notes</span>
                    <span class="portal-action-text mt-1 block text-xs text-gray-400">Monthly Home Assistant updates</span>
                </a>
                <a href="https://www.home-assistant.io/blog/categories/breaking-changes/" target="_blank" rel="noopener"
                   class="portal-action">
                    <span class="block text-sm font-semibold text-white">Breaking Changes</span>
                    <span class="portal-action-text mt-1 block text-xs text-gray-400">Compatibility notes to review</span>
                </a>
            </div>
        </div>'''


        # Backup status (from agent heartbeat)
        backup_enabled = False
        last_backup_str = "Unavailable"
        next_backup_str = "Unknown"
        backup_size_str = ""
        native_automatic_status = "Unknown"
        last_native_automatic = "Unknown"
        local_backup_count = "Unavailable"
        backup_encryption_status = "Unknown"
        # Check agent heartbeat for real-time backup status
        from routers.agent import agent_reports
        client_reports = {k: v for k, v in agent_reports.items() if v.get("client_id") == client.id}
        if client_reports:
            report = list(client_reports.values())[0]
            # Addon sends backup data in 'backup' key (or 'backup_status' for backward compat)
            bs = report.get("backup", {}) or report.get("backup_status", {})
            if bs:
                native_flag = bs.get("native_automatic_enabled")
                native_automatic_status = "Enabled" if native_flag is True else "Disabled" if native_flag is False else "Unknown"
                last_native_automatic = bs.get("last_native_automatic_backup") or "Unknown"
                next_backup_str = bs.get("next_native_automatic_backup") or "Unknown"
                local_backup_count = str(bs.get("file_count")) if bs.get("file_count") is not None else "Unavailable"
                encryption_flag = bs.get("encryption_enabled")
                backup_encryption_status = "Enabled — key managed by customer in Home Assistant" if encryption_flag is True else "Disabled" if encryption_flag is False else "Unknown"
            if bs and bs.get("enabled"):
                backup_enabled = True
                last_backup_raw = bs.get("last_backup") or bs.get("last_backup_timestamp")
                if last_backup_raw:
                    from datetime import datetime as _dt
                    # If it's a string like "2h ago" or "3d ago", use it directly
                    if isinstance(last_backup_raw, str) and (" ago" in last_backup_raw or "day" in last_backup_raw):
                        last_backup_str = last_backup_raw
                    # If it's a UTC timestamp (seconds since epoch)
                    elif isinstance(last_backup_raw, (int, float)):
                        delta = _dt.now() - _dt.fromtimestamp(last_backup_raw)
                        if delta.days > 0:
                            last_backup_str = "{} day(s) ago".format(delta.days)
                        elif delta.seconds > 3600:
                            last_backup_str = "{}h ago".format(delta.seconds // 3600)
                        else:
                            last_backup_str = "{}m ago".format(delta.seconds // 60)
                    # If it's an ISO datetime string
                    elif isinstance(last_backup_raw, str):
                        try:
                            dt = _dt.fromisoformat(last_backup_raw.replace("Z", "+00:00"))
                            delta = _dt.now().astimezone() - dt
                            if delta.days > 0:
                                last_backup_str = "{} day(s) ago".format(delta.days)
                            elif delta.seconds > 3600:
                                last_backup_str = "{}h ago".format(delta.seconds // 3600)
                            else:
                                last_backup_str = "{}m ago".format(delta.seconds // 60)
                        except (ValueError, TypeError):
                            last_backup_str = str(last_backup_raw)
                # If no relative time computed, check for a raw string
                if last_backup_str == "Not configured" and isinstance(last_backup_raw, str):
                    last_backup_str = last_backup_raw
            # Tailscale info
            ts = report.get("tailscale", {})
            tailscale_ip = ts.get("ip", "") if ts else ""
        else:
            tailscale_ip = ""
        # Fallback to DB fields
        if not backup_enabled and instance and instance.last_backup:
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

        if instance and instance.last_seen:
            from datetime import timezone as _timezone
            from zoneinfo import ZoneInfo
            report_time = instance.last_seen
            if report_time.tzinfo is None:
                report_time = report_time.replace(tzinfo=_timezone.utc)
            last_seen_display = report_time.astimezone(ZoneInfo("Africa/Johannesburg")).strftime("%d %b %Y, %H:%M")
        else:
            last_seen_display = "No report received"

        native_items = []
        if local_backup_count not in ("Unavailable", "0", 0, None):
            native_items.append('<p class="mt-2 text-sm text-gray-300"><strong class="text-white">{} detected</strong></p>'.format(escape(str(local_backup_count))))
        if last_backup_str not in ("Unavailable", "Unknown", "N/A", "Not configured", ""):
            native_items.append('<p class="mt-1 text-sm text-gray-400">Latest local backup: {}</p>'.format(escape(str(last_backup_str))))
        if not native_items:
            native_items.append('<p class="mt-2 text-sm text-gray-400">Detailed Home Assistant scheduling information is unavailable.</p>')
        native_backup_html = "".join(native_items)

        return PORTAL_HTML.format(
            onboarding_banner_html=onboarding_banner_html,
            setup_nav_label=setup_nav_label,
            setup_nav_class=setup_nav_class,
            addon_repository_url=escape(ADDON_REPOSITORY_URL, quote=True),
            subscription_token_secret=escape(subscription_token_secret, quote=True),
            subscription_token_masked=subscription_token_masked,
            subscription_token_disabled=subscription_token_disabled,
            remote_url=escape(remote_url, quote=True),
            client_portal_url=escape(client_portal_url, quote=True),
            instance_name=escape((instance.name or instance.hostname or client.name) if instance else client.name, quote=True),
            client_name=client.name,
            subdomain=client.subdomain,
            status_class="bg-green-900 text-green-300" if client.status.value == "active" else "bg-red-900 text-red-300",
            status_text=client.status.value.capitalize(),
            online_class="text-green-400" if online else "text-red-400",
            online_dot_class="status-online" if online else "status-offline",
            online_text_class="text-green-400" if online else "text-red-400",
            online_status="Online" if online else "Offline",
            ha_version=(instance.ha_version if instance else "N/A"),
            entity_count=(instance.entities_count if instance else 0),
            addon_count_display=(("?" if addon_count == 0 and integration_count > 0 else addon_count) if instance else 0),
            addon_count_suffix=" (pending)" if addon_count == 0 and integration_count > 0 else "",
            addon_count=addon_count,
            integration_count=(integration_count if instance else 0),
            user_name=user.name,
            db_size=db_size,
            uptime=uptime,
            updates_count=updates_html,
            updates_class="text-emerald-400",
            last_seen=last_seen_display,
            ha_news_section=ha_news_section,
            tickets_html=tickets_html,
            open_ticket_count=open_ticket_count,
            latest_ticket_status=latest_ticket_status,
            native_backup_html=native_backup_html,
            hours_included=hours_included,
            hours_logged=hours_logged,
            hours_billable=hours_billable,
            support_remaining_html=support_remaining_html,
            support_ticket_notice_html=support_ticket_notice_html,
            cpu_percent=(instance.cpu_usage_percent if instance else 0),
            memory_percent=(instance.memory_usage_percent if instance else 0),
            memory_used_gb=(instance.memory_used_gb if instance else 0),
            memory_total_gb=(instance.memory_total_gb if instance else 0),
            disk_percent=(instance.disk_usage_percent if instance else 0),
            disk_used_gb=(instance.disk_used_gb if instance else 0),
            disk_total_gb=(instance.disk_total_gb if instance else 0),
            backup_badge_class="bg-green-900 text-green-300" if backup_enabled else "bg-gray-700 text-gray-400",
            backup_badge_text="Local backups detected" if backup_enabled else "Native schedule unknown",
            last_backup_str=last_backup_str,
            next_backup_str=next_backup_str,
            native_automatic_status=native_automatic_status,
            last_native_automatic=last_native_automatic,
            local_backup_count=local_backup_count,
            backup_encryption_status=backup_encryption_status,

        )
