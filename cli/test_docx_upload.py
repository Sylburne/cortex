"""Test uploading a single .docx file to see the full error."""
import requests
import os

docs_dir = r"C:\Projects\Projrct Aeon\Aeon Docs"
API_URL = "https://cortex-api-cpjo.onrender.com"
API_KEY = "2e363ff7efc9809e0ffd1fd2d32b439fc73a0929d8f15e7fbed56f5d2f624c3f"
NB_ID = "af63334d-e951-43fb-b067-0c30fc0d404c"

# Find smallest .docx
files = [(os.path.getsize(os.path.join(docs_dir, f)), f) for f in os.listdir(docs_dir) if f.endswith(".docx")]
files.sort()
smallest = files[0]

# Use safe ASCII for printing
safe_name = smallest[1].encode("ascii", "replace").decode("ascii")
print(f"Smallest: {safe_name} ({smallest[0]} bytes)")

headers = {"Authorization": f"Bearer {API_KEY}"}
filepath = os.path.join(docs_dir, smallest[1])
with open(filepath, "rb") as f:
    resp = requests.post(
        f"{API_URL}/api/v1/notebooks/{NB_ID}/sources",
        headers=headers,
        files={"file": (smallest[1], f)},
        data={"path": "/aeon-docs"},
        timeout=120
    )

print(f"Status: {resp.status_code}")
print(f"Body: {resp.text[:1500]}")
