#!/usr/bin/env python3
"""
Cortex CLI — Interactive AI Agent Terminal

A Codex/Claude-Code-style REPL that combines:
  - Filesystem operations (ls, cd, cat, read, write, mkdir, rm, tree)
  - Knowledge base access (search, upload, notebooks)
  - AI chat with RAG context
  - Natural language fallback to /ask

Usage:
  python cortex.py              # Interactive REPL
  python cortex.py login        # Configure connection
  cortex                        # Via batch wrapper
"""

import os
import sys
import json
import time
import shutil
import requests
from pathlib import Path
from datetime import datetime

# ─── Config ──────────────────────────────────────────────────────────────────

CONFIG_DIR = os.path.expanduser("~/.cortex")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
HISTORY_FILE = os.path.join(CONFIG_DIR, "history.txt")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

# ─── Rich Setup ──────────────────────────────────────────────────────────────

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.text import Text
    from rich.tree import Tree as RichTree
    from rich.box import ROUNDED
    RICH = True
    console = Console()
except ImportError:
    RICH = False
    console = None

# ─── Prompt Toolkit Setup ────────────────────────────────────────────────────

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.styles import Style
    PROMPT_TOOLKIT = True
except ImportError:
    PROMPT_TOOLKIT = False

# ─── Cortex API Client ───────────────────────────────────────────────────────

class CortexClient:
    def __init__(self):
        self.url = None
        self.key = None
        self.headers = {}
        self.active_notebook = None
        self.active_session = None
        self.workspace = os.getcwd()

    def load(self):
        cfg = load_config()
        self.url = cfg.get("api_url", "").rstrip("/")
        self.key = cfg.get("api_key", "")
        if self.url and self.key:
            self.headers = {"Authorization": f"Bearer {self.key}"}
        self.active_notebook = cfg.get("active_notebook")
        self.workspace = cfg.get("workspace", os.getcwd())
        return bool(self.url and self.key)

    def save(self):
        cfg = load_config()
        cfg["api_url"] = self.url
        cfg["api_key"] = self.key
        cfg["active_notebook"] = self.active_notebook
        cfg["workspace"] = self.workspace
        save_config(cfg)

    def _request(self, method, path, **kwargs):
        kwargs.setdefault("timeout", 120)
        return requests.request(method, f"{self.url}{path}", headers=self.headers, **kwargs)

    def health(self):
        try:
            r = self._request("GET", "/health")
            return r.status_code == 200, r.json() if r.ok else {}
        except:
            return False, {}

    def list_notebooks(self):
        r = self._request("GET", "/api/v1/notebooks")
        r.raise_for_status()
        data = r.json()
        return data.get("notebooks", []) if isinstance(data, dict) else data

    def create_notebook(self, name):
        r = self._request("POST", "/api/v1/notebooks", json={"name": name})
        r.raise_for_status()
        return r.json()

    def delete_notebook(self, nb_id):
        self._request("DELETE", f"/api/v1/notebooks/{nb_id}").raise_for_status()

    def upload_file(self, filepath, notebook_id=None):
        nb = notebook_id or self.active_notebook
        if not nb:
            raise ValueError("No notebook selected. Use /kb select first.")
        filename = os.path.basename(filepath)
        with open(filepath, "rb") as f:
            r = self._request("POST", f"/api/v1/notebooks/{nb}/sources",
                            files={"file": (filename, f)}, data={"path": filepath})
        r.raise_for_status()
        return r.json()

    def search(self, query, top_k=5, notebook_id=None):
        nb = notebook_id or self.active_notebook
        if not nb:
            raise ValueError("No notebook selected.")
        r = self._request("POST", f"/api/v1/notebooks/{nb}/search",
                         json={"query": query, "top_k": top_k})
        r.raise_for_status()
        data = r.json()
        return data.get("results", []) if isinstance(data, dict) else data

    def create_session(self, notebook_id=None, provider="gemini", model="gemini-2.0-flash"):
        nb = notebook_id or self.active_notebook
        if not nb:
            raise ValueError("No notebook selected.")
        r = self._request("POST", f"/api/v1/notebooks/{nb}/rag/sessions",
                         json={"provider": provider, "model": model})
        r.raise_for_status()
        return r.json()

    def send_message(self, content, provider=None, model=None):
        if not self.active_notebook or not self.active_session:
            raise ValueError("No active session. Use /chat first.")
        body = {"content": content}
        if provider: body["provider"] = provider
        if model: body["model"] = model
        r = self._request("POST",
            f"/api/v1/notebooks/{self.active_notebook}/rag/sessions/{self.active_session}/messages",
            json=body)
        r.raise_for_status()
        return r.json()

    def list_sources(self, notebook_id=None):
        nb = notebook_id or self.active_notebook
        if not nb:
            raise ValueError("No notebook selected.")
        r = self._request("GET", f"/api/v1/notebooks/{nb}/sources")
        r.raise_for_status()
        data = r.json()
        return data.get("sources", []) if isinstance(data, dict) else data

client = CortexClient()

# ─── Output Helpers ──────────────────────────────────────────────────────────

def print_panel(title, content, style="cyan"):
    if RICH:
        console.print(Panel(content, title=title, box=ROUNDED, border_style=style))
    else:
        print(f"\n--- {title} ---")
        print(content)

def print_table(title, headers, rows):
    if RICH:
        table = Table(title=title, box=ROUNDED, border_style="cyan")
        for h in headers:
            table.add_column(h, style="bold")
        for row in rows:
            table.add_row(*[str(c) for c in row])
        console.print(table)
    else:
        print(f"\n--- {title} ---")
        print("\t".join(headers))
        for row in rows:
            print("\t".join(str(c) for c in row))

def print_markdown(text):
    if RICH:
        console.print(Markdown(text))
    else:
        print(text)

def print_error(msg):
    if RICH:
        console.print(f"[red]  {msg}[/red]")
    else:
        print(f"  Error: {msg}")

def print_success(msg):
    if RICH:
        console.print(f"[green]  {msg}[/green]")
    else:
        print(f"  {msg}")

def print_dim(msg):
    if RICH:
        console.print(f"[dim]{msg}[/dim]")
    else:
        print(f"  {msg}")

# ─── Filesystem Commands ─────────────────────────────────────────────────────

def cmd_ls(args):
    path = args or "."
    target = os.path.join(client.workspace, path) if not os.path.isabs(path) else path
    try:
        items = os.listdir(target)
        if not items:
            print_dim("(empty)")
            return
        rows = []
        for name in sorted(items):
            full = os.path.join(target, name)
            if os.path.isdir(full):
                rows.append([f"[bold cyan]{name}/[/bold cyan]" if RICH else f"{name}/", "dir", ""])
            else:
                size = os.path.getsize(full)
                if size < 1024:
                    s = f"{size}B"
                elif size < 1024*1024:
                    s = f"{size/1024:.1f}KB"
                else:
                    s = f"{size/(1024*1024):.1f}MB"
                rows.append([name, "file", s])
        print_table(f"Contents of {target}", ["Name", "Type", "Size"], rows)
    except Exception as e:
        print_error(str(e))

def cmd_cd(args):
    path = args or os.path.expanduser("~")
    target = os.path.join(client.workspace, path) if not os.path.isabs(path) else path
    try:
        os.chdir(target)
        client.workspace = os.getcwd()
        client.save()
        print_dim(f"Workspace: {client.workspace}")
    except Exception as e:
        print_error(str(e))

def cmd_pwd(args):
    print_dim(client.workspace)

def cmd_cat(args):
    if not args:
        print_error("Usage: cat <file>")
        return
    path = args if os.path.isabs(args) else os.path.join(client.workspace, args)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if RICH:
            ext = os.path.splitext(path)[1].lstrip(".")
            lang_map = {"py": "python", "js": "javascript", "ts": "typescript",
                       "json": "json", "md": "markdown", "html": "html",
                       "css": "css", "go": "go", "rs": "rust", "yaml": "yaml",
                       "yml": "yaml", "toml": "toml", "sh": "bash", "bat": "batch"}
            lang = lang_map.get(ext, "text")
            console.print(Syntax(content, lang, line_numbers=False, theme="monokai"))
        else:
            print(content)
    except Exception as e:
        print_error(str(e))

def cmd_read(args):
    if not args:
        print_error("Usage: read <file>")
        return
    path = args if os.path.isabs(args) else os.path.join(client.workspace, args)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        print_panel(f"File: {os.path.basename(path)}", content[:5000] + ("..." if len(content) > 5000 else ""))
        print_dim(f"({len(content)} chars, {len(content.splitlines())} lines)")
    except Exception as e:
        print_error(str(e))

def cmd_write(args):
    parts = args.split(None, 1) if args else []
    if len(parts) < 1:
        print_error("Usage: write <file>")
        return
    path = parts[0] if os.path.isabs(parts[0]) else os.path.join(client.workspace, parts[0])
    print_dim(f"Writing to: {path}")
    print_dim("Enter content (type . on a blank line to finish):")
    lines = []
    while True:
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            break
        if line.strip() == ".":
            break
        lines.append(line)
    content = "\n".join(lines)
    if content:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print_success(f"Written {len(content)} chars to {os.path.basename(path)}")
    else:
        print_dim("(cancelled)")

def cmd_mkdir(args):
    if not args:
        print_error("Usage: mkdir <dir>")
        return
    path = args if os.path.isabs(args) else os.path.join(client.workspace, args)
    try:
        os.makedirs(path, exist_ok=True)
        print_success(f"Created: {path}")
    except Exception as e:
        print_error(str(e))

def cmd_rm(args):
    if not args:
        print_error("Usage: rm <path>")
        return
    path = args if os.path.isabs(args) else os.path.join(client.workspace, args)
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        print_success(f"Removed: {path}")
    except Exception as e:
        print_error(str(e))

def cmd_tree(args):
    path = args or "."
    target = os.path.join(client.workspace, path) if not os.path.isabs(path) else path
    if not os.path.exists(target):
        print_error(f"Path not found: {target}")
        return
    if RICH:
        t = RichTree(f"[bold]{target}[/bold]")
        def _add_tree(node, p, depth=0, max_depth=3):
            if depth >= max_depth:
                return
            try:
                items = sorted(os.listdir(p))
            except PermissionError:
                return
            dirs = [i for i in items if os.path.isdir(os.path.join(p, i))]
            files = [i for i in items if not os.path.isdir(os.path.join(p, i))]
            for d in dirs[:8]:
                n = node.add(f"[cyan]{d}/[/cyan]")
                _add_tree(n, os.path.join(p, d), depth + 1, max_depth)
            for f in files[:5]:
                node.add(f)
            remaining = len(dirs) + len(files) - 8 - 5
            if remaining > 0:
                node.add(f"[dim](...{remaining} more)[/dim]")
        _add_tree(t, target)
        console.print(t)
    else:
        def _print_tree(p, prefix="", depth=0, max_depth=3):
            if depth >= max_depth:
                return
            try:
                items = sorted(os.listdir(p))
            except PermissionError:
                print(f"{prefix}[permission denied]")
                return
            for i, name in enumerate(items[:10]):
                full = os.path.join(p, name)
                is_last = i == len(items[:10]) - 1
                conn = "`-- " if is_last else "|-- "
                if os.path.isdir(full):
                    print(f"{prefix}{conn}{name}/")
                    _print_tree(full, prefix + ("    " if is_last else "|   "), depth + 1, max_depth)
                else:
                    print(f"{prefix}{conn}{name}")
        print(target)
        _print_tree(target)

# ─── Knowledge Base Commands ─────────────────────────────────────────────────

def cmd_kb_list(args):
    try:
        notebooks = client.list_notebooks()
        if not notebooks:
            print_dim("No notebooks. Create one with /kb create <name>")
            return
        rows = []
        for nb in notebooks:
            active = " [bold green]*[/bold green]" if RICH and nb["id"] == client.active_notebook else " *" if nb["id"] == client.active_notebook else ""
            rows.append([nb["id"][:12] + "...", nb.get("name", ""), str(nb.get("source_count", "?")), active.strip()])
        print_table("Notebooks", ["ID", "Name", "Sources", "Active"], rows)
    except Exception as e:
        print_error(str(e))

def cmd_kb_create(args):
    if not args:
        print_error("Usage: /kb create <name>")
        return
    try:
        nb = client.create_notebook(args)
        client.active_notebook = nb["id"]
        client.save()
        print_success(f"Created notebook: {nb.get('name', args)} ({nb['id']})")
        print_dim("Set as active notebook.")
    except Exception as e:
        print_error(str(e))

def cmd_kb_upload(args):
    if not args:
        print_error("Usage: /kb upload <file...>")
        return
    files = [f.strip().strip('"').strip("'") for f in args.split()]
    valid = [f for f in files if os.path.exists(f)]
    if not valid:
        print_error("No valid files found")
        return
    for fp in valid:
        print_dim(f"Uploading {os.path.basename(fp)}...")
        try:
            client.upload_file(fp)
            print_success(f"  {os.path.basename(fp)} — uploaded (processing)")
        except Exception as e:
            print_error(f"  {os.path.basename(fp)}: {e}")

def cmd_kb_search(args):
    if not args:
        print_error("Usage: /kb search <query>")
        return
    try:
        results = client.search(args)
        if not results:
            print_dim("No results found.")
            return
        for i, hit in enumerate(results, 1):
            score = hit.get("score", 0)
            content = hit.get("content", "")
            filename = hit.get("source_filename", "?")
            if RICH:
                s = f"[bold green]{score:.3f}[/bold green]" if score > 0.8 else f"[yellow]{score:.3f}[/yellow]" if score > 0.5 else f"[dim]{score:.3f}[/dim]"
                console.print(Panel(
                    Markdown(content[:500] + ("..." if len(content) > 500 else "")),
                    title=f"[{i}] [bold]{filename}[/bold]  Score: {s}",
                    box=ROUNDED, border_style="cyan"
                ))
            else:
                print(f"\n  [{i}] {filename} (score: {score:.3f})")
                print(f"      {content[:200]}...")
    except Exception as e:
        print_error(str(e))

def cmd_kb_select(args):
    if not args:
        print_error("Usage: /kb select <notebook_id_or_name>")
        return
    try:
        notebooks = client.list_notebooks()
        # Try exact ID match first
        for nb in notebooks:
            if nb["id"] == args or nb["id"].startswith(args):
                client.active_notebook = nb["id"]
                client.save()
                print_success(f"Active notebook: {nb.get('name', '')} ({nb['id']})")
                return
        # Try name match
        match = [nb for nb in notebooks if args.lower() in nb.get("name", "").lower()]
        if len(match) == 1:
            client.active_notebook = match[0]["id"]
            client.save()
            print_success(f"Active notebook: {match[0].get('name', '')} ({match[0]['id']})")
        elif len(match) > 1:
            print_dim("Multiple matches:")
            for nb in match:
                print_dim(f"  {nb['id'][:12]}...  {nb.get('name', '')}")
        else:
            print_error(f"No notebook matching '{args}'")
    except Exception as e:
        print_error(str(e))

def cmd_kb_status(args):
    if not client.active_notebook:
        print_dim("No active notebook. Use /kb select.")
        return
    try:
        notebooks = client.list_notebooks()
        name = "Unknown"
        sources = 0
        for nb in notebooks:
            if nb["id"] == client.active_notebook:
                name = nb.get("name", "Unknown")
                sources = nb.get("source_count", 0)
                break
        print_panel("Active Notebook", f"Name: {name}\nID: {client.active_notebook}\nSources: {sources}")
    except Exception as e:
        print_error(str(e))

# ─── AI Commands ─────────────────────────────────────────────────────────────

def cmd_ask(args):
    if not args:
        print_error("Usage: /ask <question>")
        return
    if not client.active_notebook:
        print_error("No notebook selected. Use /kb select first.")
        return
    try:
        # Create a one-shot session for the question
        provider = os.environ.get("CORTEX_PROVIDER", "gemini")
        model = os.environ.get("CORTEX_MODEL", "gemini-2.0-flash")
        session = client.create_session(provider=provider, model=model)
        session_id = session["id"]

        if RICH:
            console.print()
            with console.status("[bold magenta]Thinking...[/bold magenta]"):
                resp = client.send_message(args, provider=provider, model=model)
        else:
            print()
            print("  Thinking...")
            resp = client.send_message(args, provider=provider, model=model)

        ai_text = resp.get("content", "No response")
        ai_prov = resp.get("provider", provider)
        ai_model = resp.get("model", model)
        citations = resp.get("citations", [])

        if RICH:
            console.print(Panel(
                Markdown(ai_text),
                title=f"[bold magenta]AI[/bold magenta] [dim]({ai_prov}/{ai_model})[/dim]",
                border_style="magenta", box=ROUNDED, padding=(1, 2)
            ))
        else:
            print(f"\nAI ({ai_prov}/{ai_model}):\n  {ai_text}")

        if citations:
            print_dim("  Sources:")
            for c in citations[:3]:
                print_dim(f"    - {c.get('source_filename', '?')} (score: {c.get('score', 0):.2f})")
        print()
    except Exception as e:
        print_error(str(e))

def cmd_chat(args):
    if not client.active_notebook:
        print_error("No notebook selected. Use /kb select first.")
        return
    try:
        provider = os.environ.get("CORTEX_PROVIDER", "gemini")
        model = os.environ.get("CORTEX_MODEL", "gemini-2.0-flash")
        session = client.create_session(provider=provider, model=model)
        client.active_session = session["id"]

        print_panel("Chat Mode", f"Notebook: {client.active_notebook[:16]}...\nProvider: {provider}/{model}\nType /quit to exit chat, /provider or /model to switch")
        print()

        current_provider = provider
        current_model = model

        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input:
                continue
            if user_input == "/quit":
                break
            if user_input.startswith("/provider "):
                current_provider = user_input.split(" ", 1)[1].strip()
                print_dim(f"Switched to provider: {current_provider}")
                continue
            if user_input.startswith("/model "):
                current_model = user_input.split(" ", 1)[1].strip()
                print_dim(f"Switched to model: {current_model}")
                continue

            try:
                if RICH:
                    with console.status("[bold magenta]Thinking...[/bold magenta]"):
                        resp = client.send_message(user_input, current_provider, current_model)
                else:
                    resp = client.send_message(user_input, current_provider, current_model)

                ai_text = resp.get("content", "")
                citations = resp.get("citations", [])

                if RICH:
                    console.print(Panel(Markdown(ai_text),
                        title=f"[bold magenta]AI[/bold magenta] [dim]({current_provider}/{current_model})[/dim]",
                        border_style="magenta", box=ROUNDED, padding=(1, 2)))
                else:
                    print(f"\nAI ({current_provider}/{current_model}):\n  {ai_text}")

                if citations:
                    print_dim("  Sources:")
                    for c in citations[:3]:
                        print_dim(f"    - {c.get('source_filename', '?')} (score: {c.get('score', 0):.2f})")
                print()
            except Exception as e:
                print_error(str(e))

        client.active_session = None
    except Exception as e:
        print_error(str(e))

def cmd_provider(args):
    if not args:
        print_dim(f"Current provider: {os.environ.get('CORTEX_PROVIDER', 'gemini')}")
        return
    os.environ["CORTEX_PROVIDER"] = args.strip()
    print_success(f"Provider set to: {args.strip()}")

def cmd_model(args):
    if not args:
        print_dim(f"Current model: {os.environ.get('CORTEX_MODEL', 'gemini-2.0-flash')}")
        return
    os.environ["CORTEX_MODEL"] = args.strip()
    print_success(f"Model set to: {args.strip()}")

# ─── Session Commands ────────────────────────────────────────────────────────

def cmd_login(args):
    print_panel("Cortex Login", "Connect to your Cortex instance")
    url = input("  API URL [https://cortex-api-cpjo.onrender.com]: ").strip()
    if not url:
        url = "https://cortex-api-cpjo.onrender.com"
    key = input("  API Key: ").strip()
    if not key:
        print_error("API key is required")
        return
    client.url = url.rstrip("/")
    client.key = key
    client.headers = {"Authorization": f"Bearer {key}"}

    ok, data = client.health()
    if ok:
        client.save()
        print_success("Connected and credentials saved.")
    else:
        client.save()
        print_dim("Warning: Server unreachable, but credentials saved.")

def cmd_workspace(args):
    if not args:
        print_dim(f"Workspace: {client.workspace}")
        return
    path = os.path.abspath(os.path.expanduser(args))
    if os.path.isdir(path):
        client.workspace = path
        os.chdir(path)
        client.save()
        print_success(f"Workspace set to: {path}")
    else:
        print_error(f"Not a directory: {path}")

def cmd_status(args):
    ok, data = client.health()
    nb_name = "none"
    if client.active_notebook:
        try:
            notebooks = client.list_notebooks()
            for nb in notebooks:
                if nb["id"] == client.active_notebook:
                    nb_name = nb.get("name", "unknown")
                    break
        except:
            nb_name = client.active_notebook[:12] + "..."

    info = []
    info.append(f"Server:    {'[green]Online[/green]' if RICH and ok else 'Online' if ok else 'Offline'}")
    info.append(f"URL:       {client.url}")
    info.append(f"Workspace: {client.workspace}")
    info.append(f"Notebook:  {nb_name}")
    info.append(f"Provider:  {os.environ.get('CORTEX_PROVIDER', 'gemini')}")
    info.append(f"Model:     {os.environ.get('CORTEX_MODEL', 'gemini-2.0-flash')}")
    if ok:
        info.append(f"Honcho:    {data.get('honcho', 'unknown')}")

    print_panel("Cortex Status", "\n".join(info))

def cmd_help(args):
    help_text = """[bold]Commands:[/bold]

[bold cyan]Filesystem:[/bold cyan]
  ls [path]           List directory contents
  cd [path]           Change working directory
  pwd                 Show working directory
  cat <file>          Display file with syntax highlighting
  read <file>         Read file contents
  write <file>        Create/edit a file
  mkdir <dir>         Create directory
  rm <path>           Remove file or directory
  tree [path]         Show directory tree

[bold cyan]Knowledge Base:[/bold cyan]
  /kb list            List all notebooks
  /kb create <name>   Create a new notebook
  /kb upload <file>   Upload files to active notebook
  /kb search <query>  Semantic search
  /kb select <id>     Set active notebook
  /kb status          Show active notebook info

[bold cyan]AI:[/bold cyan]
  /ask <question>     Ask AI with knowledge base context
  /chat               Enter interactive chat mode
  /provider <name>    Switch AI provider (gemini/openai/anthropic/qwen/ollama/huggingface)
  /model <name>       Switch AI model

[bold cyan]Session:[/bold cyan]
  /login              Configure Cortex connection
  /workspace <path>   Set working directory
  /status             Show connection and session status
  /help               Show this help
  /quit               Exit

[dim]Tip: Type anything else to ask AI with knowledge base context.[/dim]"""
    if RICH:
        console.print(Panel(Markdown(help_text), box=ROUNDED, border_style="cyan"))
    else:
        print(help_text)

# ─── Command Router ──────────────────────────────────────────────────────────

FS_COMMANDS = {
    "ls": cmd_ls, "cd": cmd_cd, "pwd": cmd_pwd,
    "cat": cmd_cat, "read": cmd_read, "write": cmd_write,
    "mkdir": cmd_mkdir, "rm": cmd_rm, "tree": cmd_tree,
}

KB_COMMANDS = {
    "list": cmd_kb_list, "create": cmd_kb_create, "upload": cmd_kb_upload,
    "search": cmd_kb_search, "select": cmd_kb_select, "status": cmd_kb_status,
}

SESSION_COMMANDS = {
    "/login": cmd_login, "/workspace": cmd_workspace, "/status": cmd_status,
    "/help": cmd_help, "/quit": lambda _: "quit",
    "/ask": cmd_ask, "/chat": cmd_chat,
    "/provider": cmd_provider, "/model": cmd_model,
}

def dispatch(line):
    line = line.strip()
    if not line:
        return

    # Prefix commands
    if line == "/quit":
        return "quit"
    if line == "/help":
        cmd_help("")
        return
    if line.startswith("/kb "):
        parts = line[4:].split(None, 1)
        cmd = parts[0] if parts else ""
        args = parts[1] if len(parts) > 1 else ""
        if cmd in KB_COMMANDS:
            KB_COMMANDS[cmd](args)
        else:
            print_error(f"Unknown /kb command: {cmd}. Use /help for help.")
        return
    if line.startswith("/"):
        parts = line.split(None, 1)
        cmd = parts[0] if parts else ""
        args = parts[1] if len(parts) > 1 else ""
        if cmd in SESSION_COMMANDS:
            result = SESSION_COMMANDS[cmd](args)
            if result == "quit":
                return "quit"
        else:
            print_error(f"Unknown command: {cmd}. Use /help for help.")
        return

    # Filesystem commands
    parts = line.split(None, 1)
    cmd = parts[0]
    args = parts[1] if len(parts) > 1 else ""
    if cmd in FS_COMMANDS:
        FS_COMMANDS[cmd](args)
        return

    # Natural language fallback → /ask
    cmd_ask(line)

# ─── Prompt Builder ──────────────────────────────────────────────────────────

def build_prompt():
    ws = client.workspace
    home = os.path.expanduser("~")
    if ws.startswith(home):
        ws = "~" + ws[len(home):]
    if len(ws) > 30:
        ws = "..." + ws[-27:]

    nb = ""
    if client.active_notebook:
        try:
            notebooks = client.list_notebooks()
            for n in notebooks:
                if n["id"] == client.active_notebook:
                    nb = n.get("name", client.active_notebook[:8])
                    if len(nb) > 20:
                        nb = nb[:17] + "..."
                    break
        except:
            nb = client.active_notebook[:8] + "..."

    if RICH:
        parts = [
            ("class:prompt", "cortex"),
            ("", " "),
            ("class:dim", f"[{ws}]"),
        ]
        if nb:
            parts.append(("", " "))
            parts.append(("class:notebook", f"({nb})"))
        parts.append(("", "> "))
        return parts
    else:
        p = f"cortex [{ws}]"
        if nb:
            p += f" ({nb})"
        p += "> "
        return p

# ─── Main Entry Point ────────────────────────────────────────────────────────

def main():
    # Check for login subcommand
    if len(sys.argv) > 1 and sys.argv[1] == "login":
        client.load()
        cmd_login("")
        return

    if not client.load():
        print("Not logged in. Run: cortex login")
        return

    # Verify connection
    ok, _ = client.health()
    if not ok:
        print_dim("Warning: Server unreachable. Some features may not work.")

    # Banner
    if RICH:
        console.print()
        console.print(Panel.fit(
            "[bold cyan]CORTEX[/bold cyan] [dim]— Interactive AI Agent Terminal[/dim]\n"
            "[dim]Type /help for commands, or just ask a question.[/dim]",
            box=ROUNDED, border_style="cyan"
        ))
        console.print()
    else:
        print("\nCORTEX — Interactive AI Agent Terminal")
        print("Type /help for commands, or just ask a question.\n")

    # REPL
    if PROMPT_TOOLKIT:
        style = Style.from_dict({
            "prompt": "bold cyan",
            "dim": "dim",
            "notebook": "bold green",
        })
        session = PromptSession(
            history=FileHistory(HISTORY_FILE) if os.path.exists(os.path.dirname(HISTORY_FILE)) else None,
            style=style,
        )

        while True:
            try:
                if RICH:
                    user_input = session.prompt(build_prompt())
                else:
                    user_input = session.prompt(build_prompt())
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if user_input is None:
                break

            result = dispatch(user_input)
            if result == "quit":
                break
    else:
        while True:
            try:
                prompt = build_prompt()
                if isinstance(prompt, list):
                    prompt = "cortex> "
                user_input = input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            result = dispatch(user_input)
            if result == "quit":
                break

    if RICH:
        console.print("\n[dim]Goodbye![/dim]")
    else:
        print("\nGoodbye!")

if __name__ == "__main__":
    main()