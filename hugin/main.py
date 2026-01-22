#!/usr/bin/env python3
import os
import shutil
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm
from huggingface_hub import scan_cache_dir, snapshot_download

# --- CONFIGURATION ---
# Force Rust-based downloader for max speed
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

app = typer.Typer(
    help="Hugin: The High-Speed Hugging Face Scout.",
    no_args_is_help=True,
    add_completion=False
)
console = Console()

def get_size_str(size_in_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_in_bytes < 1024:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024
    return f"{size_in_bytes:.2f} PB"

@app.command("ls")
def list_cache(
    sort_by: str = typer.Option("size", "--sort", "-s", help="Sort by 'size' or 'name'"),
    filter_str: str = typer.Option(None, "--filter", "-f", help="Filter by repo name"),
):
    """
    List cached models (Dashboard).
    """
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
    table.add_column("PATH", style="dim blue", overflow="fold")

    # Sorting Logic
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
        
        table.add_row(
            repo.repo_id,
            repo.repo_type,
            ref_str,
            get_size_str(repo.size_on_disk),
            str(repo.repo_path)
        )
        total_size += repo.size_on_disk
        count += 1

    console.print(table)
    console.print(f"\n[bold]Summary:[/bold] {count} items | Total Usage: [bold green]{get_size_str(total_size)}[/bold green]")

@app.command("pull")
def pull_model(
    repo_id: str = typer.Argument(..., help="Repo ID (e.g. black-forest-labs/FLUX.1-dev)"),
    include: str = typer.Option(None, "--include", "-i", help="Glob pattern (e.g. '*.safetensors')"),
    revision: str = typer.Option(None, "--rev", "-r", help="Specific branch/tag"),
):
    """
    Turbo download a model or dataset.
    """
    console.print(Panel(f"🦅 [bold]Hugin[/bold] is flying to fetch [cyan]{repo_id}[/cyan]...", style="blue"))
    
    allow_patterns = include if include else None
    
    try:
        path = snapshot_download(
            repo_id=repo_id,
            revision=revision,
            allow_patterns=allow_patterns,
        )
        console.print(f"[bold green]✅ Retrieved![/bold green] stored at:\n{path}")
    except Exception as e:
        console.print(f"[bold red]❌ Mission Failed:[/bold red] {e}")

@app.command("nuke")
def nuke_model(
    target: str = typer.Argument(..., help="Repo ID to delete (Fuzzy match supported)"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """
    Permanently delete a model from cache.
    """
    hf_cache = scan_cache_dir()
    
    # Precise Match First
    target_repo = next((r for r in hf_cache.repos if r.repo_id == target), None)
    
    # Fuzzy Match Second
    if not target_repo:
        candidates = [r for r in hf_cache.repos if target.lower() in r.repo_id.lower()]
        if len(candidates) == 1:
            target_repo = candidates[0]
        elif len(candidates) > 1:
            console.print(f"[yellow]⚠️  Ambiguous target '{target}'. Matches:[/yellow]")
            for c in candidates:
                console.print(f" - {c.repo_id}")
            return
    
    if not target_repo:
        console.print(f"[red]❌ Target '{target}' not found in cache.[/red]")
        return

    size_str = get_size_str(target_repo.size_on_disk)
    
    if not force:
        if not Confirm.ask(f"☢️  Are you sure you want to nuke [bold red]{target_repo.repo_id}[/bold red]? ({size_str})"):
            console.print("Aborted.")
            return

    try:
        shutil.rmtree(target_repo.repo_path)
        console.print(f"[bold green]🗑️  Nuked {target_repo.repo_id} ({size_str})[/bold green]")
    except Exception as e:
        console.print(f"[red]Error deleting:[/red] {e}")

@app.command("space")
def disk_usage():
    """
    Show disk usage stats.
    """
    total, used, free = shutil.disk_usage("/")
    hf_cache = scan_cache_dir()
    cache_size = hf_cache.size_on_disk
    
    console.print(f"[bold]System Disk:[/bold] {get_size_str(used)} / {get_size_str(total)} used")
    console.print(f"[bold]Hugging Face Cache:[/bold] [cyan]{get_size_str(cache_size)}[/cyan]")

if __name__ == "__main__":
    app()