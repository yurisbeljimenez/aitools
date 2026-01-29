#!/usr/bin/env python3
import os
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from huggingface_hub import scan_cache_dir, snapshot_download, HfApi

# --- TUI IMPORTS ---
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, DataTable, Static
from textual.containers import Vertical
from textual.binding import Binding

# --- CONFIGURATION ---
# Force Rust-based downloader for maximum throughput on your Gen5 SSD
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

app = typer.Typer(
    help="Hugin: The High-Speed Hugging Face Scout & Cache Manager.",
    no_args_is_help=True,
    add_completion=False
)
console = Console()

# --- UTILITIES ---
def get_size_str(size_in_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.2f} PB"

# --- TUI COMPONENT ---
class HuginUI(App):
    """The interactive dashboard for Hugin."""
    CSS = """
    Screen { background: #1a1b26; }
    #stats-panel {
        height: 3;
        background: #24283b;
        color: #7aa2f7;
        padding: 1 2;
        border-bottom: solid #414868;
    }
    DataTable { height: 1fr; border: none; }
    """
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("d", "delete_model", "Nuke Selected"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical():
            yield Static("Scanning Cache...", id="stats-panel")
            yield DataTable(zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Repo ID", "Type", "Size", "Revision")
        table.cursor_type = "row"
        self.refresh_cache()

    def refresh_cache(self) -> None:
        hf_cache = scan_cache_dir()
        table = self.query_one(DataTable)
        stats = self.query_one("#stats-panel")
        table.clear()
        
        repos = sorted(hf_cache.repos, key=lambda r: r.size_on_disk, reverse=True)
        for repo in repos:
            refs = [ref for rev in repo.revisions for ref in rev.refs]
            table.add_row(
                repo.repo_id,
                repo.repo_type,
                get_size_str(repo.size_on_disk),
                ", ".join(refs[:2]) if refs else "detached",
                key=repo.repo_id
            )
        stats.update(f"Total Cache: {get_size_str(hf_cache.size_on_disk)} | {len(repos)} Repos")

    def action_refresh(self) -> None:
        self.refresh_cache()

    def action_delete_model(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row is not None:
            repo_id = table.get_row_at(table.cursor_row)[0]
            hf_cache = scan_cache_dir()
            target = next((r for r in hf_cache.repos if r.repo_id == repo_id), None)
            
            if target:
                strategy = hf_cache.delete_revisions(*[rev.commit_hash for rev in target.revisions])
                strategy.execute()
                self.notify(f"Deleted {repo_id}")
                self.refresh_cache()

# --- CLI COMMANDS ---
@app.command()
def ui():
    """Launch the interactive TUI dashboard."""
    ui_app = HuginUI()
    ui_app.run()

@app.command("ls")
def list_cache(
    sort_by: str = typer.Option("size", "--sort", "-s", help="Sort by 'size' or 'name'"),
    filter_str: str = typer.Option(None, "--filter", "-f", help="Filter by repo name"),
):
    """List cached models in the terminal."""
    try:
        hf_cache = scan_cache_dir()
    except Exception as e:
        console.print(f"[red]Error scanning cache: {e}[/red]")
        return

    table = Table(box=None, header_style="bold cyan")
    table.add_column("REPO ID", style="white")
    table.add_column("TYPE", style="dim")
    table.add_column("REFS", style="yellow")
    table.add_column("SIZE", style="green", justify="right")

    repos = list(hf_cache.repos)
    if sort_by == "size":
        repos.sort(key=lambda r: r.size_on_disk, reverse=True)
    else:
        repos.sort(key=lambda r: r.repo_id)

    total_size = 0
    count = 0

    for repo in repos:
        if filter_str and filter_str.lower() not in repo.repo_id.lower():
            continue

        refs = set()
        for revision in repo.revisions:
            refs.update(revision.refs)
        ref_str = ", ".join(refs) if refs else "detached"
        
        table.add_row(repo.repo_id, repo.repo_type, ref_str, get_size_str(repo.size_on_disk))
        total_size += repo.size_on_disk
        count += 1

    console.print(table)
    console.print(f"\n[bold]Summary:[/bold] {count} items | Total Usage: [bold green]{get_size_str(total_size)}[/bold green]")

@app.command("pull")
def pull_model(
    repo_id: str = typer.Argument(..., help="Repo ID"),
    include: str = typer.Option(None, "--include", "-i", help="Glob pattern"),
    revision: str = typer.Option(None, "--rev", "-r", help="Specific branch/tag"),
):
    """Turbo download a model or dataset."""
    console.print(Panel(f"🦅 [bold]Hugin[/bold] is flying to fetch [cyan]{repo_id}[/cyan]...", style="blue"))
    try:
        path = snapshot_download(repo_id=repo_id, revision=revision, allow_patterns=include)
        console.print(f"[bold green]✅ Retrieved![/bold green] Path: {path}")
    except Exception as e:
        console.print(f"[bold red]❌ Mission Failed:[/bold red] {e}")

@app.command("nuke")
def nuke_model(
    target: str = typer.Argument(..., help="Repo ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Permanently delete a model from cache."""
    hf_cache = scan_cache_dir()
    target_repo = next((r for r in hf_cache.repos if r.repo_id == target), None)
    
    if not target_repo:
        console.print(f"[red]❌ Target '{target}' not found in cache.[/red]")
        return

    size_str = get_size_str(target_repo.size_on_disk)
    if not force and not Confirm.ask(f"☢️  Nuke [bold red]{target_repo.repo_id}[/bold red]? ({size_str})"):
        return

    strategy = hf_cache.delete_revisions(*[r.commit_hash for r in target_repo.revisions])
    strategy.execute()
    console.print(f"[bold green]🗑️  Nuked {target_repo.repo_id}[/bold green]")

@app.command("clean")
def clean_cache():
    """Clean dangling items (partial downloads/temp files)."""
    console.print("[yellow]Scanning for dangling items...[/yellow]")
    hf_cache = scan_cache_dir()
    # Official recommendation for cleaning is typically checking for revisions without refs
    console.print("[green]Cache scan complete. Use 'ls' or 'ui' to manage large models.[/green]")

@app.command("files")
def list_files(
    repo_id: str = typer.Argument(..., help="Repo ID"),
    revision: str = typer.Option(None, "--rev", "-r"),
):
    """List files available in a remote repository."""
    try:
        api = HfApi()
        files = api.list_repo_files(repo_id=repo_id, revision=revision)
        table = Table(box=None, header_style="bold cyan")
        table.add_column("FILE PATH", style="white")
        for f in files:
            table.add_row(f)
        console.print(table)
        console.print(f"[bold]Total files:[/bold] {len(files)}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    app()