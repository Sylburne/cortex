"""Test uploading .docx with ASCII-only filename."""
import requests
import os
import shutil
import tempfile

docs_dir = r"C:\Projects\Projrct Aeon\Aeon Docs"
API_URL = "https://cortex-api-cpjo.onrender.com"
API_KEY = "2e363ff7efc9809e0ffd1fd2d32b439fc73a0929d8f15e7fbed56f5d2f624c3f"
NB_ID = "af63334d-e951-43fb-b067-0c30fc0d404c"

# Find smallest .docx
files = [(os.path.getsize(os.path.join(docs_dir, f)), f) for f in os.listdir(docs_dir) if f.endswith(".docx")]
files.sort()
smallest = files[0]

# Copy to temp with ASCII name
tmp = tempfile.mktemp(suffix=".docx")
shutil.copy(os.path.join(docs_dir, smallest[1]), tmp)

print(f"Original: {smallest[1].encode('ascii', 'replace').decode('ascii')}")
print(f"Size: {smallest[0]} bytes")
print(f"Testing with ASCII name: test_doc.docx")

headers = {"Authorization": f"Bearer {API_KEY}"}
with open(tmp, "rb") as f:
    resp = requests.post(
        f"{API_URL}/api/v1/notebooks/{NB_ID}/sources",
        headers=headers,
        files={"file": ("test_doc.docx", f)},
        data={"path": "/test"},
        timeout=120
    )

print(f"\nStatus: {resp.status_code}")
print(f"Body: {resp.text[:2000]}")

os.unlink(tmp)
