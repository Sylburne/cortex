#!/usr/bin/env python3
"""Cortex CLI — interactive knowledge base tool."""
import argparse
import json
import os
import sys
import requests

CONFIG_DIR = os.path.expanduser("~/.cortex")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def get_client():
    cfg = load_config()
    if not cfg.get("api_url") or not cfg.get("api_key"):
        print("Not logged in. Run: cortex login")
        sys.exit(1)
    return cfg["api_url"].rstrip("/"), {"Authorization": f"Bearer {cfg['api_key']}"}

# ─── LOGIN ───────────────────────────────────────────────
def cmd_login(args):
    print("=== Cortex Login ====================================")
    url = args.url or input("  API URL [https://cortex-api-cpjo.onrender.com]: ").strip()
    if not url:
        url = "https://cortex-api-cpjo.onrender.com"
    key = args.key or input("  API Key: ").strip()
    if not key:
        print("  Error: API key is required")
        sys.exit(1)
    save_config({"api_url": url, "api_key": key})
    # Verify
    try:
        r = requests.get(f"{url}/health", timeout=60, headers={"Authorization": f"Bearer {key}"})
        if r.status_code == 200:
            print(f"  Connected to Cortex!")
        else:
            print(f"  Warning: got status {r.status_code}, but credentials saved.")
    except Exception as e:
        print(f"  Warning: couldn't reach server ({e}), but credentials saved.")
    print(f"  Config saved to {CONFIG_FILE}")
    print("=====================================================")

# ─── NOTEBOOKS ───────────────────────────────────────────
def cmd_notebooks(args):
    url, headers = get_client()
    r = requests.get(f"{url}/api/v1/notebooks", headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    # Handle paginated response
    if isinstance(data, dict):
        notebooks = data.get("notebooks", [])
    else:
        notebooks = data
    if not notebooks:
        print("No notebooks yet. Create one with: cortex create <name>")
        return
    print(f"{'ID':<40} {'Name':<30} {'Sources'}")
    print("-" * 80)
    for nb in notebooks:
        print(f"{nb['id']:<40} {nb.get('name',''):<30} {nb.get('source_count', '?')}")

def cmd_create(args):
    url, headers = get_client()
    r = requests.post(f"{url}/api/v1/notebooks", headers=headers,
                       json={"name": args.name}, timeout=30)
    r.raise_for_status()
    nb = r.json()
    print(f"Created notebook: {nb['id']}")
    print(f"  Name: {nb.get('name', args.name)}")

def cmd_delete(args):
    url, headers = get_client()
    r = requests.delete(f"{url}/api/v1/notebooks/{args.id}", headers=headers, timeout=30)
    r.raise_for_status()
    print(f"Deleted notebook {args.id}")

# ─── UPLOAD ──────────────────────────────────────────────
def cmd_upload(args):
    url, headers = get_client()
    notebook_id = args.notebook
    for filepath in args.files:
        if not os.path.exists(filepath):
            print(f"  Skipping {filepath} (not found)")
            continue
        filename = os.path.basename(filepath)
        print(f"  Uploading {filename}...", end=" ")
        try:
            with open(filepath, "rb") as f:
                r = requests.post(
                    f"{url}/api/v1/notebooks/{notebook_id}/sources",
                    headers=headers,
                    files={"file": (filename, f)},
                    data={"path": filepath},
                    timeout=120,
                )
            r.raise_for_status()
            print("done (processing in background)")
        except Exception as e:
            print(f"failed: {e}")

# ─── SEARCH ──────────────────────────────────────────────
def cmd_search(args):
    url, headers = get_client()
    r = requests.post(f"{url}/api/v1/notebooks/{args.notebook}/search",
                       headers=headers,
                       json={"query": args.query, "top_k": args.top_k},
                       timeout=30)
    r.raise_for_status()
    data = r.json()
    # Handle paginated response
    if isinstance(data, dict):
        results = data.get("results", [])
    else:
        results = data
    if not results:
        print("No results found.")
        return
    for i, hit in enumerate(results, 1):
        print(f"\n  [{i}] {hit.get('source_filename', '?')} (score: {hit.get('score', 0):.3f})")
        content = hit.get('content', '')
        print(f"      {content[:200]}{'...' if len(content) > 200 else ''}")

# ─── CHAT ────────────────────────────────────────────────
def cmd_chat(args):
    url, headers = get_client()
    notebook_id = args.notebook
    provider = args.provider or "gemini"
    model = args.model or "gemini-2.0-flash"

    # Create session
    r = requests.post(f"{url}/api/v1/notebooks/{notebook_id}/rag/sessions",
                       headers=headers,
                       json={"provider": provider, "model": model},
                       timeout=30)
    r.raise_for_status()
    session = r.json()
    session_id = session["id"]

    print("=== Cortex Chat =====================================")
    print(f"  Notebook:  {notebook_id[:16]}...")
    print(f"  Provider:  {provider}")
    print(f"  Model:     {model}")
    print(f"  Session:   {session_id[:16]}...")
    print(f"")
    print(f"  Commands:")
    print(f"    /provider <name>  -- switch provider")
    print(f"    /model <name>     -- switch model")
    print(f"    /quit             -- exit chat")
    print("=====================================================")
    print()

    current_provider = provider
    current_model = model

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_input:
            continue
        if user_input == "/quit":
            print("Bye!")
            break
        if user_input.startswith("/provider "):
            current_provider = user_input.split(" ", 1)[1].strip()
            print(f"  Switched to provider: {current_provider}")
            continue
        if user_input.startswith("/model "):
            current_model = user_input.split(" ", 1)[1].strip()
            print(f"  Switched to model: {current_model}")
            continue

        # Send message
        try:
            r = requests.post(
                f"{url}/api/v1/notebooks/{notebook_id}/rag/sessions/{session_id}/messages",
                headers=headers,
                json={"content": user_input, "provider": current_provider, "model": current_model},
                timeout=120,
            )
            r.raise_for_status()
            resp = r.json()
            print(f"\nAI ({resp.get('provider','?')}/{resp.get('model','?')}):")
            print(f"  {resp['content']}\n")

            citations = resp.get("citations", [])
            if citations:
                print(f"  Sources:")
                for c in citations[:3]:
                    print(f"    - {c.get('source_filename','?')} (score: {c.get('score',0):.2f})")
                print()
        except requests.exceptions.RequestException as e:
            print(f"\n  Error: {e}\n")

# ─── STATUS ──────────────────────────────────────────────
def cmd_status(args):
    cfg = load_config()
    url = cfg.get("api_url", "not set")
    print("=== Cortex Status ===================================")
    print(f"  Config:  {CONFIG_FILE}")
    print(f"  API URL: {url}")
    try:
        headers = {"Authorization": f"Bearer {cfg.get('api_key','')}"}
        r = requests.get(f"{url}/health", headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            print(f"  Server:  online (honcho: {data.get('honcho', 'unknown')})")
        else:
            print(f"  Server:  status {r.status_code}")
    except Exception as e:
        print(f"  Server:  unreachable ({e})")
    print("=====================================================")

# ─── MAIN ────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="cortex",
        description="Cortex — Personal knowledge base with AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cortex login                                          # Connect to your Cortex instance
  cortex create "Work Notes"                            # Create a notebook
  cortex notebooks                                      # List all notebooks
  cortex upload NOTEBOOK_ID doc.pdf readme.md           # Upload documents
  cortex chat NOTEBOOK_ID                               # Start chatting (interactive)
  cortex chat NOTEBOOK_ID --provider qwen --model qwen-plus  # Use Qwen
  cortex search NOTEBOOK_ID "machine learning"          # Search your knowledge
  cortex status                                         # Check connection
        """
    )
    sub = parser.add_subparsers(dest="command")

    # login
    p = sub.add_parser("login", help="Connect to Cortex")
    p.add_argument("--url", help="API URL")
    p.add_argument("--key", help="API key")

    # notebooks
    sub.add_parser("notebooks", help="List notebooks")

    # create
    p = sub.add_parser("create", help="Create a notebook")
    p.add_argument("name", help="Notebook name")

    # delete
    p = sub.add_parser("delete", help="Delete a notebook")
    p.add_argument("id", help="Notebook ID")

    # upload
    p = sub.add_parser("upload", help="Upload files to a notebook")
    p.add_argument("notebook", help="Notebook ID")
    p.add_argument("files", nargs="+", help="File paths to upload")

    # search
    p = sub.add_parser("search", help="Search a notebook")
    p.add_argument("notebook", help="Notebook ID")
    p.add_argument("query", help="Search query")
    p.add_argument("--top-k", type=int, default=5, help="Number of results")

    # chat
    p = sub.add_parser("chat", help="Interactive chat with RAG")
    p.add_argument("notebook", help="Notebook ID")
    p.add_argument("--provider", help="AI provider (gemini/openai/qwen/huggingface/ollama/anthropic)")
    p.add_argument("--model", help="AI model name")

    # status
    sub.add_parser("status", help="Check connection status")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "login": cmd_login,
        "notebooks": cmd_notebooks,
        "create": cmd_create,
        "delete": cmd_delete,
        "upload": cmd_upload,
        "search": cmd_search,
        "chat": cmd_chat,
        "status": cmd_status,
    }

    try:
        commands[args.command](args)
    except requests.exceptions.HTTPError as e:
        print(f"Error: {e}")
        if e.response is not None:
            try:
                print(f"  {e.response.json()}")
            except:
                print(f"  {e.response.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
