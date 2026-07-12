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

# ─── Built-in Provider & Model Data ───────────────────────────────────────────

BUILTIN_PROVIDERS = {
    "gemini":     "Google Gemini           (google_api_key)",
    "openai":     "OpenAI                  (openai_api_key)",
    "anthropic":  "Anthropic Claude        (anthropic_api_key)",
    "qwen":       "Alibaba Qwen/DashScope  (qwen_api_key)",
    "ollama":     "Ollama (local)          (ollama_base_url)",
    "huggingface":"HuggingFace Inference   (huggingface_api_key)",
}

BUILTIN_MODELS = {
    "gemini":      ["gemini-2.0-flash", "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash-lite"],
    "openai":      ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
    "anthropic":   ["claude-3-5-sonnet", "claude-3-haiku", "claude-3-opus", "claude-3-7-sonnet"],
    "qwen":        ["qwen-max", "qwen-plus", "qwen-turbo"],
    "ollama":      ["llama3.2", "mistral", "codellama", "gemma2"],
    "huggingface": ["mistralai/Mixtral-8x7B", "meta-llama/Llama-3-8B", "google/gemma-2-9b"],
}

ALL_SLASH_COMMANDS = [
    "/ask", "/chat", "/deploy", "/help", "/honcho",
    "/kb", "/login", "/model", "/provider", "/quit",
    "/settings", "/status", "/sync", "/workspace",
]

KB_SUB_COMMANDS = ["list", "create", "upload", "search", "select", "status"]
HONCHO_SUB_COMMANDS = ["enable", "disable"]
SYNC_SUB_COMMANDS = ["github", "render"]
PROVIDER_SUB_COMMANDS = ["add", "remove", "list"]

# ─── Tab Completion ──────────────────────────────────────────────────────────

try:
    from prompt_toolkit.completion import PathCompleter
    PATH_COMPLETER = PathCompleter(expanduser=True)
except ImportError:
    PATH_COMPLETER = None

class CortexCompleter(Completer):
    """Auto-complete Cortex commands and file paths."""

    def __init__(self):
        self._cached_notebooks = []

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        word = document.get_word_before_cursor(WORD=True)

        # /kb sub-commands
        if text.rstrip().startswith("/kb "):
            after_kb = text[len("/kb "):].lstrip()
            parts = after_kb.split(None, 1)
            if len(parts) == 1 and not after_kb.endswith(" "):
                # Completing sub-command
                for cmd in KB_SUB_COMMANDS:
                    if cmd.startswith(parts[0]):
                        yield Completion(cmd, start_position=-len(parts[0]))
            elif parts and parts[0] == "select":
                # Completing notebook IDs
                nb_prefix = parts[1] if len(parts) > 1 else ""
                for nb in self._cached_notebooks:
                    if nb["id"].startswith(nb_prefix) or nb.get("name", "").lower().startswith(nb_prefix.lower()):
                        display = f"{nb['id'][:12]}... ({nb.get('name', '')})"
                        yield Completion(nb["id"], start_position=-len(nb_prefix), display=display)
            return

        # /provider sub-commands
        if text.rstrip().startswith("/provider "):
            after = text[len("/provider "):].lstrip()
            parts = after.split(None, 1)
            if len(parts) == 1 and not after.endswith(" "):
                for cmd in PROVIDER_SUB_COMMANDS:
                    if cmd.startswith(parts[0]):
                        yield Completion(cmd, start_position=-len(parts[0]))
                # Also suggest provider names
                for prov in BUILTIN_PROVIDERS:
                    if prov.startswith(parts[0]):
                        yield Completion(prov, start_position=-len(parts[0]))
                # Custom providers
                cfg = load_config()
                for prov in cfg.get("custom_providers", {}):
                    if prov.startswith(parts[0]):
                        yield Completion(prov, start_position=-len(parts[0]))
            return

        # /sync sub-commands
        if text.rstrip().startswith("/sync "):
            after = text[len("/sync "):].lstrip()
            if not after.endswith(" "):
                for cmd in SYNC_SUB_COMMANDS:
                    if cmd.startswith(after):
                        yield Completion(cmd, start_position=-len(after))
            return

        # /honcho sub-commands
        if text.rstrip().startswith("/honcho "):
            after = text[len("/honcho "):].lstrip()
            if not after.endswith(" "):
                for cmd in HONCHO_SUB_COMMANDS:
                    if cmd.startswith(after):
                        yield Completion(cmd, start_position=-len(after))
            return

        # /model — suggest model names
        if text.rstrip().startswith("/model "):
            after = text[len("/model "):].lstrip()
            if not after.endswith(" "):
                for models in BUILTIN_MODELS.values():
                    for m in models:
                        if m.startswith(after):
                            yield Completion(m, start_position=-len(after))
            return

        # Slash commands (when typing /)
        if text.startswith("/"):
            for cmd in ALL_SLASH_COMMANDS:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))
            return

        # Filesystem commands — suggest file paths
        parts = text.split(None, 1)
        if parts and parts[0] in ("ls", "cd", "cat", "read", "write", "rm", "tree", "mkdir"):
            if PATH_COMPLETER:
                path_arg = parts[1] if len(parts) > 1 else ""
                # Resolve relative to workspace
                if path_arg and not os.path.isabs(path_arg):
                    path_arg = os.path.join(client.workspace, path_arg)
                elif not path_arg:
                    path_arg = client.workspace
                # Create a sub-document for path completion
                from prompt_toolkit.document import Document
                path_doc = Document(path_arg, len(path_arg))
                yield from PATH_COMPLETER.get_completions(path_doc, complete_event)
            return

        # General filesystem commands
        for cmd in ("ls", "cd", "pwd", "cat", "read", "write", "mkdir", "rm", "tree"):
            if cmd.startswith(text):
                yield Completion(cmd, start_position=-len(text))

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
        # Restore saved provider/model preferences
        if cfg.get("default_provider") and "CORTEX_PROVIDER" not in os.environ:
            os.environ["CORTEX_PROVIDER"] = cfg["default_provider"]
        if cfg.get("default_model") and "CORTEX_MODEL" not in os.environ:
            os.environ["CORTEX_MODEL"] = cfg["default_model"]
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
    parts = args.split(None, 1) if args else []
    sub = parts[0] if parts else ""
    sub_args = parts[1] if len(parts) > 1 else ""

    # /provider add <key> <name> <api_base> <api_key>
    if sub == "add":
        add_parts = sub_args.split(None, 3) if sub_args else []
        if len(add_parts) < 4:
            print_error("Usage: /provider add <key> <name> <api_base> <api_key>")
            print_dim('  Example: /provider add my-llm "My LLM" https://api.example.com/v1 sk-xxx')
            return
        key, name, api_base, api_key = add_parts
        cfg = load_config()
        if "custom_providers" not in cfg:
            cfg["custom_providers"] = {}
        # Auto-detect models from the API if possible, default to empty list
        cfg["custom_providers"][key] = {
            "name": name,
            "api_base": api_base,
            "api_key": api_key,
            "models": [],
            "type": "openai-compatible"
        }
        save_config(cfg)
        print_success(f"Added custom provider: {name} ({key})")
        print_dim("  Use /provider {key} to select it, then /model to pick a model.")
        return

    # /provider remove <key>
    if sub == "remove":
        if not sub_args:
            print_error("Usage: /provider remove <key>")
            return
        cfg = load_config()
        if "custom_providers" in cfg and sub_args in cfg["custom_providers"]:
            del cfg["custom_providers"][sub_args]
            save_config(cfg)
            # If this was the active provider, reset to gemini
            if os.environ.get("CORTEX_PROVIDER") == sub_args:
                os.environ["CORTEX_PROVIDER"] = "gemini"
            print_success(f"Removed custom provider: {sub_args}")
        else:
            print_error(f"Provider '{sub_args}' not found.")
        return

    # /provider list
    if sub == "list":
        _show_provider_table()
        return

    # /provider — show picker
    if not args:
        _show_provider_table()
        try:
            choice = input("  Pick provider (name or number): ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if choice.isdigit():
            providers = list(BUILTIN_PROVIDERS.keys())
            cfg = load_config()
            providers.extend(cfg.get("custom_providers", {}).keys())
            idx = int(choice) - 1
            if 0 <= idx < len(providers):
                choice = providers[idx]
        if choice:
            os.environ["CORTEX_PROVIDER"] = choice
            cfg = load_config()
            cfg["default_provider"] = choice
            save_config(cfg)
            print_success(f"Provider set to: {choice}")
        return

    # /provider <name> — direct set
    os.environ["CORTEX_PROVIDER"] = args.strip()
    cfg = load_config()
    cfg["default_provider"] = args.strip()
    save_config(cfg)
    print_success(f"Provider set to: {args.strip()}")

def _show_provider_table():
    cfg = load_config()
    current = os.environ.get("CORTEX_PROVIDER", "gemini")
    rows = []
    all_providers = list(BUILTIN_PROVIDERS.items())
    all_providers.extend([(k, f"{v['name']} (custom: {v['api_base']})")
                         for k, v in cfg.get("custom_providers", {}).items()])
    for i, (key, desc) in enumerate(all_providers, 1):
        active = " [bold green]*[/bold green]" if RICH and key == current else " *" if key == current else ""
        rows.append([str(i), key, desc, active.strip()])
    print_table("AI Providers", ["#", "Key", "Description", "Active"], rows)

def cmd_model(args):
    if not args:
        _show_model_table()
        try:
            choice = input("  Pick model (name or number): ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if choice.isdigit():
            all_models = []
            for models in BUILTIN_MODELS.values():
                all_models.extend(models)
            cfg = load_config()
            for prov in cfg.get("custom_providers", {}).values():
                all_models.extend(prov.get("models", []))
            idx = int(choice) - 1
            if 0 <= idx < len(all_models):
                choice = all_models[idx]
        if choice:
            os.environ["CORTEX_MODEL"] = choice
            cfg = load_config()
            cfg["default_model"] = choice
            save_config(cfg)
            print_success(f"Model set to: {choice}")
        return

    os.environ["CORTEX_MODEL"] = args.strip()
    cfg = load_config()
    cfg["default_model"] = args.strip()
    save_config(cfg)
    print_success(f"Model set to: {args.strip()}")

def _show_model_table():
    current = os.environ.get("CORTEX_MODEL", "gemini-2.0-flash")
    rows = []
    idx = 1
    for prov, models in BUILTIN_MODELS.items():
        for m in models:
            active = " [bold green]*[/bold green]" if RICH and m == current else " *" if m == current else ""
            rows.append([str(idx), prov, m, active.strip()])
            idx += 1
    cfg = load_config()
    for prov_key, prov_data in cfg.get("custom_providers", {}).items():
        for m in prov_data.get("models", []):
            active = " [bold green]*[/bold green]" if RICH and m == current else " *" if m == current else ""
            rows.append([str(idx), prov_key, m, active.strip()])
            idx += 1
    print_table("AI Models", ["#", "Provider", "Model", "Active"], rows)

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
  ls [[path]]           List directory contents
  cd [[path]]           Change working directory
  pwd                   Show working directory
  cat <file>            Display file with syntax highlighting
  read <file>           Read file contents
  write <file>          Create/edit a file
  mkdir <dir>           Create directory
  rm <path>             Remove file or directory
  tree [[path]]         Show directory tree

[bold cyan]Knowledge Base:[/bold cyan]
  /kb list              List all notebooks
  /kb create <name>     Create a new notebook
  /kb upload <file...>  Upload files to active notebook
  /kb search <query>    Semantic search
  /kb select <id>       Set active notebook
  /kb status            Show active notebook info

[bold cyan]AI:[/bold cyan]
  /ask <question>       Ask AI with knowledge base context
  /chat                 Enter interactive chat mode
  /provider <name>      Switch AI provider (gemini/openai/anthropic/qwen/ollama/huggingface)
  /model <name>         Switch AI model

[bold cyan]Session:[/bold cyan]
  /login                Configure Cortex connection
  /workspace <path>     Set working directory
  /status               Show connection and session status
  /help                 Show this help
  /quit                 Exit

[dim]Tip: Type anything else to ask AI with knowledge base context.[/dim]

[bold cyan]Settings & Deploy:[/bold cyan]
  /settings             Open interactive settings menu
  /deploy               Trigger Render deploy via deploy hook
  /sync github          Push config to GitHub
  /sync render          Alias for /deploy
  /honcho               Show Honcho memory status
  /honcho enable <key>  Set Honcho API key
  /honcho disable       Disable Honcho memory

[bold cyan]Tab Completion:[/bold cyan]
  Press [bold]TAB[/bold] after / to see all commands, or after a command for suggestions."""
    if RICH:
        console.print(Panel(help_text, box=ROUNDED, border_style="cyan"))
    else:
        print(help_text)

# ─── Settings & Deploy Commands ───────────────────────────────────────────────

def cmd_settings(args):
    """Interactive settings menu."""
    cfg = load_config()

    def _show():
        info = []
        info.append(f"  1. API URL:          {cfg.get('api_url', 'not set')}")
        info.append(f"  2. API Key:          {'***' + cfg.get('api_key', '')[-4:] if cfg.get('api_key') else 'not set'}")
        info.append(f"  3. Default Provider: {os.environ.get('CORTEX_PROVIDER', 'gemini')}")
        info.append(f"  4. Default Model:    {os.environ.get('CORTEX_MODEL', 'gemini-2.0-flash')}")
        info.append(f"  5. Workspace:        {client.workspace}")
        info.append(f"  6. GitHub Repo:      {cfg.get('github_repo', 'not set')}")
        info.append(f"  7. Render Hook:      {cfg.get('render_deploy_hook', 'not set')}")
        info.append(f"  8. Honcho API Key:   {'***' + cfg.get('honcho_api_key', '')[-4:] if cfg.get('honcho_api_key') else 'not set'}")
        info.append(f"  9. Custom Providers: {len(cfg.get('custom_providers', {}))} configured")
        info.append(f"  0. Exit settings")
        print_panel("Settings", "\n".join(info))

    while True:
        _show()
        try:
            choice = input("  Setting to change (0-9): ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if choice == "0":
            break
        elif choice == "1":
            url = input("  API URL: ").strip()
            if url:
                cfg["api_url"] = url
                client.url = url.rstrip("/")
                if client.key:
                    client.headers = {"Authorization": f"Bearer {client.key}"}
                save_config(cfg)
                print_success("API URL updated.")
        elif choice == "2":
            key = input("  API Key: ").strip()
            if key:
                cfg["api_key"] = key
                client.key = key
                if client.url:
                    client.headers = {"Authorization": f"Bearer {key}"}
                save_config(cfg)
                print_success("API Key updated.")
        elif choice == "3":
            _show_provider_table()
            prov = input("  Provider key: ").strip()
            if prov:
                os.environ["CORTEX_PROVIDER"] = prov
                cfg["default_provider"] = prov
                save_config(cfg)
                print_success(f"Default provider set to: {prov}")
        elif choice == "4":
            _show_model_table()
            model = input("  Model name: ").strip()
            if model:
                os.environ["CORTEX_MODEL"] = model
                cfg["default_model"] = model
                save_config(cfg)
                print_success(f"Default model set to: {model}")
        elif choice == "5":
            path = input("  Workspace path: ").strip()
            if path and os.path.isdir(os.path.expanduser(path)):
                abspath = os.path.abspath(os.path.expanduser(path))
                client.workspace = abspath
                os.chdir(abspath)
                cfg["workspace"] = abspath
                save_config(cfg)
                print_success(f"Workspace set to: {abspath}")
            else:
                print_error("Invalid directory.")
        elif choice == "6":
            repo = input("  GitHub repo URL: ").strip()
            if repo:
                cfg["github_repo"] = repo
                save_config(cfg)
                print_success("GitHub repo URL updated.")
        elif choice == "7":
            hook = input("  Render deploy hook URL: ").strip()
            if hook:
                cfg["render_deploy_hook"] = hook
                save_config(cfg)
                print_success("Render deploy hook updated.")
        elif choice == "8":
            key = input("  Honcho API Key: ").strip()
            if key:
                cfg["honcho_api_key"] = key
                save_config(cfg)
                print_success("Honcho API key updated.")
            else:
                cfg["honcho_api_key"] = ""
                save_config(cfg)
                print_dim("Honcho API key cleared.")
        elif choice == "9":
            _manage_custom_providers()
        else:
            print_error("Invalid choice.")

def _manage_custom_providers():
    cfg = load_config()
    providers = cfg.get("custom_providers", {})
    if not providers:
        print_dim("No custom providers configured.")
        print_dim("Use /provider add <key> <name> <api_base> <api_key> to add one.")
        return
    rows = []
    for key, data in providers.items():
        rows.append([key, data.get("name", ""), data.get("api_base", ""), str(len(data.get("models", [])))])
    print_table("Custom Providers", ["Key", "Name", "API Base", "Models"], rows)
    key = input("  Provider key to remove (or Enter to skip): ").strip()
    if key and key in providers:
        del cfg["custom_providers"][key]
        save_config(cfg)
        print_success(f"Removed custom provider: {key}")

def cmd_deploy(args):
    """Trigger a Render deploy via deploy hook."""
    cfg = load_config()
    hook = cfg.get("render_deploy_hook", "")
    if not hook:
        print_error("No Render deploy hook configured.")
        print_dim("  Set it via /settings (option 7) or add 'render_deploy_hook' to ~/.cortex/config.json")
        return
    print_dim("Triggering Render deploy...")
    try:
        if RICH:
            with console.status("[bold cyan]Deploying...[/bold cyan]"):
                r = requests.post(hook, timeout=30)
        else:
            r = requests.post(hook, timeout=30)
        if r.status_code in (200, 201, 202, 204):
            print_success("Deploy triggered! Check Render dashboard for status.")
        else:
            print_error(f"Deploy hook returned {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print_error(f"Deploy failed: {e}")

def cmd_sync(args):
    """Sync config to GitHub or trigger Render deploy."""
    parts = args.split(None, 1) if args else []
    sub = parts[0] if parts else ""

    if sub == "github":
        cfg = load_config()
        repo = cfg.get("github_repo", "")
        token = cfg.get("github_token", "")
        if not repo:
            print_error("No GitHub repo configured. Set via /settings (option 6).")
            return
        if not token:
            print_error("No GitHub token configured. Add 'github_token' to ~/.cortex/config.json")
            return

        config_path = os.path.expanduser("~/.cortex/config.json")
        if not os.path.exists(config_path):
            print_error("No config file to sync.")
            return

        import subprocess, tempfile
        # Clone to temp dir, copy config, commit, push
        tmpdir = tempfile.mkdtemp(prefix="cortex_sync_")
        try:
            repo_url = repo.replace("https://", f"https://{token}@")
            subprocess.run(["git", "clone", "--depth", "1", repo_url, tmpdir],
                          capture_output=True, check=True, timeout=30)
            # Copy config into repo
            dest = os.path.join(tmpdir, ".cortex", "config.json")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(config_path, dest)
            # Commit and push
            subprocess.run(["git", "-C", tmpdir, "config", "user.name", "Cortex CLI"],
                          capture_output=True, check=True)
            subprocess.run(["git", "-C", tmpdir, "config", "user.email", "cortex@local"],
                          capture_output=True, check=True)
            subprocess.run(["git", "-C", tmpdir, "add", ".cortex/config.json"],
                          capture_output=True, check=True)
            result = subprocess.run(["git", "-C", tmpdir, "commit", "-m", "sync: update cortex config"],
                                   capture_output=True, text=True)
            if "nothing to commit" in result.stdout + result.stderr:
                print_dim("Config is already up to date on GitHub.")
            else:
                subprocess.run(["git", "-C", tmpdir, "push", "origin", "HEAD"],
                              capture_output=True, check=True, timeout=30)
                print_success("Config synced to GitHub.")
        except subprocess.CalledProcessError as e:
            print_error(f"Git sync failed: {e.stderr if hasattr(e, 'stderr') else e}")
        except Exception as e:
            print_error(f"Sync failed: {e}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    elif sub == "render":
        cmd_deploy("")
    else:
        print_error("Usage: /sync github | /sync render")
        print_dim("  github — Push ~/.cortex/config.json to GitHub")
        print_dim("  render — Trigger Render deploy via deploy hook")

def cmd_honcho(args):
    """Show or configure Honcho memory."""
    parts = args.split(None, 1) if args else []
    sub = parts[0] if parts else ""

    if sub == "enable":
        key = parts[1] if len(parts) > 1 else ""
        if not key:
            key = input("  Honcho API Key: ").strip()
        if key:
            cfg = load_config()
            cfg["honcho_api_key"] = key
            save_config(cfg)
            print_success("Honcho enabled. API key saved.")
            print_dim("  Note: The server must be redeployed with this key to activate Honcho.")
        return

    if sub == "disable":
        cfg = load_config()
        cfg["honcho_api_key"] = ""
        save_config(cfg)
        print_success("Honcho disabled.")
        return

    # Show status
    cfg = load_config()
    honcho_key = cfg.get("honcho_api_key", "")
    ok, data = client.health()

    info = []
    if honcho_key:
        info.append(f"  Status:   [green]Configured[/green]" if RICH else "  Status:   Configured")
        info.append(f"  Key:      ***{honcho_key[-4:]}")
    else:
        info.append(f"  Status:   [dim]Not configured[/dim]" if RICH else "  Status:   Not configured")

    if ok:
        server_honcho = data.get("honcho", "unknown")
        info.append(f"  Server:   {server_honcho}")
    else:
        info.append(f"  Server:   [red]Offline[/red]" if RICH else "  Server:   Offline")

    info.append("")
    info.append("  /honcho enable <key>   — Set Honcho API key")
    info.append("  /honcho disable        — Disable Honcho memory")

    print_panel("Honcho Memory", "\n".join(info))

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
    "/settings": cmd_settings, "/deploy": cmd_deploy,
    "/sync": cmd_sync, "/honcho": cmd_honcho,
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

# ─── Banner ──────────────────────────────────────────────────────────────────

def show_banner():
    """Show the startup banner with ASCII art logo and live system info."""
    if not RICH:
        print("\n    CORTEX — Interactive AI Agent Terminal v0.1.0")
        print("    Type /help for commands, or just ask a question.\n")
        return

    console.print()

    # ASCII art logo
    logo = """[bold cyan]
   ██████╗ ██████╗ ██████╗ ████████╗███████╗██╗  ██╗
  ██╔════╝██╔═══██╗██╔══██╗╚══██╔══╝██╔════╝╚██╗██╔╝
  ██║     ██║   ██║██████╔╝   ██║   █████╗   ╚███╔╝
  ██║     ██║   ██║██╔══██╗   ██║   ██╔══╝   ██╔██╗
  ╚██████╗╚██████╔╝██║  ██║   ██║   ███████╗██╔╝ ██╗
   ╚═════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝[/bold cyan]"""
    console.print(logo)
    console.print("  [dim]Personal AI Knowledge Base[/dim] [bold]v0.1.0[/bold]")
    console.print()

    # Gather live info
    ok, data = client.health()
    server_status = "[green]● Online[/green]" if ok else "[red]● Offline[/red]"
    server_url = client.url or "not configured"

    # Notebook info
    nb_name = "none"
    nb_sources = 0
    nb_count = 0
    if client.active_notebook:
        try:
            notebooks = client.list_notebooks()
            nb_count = len(notebooks)
            for n in notebooks:
                if n["id"] == client.active_notebook:
                    nb_name = n.get("name", "unknown")
                    nb_sources = n.get("source_count", 0)
                    break
        except Exception:
            nb_name = client.active_notebook[:12] + "..."

    provider = os.environ.get("CORTEX_PROVIDER", "gemini")
    model = os.environ.get("CORTEX_MODEL", "gemini-2.0-flash")

    # Build info lines
    lines = []
    lines.append(f"  {server_status}      [dim]{server_url}[/dim]")
    lines.append(f"  [bold]▣[/bold] Notebook     [cyan]{nb_name}[/cyan]  [dim]({nb_sources} sources)[/dim]")
    if nb_count > 0:
        lines.append(f"  [bold]▣[/bold] Library      {nb_count} notebooks total")
    lines.append(f"  [bold]◆[/bold] AI           {provider} / {model}")
    lines.append(f"  [bold]◇[/bold] Workspace    [dim]{client.workspace}[/dim]")
    lines.append("")
    lines.append("  [dim]Type /help for commands, or just ask a question.[/dim]")

    console.print(Panel(
        "\n".join(lines),
        title="[bold]Cortex[/bold]",
        box=ROUNDED,
        border_style="cyan",
        padding=(1, 2)
    ))
    console.print()

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
    show_banner()

    # REPL
    if PROMPT_TOOLKIT:
        style = Style.from_dict({
            "prompt": "bold cyan",
            "dim": "dim",
            "notebook": "bold green",
        })
        cortex_completer = CortexCompleter()
        session = PromptSession(
            history=FileHistory(HISTORY_FILE) if os.path.exists(os.path.dirname(HISTORY_FILE)) else None,
            style=style,
            completer=cortex_completer,
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