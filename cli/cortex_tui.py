#!/usr/bin/env python3
"""Cortex TUI — Interactive terminal interface."""
import os
import sys
import json
import time
import threading
import requests
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.layout import Layout
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.markdown import Markdown
from rich.align import Align
from rich.columns import Columns
from rich.box import ROUNDED, DOUBLE, HEAVY

CONFIG_DIR = os.path.expanduser("~/.cortex")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
console = Console()

class CortexClient:
    def __init__(self):
        self.url = None
        self.key = None
        self.headers = {}
        
    def load(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
                self.url = cfg.get("api_url", "").rstrip("/")
                self.key = cfg.get("api_key", "")
                self.headers = {"Authorization": f"Bearer {self.key}"}
                return bool(self.url and self.key)
        return False
    
    def save(self, url, key):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump({"api_url": url, "api_key": key}, f, indent=2)
        self.url = url.rstrip("/")
        self.key = key
        self.headers = {"Authorization": f"Bearer {key}"}
    
    def health(self):
        try:
            r = requests.get(f"{self.url}/health", headers=self.headers, timeout=60)
            return r.status_code == 200, r.json() if r.ok else {}
        except Exception as e:
            return False, {"error": str(e)}
    
    def list_notebooks(self):
        r = requests.get(f"{self.url}/api/v1/notebooks", headers=self.headers, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("notebooks", []) if isinstance(data, dict) else data
    
    def create_notebook(self, name):
        r = requests.post(f"{self.url}/api/v1/notebooks", headers=self.headers,
                         json={"name": name}, timeout=30)
        r.raise_for_status()
        return r.json()
    
    def delete_notebook(self, nb_id):
        r = requests.delete(f"{self.url}/api/v1/notebooks/{nb_id}", headers=self.headers, timeout=30)
        r.raise_for_status()
    
    def upload_file(self, notebook_id, filepath):
        filename = os.path.basename(filepath)
        with open(filepath, "rb") as f:
            r = requests.post(f"{self.url}/api/v1/notebooks/{notebook_id}/sources",
                            headers=self.headers,
                            files={"file": (filename, f)},
                            data={"path": filepath}, timeout=120)
        r.raise_for_status()
        return r.json()
    
    def search(self, notebook_id, query, top_k=5):
        r = requests.post(f"{self.url}/api/v1/notebooks/{notebook_id}/search",
                         headers=self.headers,
                         json={"query": query, "top_k": top_k}, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("results", []) if isinstance(data, dict) else data
    
    def create_session(self, notebook_id, provider="gemini", model="gemini-2.0-flash"):
        r = requests.post(f"{self.url}/api/v1/notebooks/{notebook_id}/rag/sessions",
                         headers=self.headers,
                         json={"provider": provider, "model": model}, timeout=30)
        r.raise_for_status()
        return r.json()
    
    def send_message(self, notebook_id, session_id, content, provider=None, model=None):
        body = {"content": content}
        if provider: body["provider"] = provider
        if model: body["model"] = model
        r = requests.post(f"{self.url}/api/v1/notebooks/{notebook_id}/rag/sessions/{session_id}/messages",
                         headers=self.headers, json=body, timeout=120)
        r.raise_for_status()
        return r.json()
    
    def review_notebook(self, notebook_id, updated_notebook_id=None, instructions=None, provider=None, model=None):
        body = {}
        if updated_notebook_id:
            body["updated_notebook_id"] = updated_notebook_id
        if instructions:
            body["instructions"] = instructions
        if provider:
            body["provider"] = provider
        if model:
            body["model"] = model
        r = requests.post(f"{self.url}/api/v1/notebooks/{notebook_id}/review",
                         headers=self.headers, json=body, timeout=180)
        r.raise_for_status()
        return r.json()
    
    def upload_review_results(self, notebook_id, target_notebook_id, review_response):
        r = requests.post(f"{self.url}/api/v1/notebooks/{notebook_id}/review/upload-updated/{target_notebook_id}",
                         headers=self.headers, json=review_response, timeout=120)
        r.raise_for_status()
        return r.json()

client = CortexClient()

def header():
    return Panel.fit(
        "[bold cyan]CORTEX[/bold cyan] - [dim]Personal Knowledge Base[/dim]",
        box=DOUBLE,
        border_style="cyan",
        padding=(0, 2)
    )

def status_panel():
    ok, data = client.health()
    status = "[green]ONLINE[/green]" if ok else "[red]OFFLINE[/red]"
    honcho = f" (honcho: {data.get('honcho', 'N/A')})" if ok else ""
    return Panel(
        f"Server: {status}{honcho}\nURL: [dim]{client.url}[/dim]",
        title="[bold]Status[/bold]",
        border_style="blue",
        box=ROUNDED
    )

def show_login():
    console.clear()
    console.print(header())
    console.print()
    console.print(Panel.fit("[bold yellow]Login Required[/bold yellow]\nConnect to your Cortex instance", box=ROUNDED, border_style="yellow"))
    console.print()
    
    url = Prompt.ask("  API URL", default="https://cortex-api-cpjo.onrender.com")
    key = Prompt.ask("  API Key", password=True)
    
    if not key:
        console.print("[red]  Error: API key is required[/red]")
        time.sleep(1)
        return False
    
    with console.status("[bold cyan]Connecting...[/bold cyan]"):
        client.save(url, key)
        ok, data = client.health()
    
    if ok:
        console.print(Panel.fit("[bold green]Connected successfully![/bold green]", box=ROUNDED, border_style="green"))
        time.sleep(1)
        return True
    else:
        console.print(f"[yellow]  Warning: Server unreachable, but credentials saved.[/yellow]")
        time.sleep(2)
        return True

def show_main_menu():
    console.clear()
    console.print(header())
    console.print()
    
    menu = Table(show_header=False, box=None, padding=(0, 2))
    menu.add_column("Key", style="bold cyan", width=4)
    menu.add_column("Action")
    
    menu.add_row("[1]", "View Notebooks")
    menu.add_row("[2]", "Create Notebook")
    menu.add_row("[3]", "Upload Files")
    menu.add_row("[4]", "Chat with AI")
    menu.add_row("[5]", "Search Knowledge")
    menu.add_row("[6]", "Delete Notebook")
    menu.add_row("[7]", "Review & Update Files")
    menu.add_row("[s]", "Server Status")
    menu.add_row("[q]", "Quit")
    
    console.print(Panel(menu, title="[bold]Main Menu[/bold]", box=ROUNDED, border_style="cyan"))
    console.print()
    
    return Prompt.ask("  Select", choices=["1","2","3","4","5","6","7","s","q"], default="1")

def select_notebook(prompt="Select notebook"):
    """Returns notebook ID or None."""
    with console.status("[bold cyan]Loading notebooks...[/bold cyan]"):
        notebooks = client.list_notebooks()
    
    if not notebooks:
        console.print("[yellow]  No notebooks found. Create one first.[/yellow]")
        Prompt.ask("  Press Enter to continue")
        return None
    
    table = Table(title="Your Notebooks", box=ROUNDED, border_style="cyan")
    table.add_column("#", style="bold", width=4)
    table.add_column("ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Sources", justify="right")
    
    for i, nb in enumerate(notebooks, 1):
        table.add_row(str(i), nb["id"][:12] + "...", nb.get("name", "Untitled"), 
                     str(nb.get("source_count", "?")))
    
    console.print(table)
    console.print()
    
    choice = Prompt.ask(f"  {prompt} (1-{len(notebooks)})", default="1")
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(notebooks):
            return notebooks[idx]["id"]
    except:
        pass
    
    console.print("[red]  Invalid selection[/red]")
    time.sleep(1)
    return None

def view_notebooks():
    console.clear()
    console.print(header())
    console.print()
    
    with console.status("[bold cyan]Loading notebooks...[/bold cyan]"):
        notebooks = client.list_notebooks()
    
    if not notebooks:
        console.print(Panel.fit("[dim]No notebooks yet. Create one from the main menu![/dim]", box=ROUNDED))
    else:
        table = Table(title=f"Notebooks ({len(notebooks)})", box=ROUNDED, border_style="cyan")
        table.add_column("ID", style="dim", max_width=36)
        table.add_column("Name", style="bold cyan")
        table.add_column("Sources", justify="right", style="green")
        table.add_column("Created", style="dim")
        
        for nb in notebooks:
            created = nb.get("created_at", "")[:10] if nb.get("created_at") else "?"
            table.add_row(nb["id"], nb.get("name", "Untitled"),
                        str(nb.get("source_count", "?")), created)
        
        console.print(table)
    
    console.print()
    Prompt.ask("  Press Enter to continue")

def create_notebook():
    console.clear()
    console.print(header())
    console.print()
    console.print(Panel.fit("[bold]Create New Notebook[/bold]", box=ROUNDED, border_style="green"))
    console.print()
    
    name = Prompt.ask("  Notebook name")
    if not name:
        console.print("[red]  Name cannot be empty[/red]")
        time.sleep(1)
        return
    
    with console.status("[bold cyan]Creating notebook...[/bold cyan]"):
        nb = client.create_notebook(name)
    
    console.print()
    console.print(Panel.fit(
        f"[bold green]Created![/bold green]\n\n"
        f"ID: [cyan]{nb['id']}[/cyan]\n"
        f"Name: [bold]{nb.get('name', name)}[/bold]",
        box=ROUNDED, border_style="green"
    ))
    console.print()
    Prompt.ask("  Press Enter to continue")

def upload_files():
    console.clear()
    console.print(header())
    console.print()
    
    nb_id = select_notebook("Upload to notebook")
    if not nb_id:
        return
    
    console.clear()
    console.print(header())
    console.print()
    console.print(Panel.fit(f"[bold]Upload Files[/bold]\nto notebook: [cyan]{nb_id[:12]}...[/cyan]", 
                           box=ROUNDED, border_style="green"))
    console.print()
    
    paths_str = Prompt.ask("  File paths (space-separated, or drag & drop)")
    if not paths_str:
        return
    
    filepaths = [p.strip().strip('"').strip("'") for p in paths_str.split()]
    valid_files = [f for f in filepaths if os.path.exists(f)]
    
    if not valid_files:
        console.print("[red]  No valid files found[/red]")
        time.sleep(1)
        return
    
    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Uploading {len(valid_files)} file(s)...", total=len(valid_files))
        
        for filepath in valid_files:
            progress.update(task, description=f"Uploading {os.path.basename(filepath)}...")
            try:
                client.upload_file(nb_id, filepath)
            except Exception as e:
                console.print(f"\n  [red]Failed {os.path.basename(filepath)}: {e}[/red]")
            progress.advance(task)
    
    console.print()
    console.print(Panel.fit("[bold green]Upload complete![/bold green]\n[dim]Files are processing in the background[/dim]",
                           box=ROUNDED, border_style="green"))
    console.print()
    Prompt.ask("  Press Enter to continue")

def chat_mode():
    console.clear()
    console.print(header())
    console.print()
    
    nb_id = select_notebook("Chat with notebook")
    if not nb_id:
        return
    
    provider = Prompt.ask("  Provider", default="gemini")
    model = Prompt.ask("  Model", default="gemini-2.0-flash")
    
    with console.status("[bold cyan]Creating chat session...[/bold cyan]"):
        session = client.create_session(nb_id, provider, model)
        session_id = session["id"]
    
    console.clear()
    console.print(header())
    console.print()
    console.print(Panel(
        f"Notebook: [cyan]{nb_id[:16]}...[/cyan]  |  "
        f"Provider: [green]{provider}[/green]  |  "
        f"Model: [yellow]{model}[/yellow]\n"
        f"[dim]Commands: /provider <name> | /model <name> | /quit[/dim]",
        title="[bold]Chat Mode[/bold]",
        box=ROUNDED,
        border_style="cyan"
    ))
    console.print()
    
    current_provider = provider
    current_model = model
    chat_history = []
    
    while True:
        try:
            user_input = Prompt.ask("[bold cyan]You[/bold cyan]")
        except (EOFError, KeyboardInterrupt):
            break
        
        if not user_input:
            continue
        if user_input.lower() == "/quit":
            break
        if user_input.startswith("/provider "):
            current_provider = user_input.split(" ", 1)[1].strip()
            console.print(f"  [dim]Switched to provider: {current_provider}[/dim]")
            continue
        if user_input.startswith("/model "):
            current_model = user_input.split(" ", 1)[1].strip()
            console.print(f"  [dim]Switched to model: {current_model}[/dim]")
            continue
        
        # Show user message
        chat_history.append(("you", user_input))
        
        # Get AI response
        try:
            with console.status("[bold magenta]Thinking...[/bold magenta]"):
                resp = client.send_message(nb_id, session_id, user_input, 
                                          current_provider, current_model)
            
            ai_text = resp.get("content", "No response")
            ai_prov = resp.get("provider", current_provider)
            ai_model = resp.get("model", current_model)
            citations = resp.get("citations", [])
            
            # Format response
            response_panel = Panel(
                Markdown(ai_text),
                title=f"[bold magenta]AI[/bold magenta] [dim]({ai_prov}/{ai_model})[/dim]",
                border_style="magenta",
                box=ROUNDED,
                padding=(1, 2)
            )
            console.print(response_panel)
            
            if citations:
                cit_table = Table(show_header=False, box=None, padding=(0, 1))
                cit_table.add_column("Source", style="dim")
                cit_table.add_column("Score", style="green", width=8)
                for c in citations[:3]:
                    cit_table.add_row(c.get("source_filename", "?"), f"{c.get('score', 0):.2f}")
                console.print(Panel(cit_table, title="[dim]Sources[/dim]", box=None))
            
            console.print()
            chat_history.append(("ai", ai_text))
            
        except requests.exceptions.RequestException as e:
            console.print(f"[red]  Error: {e}[/red]\n")

def search_mode():
    console.clear()
    console.print(header())
    console.print()
    
    nb_id = select_notebook("Search notebook")
    if not nb_id:
        return
    
    console.clear()
    console.print(header())
    console.print()
    
    query = Prompt.ask("  Search query")
    if not query:
        return
    
    top_k = Prompt.ask("  Number of results", default="5")
    
    with console.status("[bold cyan]Searching...[/bold cyan]"):
        results = client.search(nb_id, query, int(top_k))
    
    console.clear()
    console.print(header())
    console.print()
    
    if not results:
        console.print(Panel.fit("[dim]No results found.[/dim]", box=ROUNDED))
    else:
        console.print(Panel.fit(f"[bold]Search Results[/bold] for: [cyan]{query}[/cyan] ({len(results)} found)",
                               box=ROUNDED, border_style="green"))
        console.print()
        
        for i, hit in enumerate(results, 1):
            content = hit.get("content", "")
            score = hit.get("score", 0)
            filename = hit.get("source_filename", "Unknown")
            
            # Color score
            if score > 0.8:
                score_str = f"[bold green]{score:.3f}[/bold green]"
            elif score > 0.5:
                score_str = f"[yellow]{score:.3f}[/yellow]"
            else:
                score_str = f"[dim]{score:.3f}[/dim]"
            
            panel = Panel(
                Markdown(content[:500] + ("..." if len(content) > 500 else "")),
                title=f"[{i}] [bold]{filename}[/bold]  Score: {score_str}",
                border_style="cyan",
                box=ROUNDED,
                padding=(1, 2)
            )
            console.print(panel)
            console.print()
    
    Prompt.ask("  Press Enter to continue")

def delete_notebook():
    console.clear()
    console.print(header())
    console.print()
    
    nb_id = select_notebook("Delete notebook")
    if not nb_id:
        return
    
    if Confirm.ask(f"  [red]Really delete notebook {nb_id}?[/red]", default=False):
        with console.status("[bold red]Deleting...[/bold red]"):
            client.delete_notebook(nb_id)
        console.print("[green]  Deleted![/green]")
    else:
        console.print("[dim]  Cancelled[/dim]")
    time.sleep(1)

def show_status():
    console.clear()
    console.print(header())
    console.print()
    
    with console.status("[bold cyan]Checking server...[/bold cyan]"):
        ok, data = client.health()
    
    info = Table(show_header=False, box=None, padding=(0, 2))
    info.add_column("Key", style="bold")
    info.add_column("Value")
    
    info.add_row("Config", CONFIG_FILE)
    info.add_row("API URL", client.url or "[dim]not set[/dim]")
    info.add_row("Server", "[green]Online[/green]" if ok else "[red]Offline[/red]")
    if ok:
        info.add_row("Honcho", str(data.get("honcho", "unknown")))
    
    console.print(Panel(info, title="[bold]Server Status[/bold]", box=ROUNDED, 
                       border_style="cyan" if ok else "red"))
    console.print()
    Prompt.ask("  Press Enter to continue")

def review_mode():
    """AI-powered file review and update generation."""
    console.clear()
    console.print(header())
    console.print()
    console.print(Panel.fit(
        "[bold]Review & Update Files[/bold]\n\n"
        "AI will review your notebook files and can:\n"
        "- Compare with an updated notebook\n"
        "- Generate improved/updated versions\n"
        "- Apply your custom instructions",
        box=ROUNDED, border_style="magenta"
    ))
    console.print()
    
    # Select original notebook
    console.print("[bold]Step 1:[/bold] Select the original notebook")
    original_id = select_notebook("Original notebook")
    if not original_id:
        return
    
    console.clear()
    console.print(header())
    console.print()
    
    # Ask if they want to compare with another notebook
    compare = Confirm.ask("  Compare with an updated notebook?", default=False)
    
    updated_id = None
    if compare:
        console.print()
        console.print("[bold]Step 2:[/bold] Select the updated notebook for comparison")
        updated_id = select_notebook("Updated notebook")
        if not updated_id:
            console.print("[yellow]  No updated notebook selected, reviewing original only[/yellow]")
            time.sleep(1)
    
    console.clear()
    console.print(header())
    console.print()
    
    # Get instructions
    console.print("[bold]Step 3:[/bold] Review instructions (optional)")
    console.print("[dim]  Examples: 'Improve clarity', 'Add more examples', 'Update for 2024'[/dim]")
    instructions = Prompt.ask("  Instructions", default="")
    
    # Provider/model
    console.print()
    provider = Prompt.ask("  Provider", default="gemini")
    model = Prompt.ask("  Model", default="gemini-2.0-flash")
    
    console.clear()
    console.print(header())
    console.print()
    
    # Run the review
    console.print(Panel.fit(
        f"[bold]Reviewing files...[/bold]\n\n"
        f"Original: [cyan]{original_id[:12]}...[/cyan]\n"
        f"Updated:  [cyan]{updated_id[:12] if updated_id else 'None'}...[/cyan]\n"
        f"Provider: [green]{provider}/{model}[/green]",
        box=ROUNDED, border_style="magenta"
    ))
    console.print()
    
    with console.status("[bold magenta]AI is reviewing files (this may take a minute)...[/bold magenta]"):
        try:
            result = client.review_notebook(
                original_id,
                updated_notebook_id=updated_id,
                instructions=instructions if instructions else None,
                provider=provider,
                model=model
            )
        except requests.exceptions.RequestException as e:
            console.print(f"[red]  Review failed: {e}[/red]")
            Prompt.ask("  Press Enter to continue")
            return
    
    # Display results
    console.clear()
    console.print(header())
    console.print()
    
    summary = result.get("summary", "No summary")
    console.print(Panel(
        Markdown(summary),
        title="[bold magenta]Review Summary[/bold magenta]",
        border_style="magenta",
        box=ROUNDED,
        padding=(1, 2)
    ))
    console.print()
    
    updated_files = result.get("updated_files", [])
    if not updated_files:
        console.print("[yellow]  No updated files generated.[/yellow]")
        Prompt.ask("  Press Enter to continue")
        return
    
    console.print(f"[bold]Generated {len(updated_files)} updated file(s):[/bold]")
    console.print()
    
    for i, f in enumerate(updated_files, 1):
        filename = f.get("filename", "unknown")
        changes = f.get("changes", "No changes description")
        content_preview = f.get("content", "")[:200]
        
        file_panel = Panel(
            f"[dim]{content_preview}...[/dim]",
            title=f"[{i}] [bold cyan]{filename}[/bold cyan]",
            subtitle=f"[italic]{changes}[/italic]",
            border_style="cyan",
            box=ROUNDED,
            padding=(1, 2)
        )
        console.print(file_panel)
        console.print()
    
    # Ask if they want to save the results
    console.print()
    if Confirm.ask("  Save updated files to a notebook?", default=True):
        console.print()
        console.print("[bold]Select target notebook for updated files:[/bold]")
        
        # Option to create new or use existing
        target_choice = Prompt.ask(
            "  Target",
            choices=["existing", "new"],
            default="new"
        )
        
        if target_choice == "new":
            name = Prompt.ask("  New notebook name", default="Updated Files")
            with console.status("[bold cyan]Creating notebook...[/bold cyan]"):
                new_nb = client.create_notebook(name)
                target_id = new_nb["id"]
            console.print(f"  [green]Created notebook: {target_id}[/green]")
        else:
            target_id = select_notebook("Target notebook")
            if not target_id:
                console.print("[yellow]  No target selected, files not saved[/yellow]")
                Prompt.ask("  Press Enter to continue")
                return
        
        # Upload the results
        with console.status("[bold cyan]Uploading updated files...[/bold cyan]"):
            try:
                upload_result = client.upload_review_results(original_id, target_id, result)
                uploaded = upload_result.get("uploaded", [])
                console.print()
                console.print(Panel.fit(
                    f"[bold green]Uploaded {len(uploaded)} file(s)![/bold green]\n\n"
                    f"Target notebook: [cyan]{target_id}[/cyan]",
                    box=ROUNDED, border_style="green"
                ))
            except requests.exceptions.RequestException as e:
                console.print(f"[red]  Upload failed: {e}[/red]")
    
    console.print()
    Prompt.ask("  Press Enter to continue")

def main():
    # Check login
    if not client.load():
        if not show_login():
            return
    
    # Main loop
    while True:
        choice = show_main_menu()
        
        if choice == "1":
            view_notebooks()
        elif choice == "2":
            create_notebook()
        elif choice == "3":
            upload_files()
        elif choice == "4":
            chat_mode()
        elif choice == "5":
            search_mode()
        elif choice == "6":
            delete_notebook()
        elif choice == "7":
            review_mode()
        elif choice == "s":
            show_status()
        elif choice == "q":
            if Confirm.ask("  Quit Cortex?", default=True):
                console.clear()
                console.print("[dim]Goodbye![/dim]")
                break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.clear()
        console.print("[dim]Interrupted. Goodbye![/dim]")
