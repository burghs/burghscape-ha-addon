#!/usr/bin/env python3
import urllib.request, json

# Login
req = urllib.request.Request('http://localhost:8000/api/portal/auth/login',
    data=json.dumps({"email":"kenmyb@gmail.com","password":"Beacon2026!"}).encode(),
    headers={"Content-Type":"application/json"})
resp = urllib.request.urlopen(req)
token = json.loads(resp.read())["token"]
print(f"Token: {token[:20]}...")

# Access portal
req2 = urllib.request.Request('http://localhost:8000/portal')
req2.add_header('Cookie', f'portal_token={token}')
resp2 = urllib.request.urlopen(req2)
html = resp2.read().decode()
print(f"HTTP {resp2.status}")
print(f"Title: {[line for line in html.split(chr(10)) if '<title>' in line][0].strip()}")
print(f"Contains 'System Resources': {'System Resources' in html}")
print(f"Contains 'progress-bar': {'progress-bar' in html}")
