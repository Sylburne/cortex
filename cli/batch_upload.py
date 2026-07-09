"""Batch upload all files from Aeon Docs to the Project Aeon notebook."""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cortex-mcp"))
from cortex_mcp_client import CortexClient

API_URL = "https://cortex-api-cpjo.onrender.com"
API_KEY = "2e363ff7efc9809e0ffd1fd2d32b439fc73a0929d8f15e7fbed56f5d2f624c3f"
NOTEBOOK_ID = "af63334d-e951-43fb-b067-0c30fc0d404c"
DOCS_DIR = r"C:\Projects\Projrct Aeon\Aeon Docs"

client = CortexClient(API_URL, API_KEY, timeout=120)

files = sorted(os.listdir(DOCS_DIR))
files = [f for f in files if os.path.isfile(os.path.join(DOCS_DIR, f))]

print(f"Uploading {len(files)} files to Project Aeon notebook...")
print(f"API: {API_URL}")
print()

success = 0
failed = 0
skipped = 0
failures = []

for i, filename in enumerate(files, 1):
    filepath = os.path.join(DOCS_DIR, filename)
    short = filename[:60] + "..." if len(filename) > 60 else filename
    print(f"[{i}/{len(files)}] {short}", end=" ... ", flush=True)
    try:
        result = client.upload_file(NOTEBOOK_ID, filepath)
        print(f"OK ({result.get('id', '?')[:8]})")
        success += 1
    except Exception as e:
        err = str(e)[:80]
        print(f"FAILED - {err}")
        failures.append((filename, err))
        failed += 1

print()
print(f"=== Upload Complete ===")
print(f"Success: {success}")
print(f"Failed:  {failed}")
print(f"Total:   {len(files)}")

if failures:
    print("\nFailed files:")
    for name, err in failures:
        print(f"  - {name}: {err}")
