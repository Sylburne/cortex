#!/usr/bin/env python3
"""Quick deployment verification script.

Run after deploying to Render/Fly.io to confirm everything works:
    python verify_deploy.py https://cortex-api.onrender.com

Or locally:
    python verify_deploy.py http://localhost:8000
"""
import sys
import httpx
import json

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
API_KEY = "dev-api-key-change-me"  # Change to your deployed API_KEY

headers = {"Authorization": f"Bearer {API_KEY}"}


def test(name: str, method: str, path: str, expected_status: int = 200, body: dict = None):
    """Test one endpoint and print result."""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            r = httpx.get(url, headers=headers, timeout=10)
        else:
            r = httpx.post(url, headers=headers, json=body, timeout=10)
        
        status = "✓" if r.status_code == expected_status else "✗"
        print(f"{status} {name:30} {r.status_code} (expected {expected_status})")
        if r.status_code != expected_status:
            print(f"  Response: {r.text[:200]}")
        return r
    except Exception as e:
        print(f"✗ {name:30} ERROR: {e}")
        return None


print(f"\n{'='*60}")
print(f"Cortex Deployment Verification")
print(f"{'='*60}")
print(f"Base URL: {BASE_URL}\n")

# 1. Health check
print("--- Health Checks ---")
r = test("Root endpoint", "GET", "/")
if r and r.status_code == 200:
    data = r.json()
    print(f"  Service: {data.get('service')} | Version: {data.get('version')}")
    print(f"  Honcho: {'enabled' if data.get('honcho') else 'disabled'}")

test("Health endpoint", "GET", "/health")

# 2. Notebook CRUD
print("\n--- Notebook CRUD ---")
r = test("Create notebook", "POST", "/api/v1/notebooks", body={
    "name": "Test Notebook",
    "description": "Verification test"
})
notebook_id = r.json().get("id") if r and r.status_code == 200 else None

if notebook_id:
    test("List notebooks", "GET", "/api/v1/notebooks")
    test("Get notebook", "GET", f"/api/v1/notebooks/{notebook_id}")

# 3. Memory status
print("\n--- Honcho Memory ---")
r = test("Memory status", "GET", "/api/v1/memory/status")
if r and r.status_code == 200:
    data = r.json()
    print(f"  Enabled: {data.get('enabled')} | Workspace: {data.get('workspace_id')}")

# 4. Cleanup
if notebook_id:
    print("\n--- Cleanup ---")
    import httpx
    try:
        httpx.delete(f"{BASE_URL}/api/v1/notebooks/{notebook_id}", headers=headers, timeout=10)
        print("✓ Deleted test notebook")
    except:
        pass

print(f"\n{'='*60}")
print("Verification complete!")
print(f"{'='*60}\n")
