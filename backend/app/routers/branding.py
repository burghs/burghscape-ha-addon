"""Admin branding upload endpoint."""
from fastapi import APIRouter, UploadFile, File, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import os
import aiofiles

router = APIRouter()

BRAND_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "brand")
os.makedirs(BRAND_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".webp", ".ico"}


@router.get("/admin/branding", response_class=HTMLResponse)
async def branding_upload_page(request: Request):
    """Simple upload page for brand assets."""
    token = request.cookies.get("admin_token", "")
    if not token:
        return HTMLResponse(status_code=302, headers={"Location": "/login"})

    from admin_auth import verify_admin_token
    payload = verify_admin_token(token)
    if not payload:
        return HTMLResponse(status_code=302, headers={"Location": "/login"})

    # Check existing files
    files = []
    if os.path.exists(BRAND_DIR):
        files = os.listdir(BRAND_DIR)

    existing_html = ""
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in {".png", ".jpg", ".jpeg", ".svg", ".webp"}:
            existing_html += f'<div style="display:inline-block;margin:10px;text-align:center"><img src="/static/brand/{f}" style="max-height:80px;max-width:160px"><br><code>{f}</code></div>'

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Branding — Burghscape Admin</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>:root{{--bg:#0f172a;--card:#1e293b;--border:#334155;--text:#e2e8f0;--muted:#94a3b8;--accent:#8b5cf6}}</style>
</head><body class="bg-[#0f172a] text-gray-200 min-h-screen">
<div class="max-w-2xl mx-auto p-8">
    <h1 class="text-2xl font-bold mb-2">Branding & Logo</h1>
    <p class="text-gray-400 mb-6">Upload your company logo. Use <code>logo.png</code> or <code>logo.svg</code> for the main brand image.</p>

    <div class="bg-[#1e293b] rounded-xl p-6 border border-[#334155] mb-6">
        <h2 class="text-lg font-semibold mb-4">Current Brand Assets</h2>
        {f'<div class="flex flex-wrap gap-4">{existing_html}</div>' if existing_html else '<p class="text-gray-500">No brand assets uploaded yet.</p>'}
    </div>

    <div class="bg-[#1e293b] rounded-xl p-6 border border-[#334155]">
        <h2 class="text-lg font-semibold mb-4">Upload New Image</h2>
        <form id="upload-form" class="space-y-4">
            <input type="file" id="file-input" accept="image/*" class="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-purple-600 file:text-white file:font-medium hover:file:bg-purple-500 cursor-pointer">
            <button type="submit" class="bg-purple-600 hover:bg-purple-500 text-white px-6 py-2 rounded-lg font-medium">Upload</button>
        </form>
        <p id="result" class="mt-4 text-sm"></p>
    </div>

    <div class="mt-6 text-center">
        <a href="/" class="text-gray-500 hover:text-gray-300 text-sm">← Back to Dashboard</a>
    </div>
</div>
<script>
document.getElementById("upload-form").onsubmit = async (e) => {{
    e.preventDefault();
    const file = document.getElementById("file-input").files[0];
    if (!file) return alert("Select a file first");
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/admin/branding/upload", {{
        method: "POST",
        credentials: "include",
        body: form,
    }});
    const data = await res.json();
    document.getElementById("result").textContent = data.message || data.detail;
    if (res.ok) setTimeout(() => location.reload(), 1000);
}};
</script>
</body></html>"""


@router.post("/admin/branding/upload")
async def upload_branding(request: Request, file: UploadFile = File(...)):
    """Upload a brand asset."""
    token = request.cookies.get("admin_token", "")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    from admin_auth import verify_admin_token
    payload = verify_admin_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Validate extension
    filename = file.filename or "upload.png"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Enforce naming convention for logo
    if "logo" in filename.lower():
        filename = f"logo{ext}"

    filepath = os.path.join(BRAND_DIR, filename)

    async with aiofiles.open(filepath, "wb") as f:
        content = await file.read()
        await f.write(content)

    return {"message": f"Uploaded {filename} ({len(content)} bytes)", "filename": filename}


@router.get("/static/brand/{filename}")
async def serve_brand(filename: str):
    """Serve brand assets."""
    filepath = os.path.join(BRAND_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404)
    return FileResponse(filepath)
