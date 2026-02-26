#!/usr/bin/env python3
import sys
import re
import time
import typer
import browser_cookie3
import instaloader
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(help="Copycat Insta: Profile Ingestor", no_args_is_help=True)
console = Console()

def sanitize_filename(name: str, max_len: 50) -> str:
    """Sanitizes strings for safe filenames."""
    if not name: 
        return "untitled"
    clean = re.sub(r'[^a-zA-Z0-9]', '_', name)
    clean = re.sub(r'_+', '_', clean)
    clean = clean.strip('_')
    return clean[:max_len]

def get_cookies(browser: str, domain: str = ".instagram.com"):
    """Extracts cookies from the specified browser."""
    try:
        if browser.lower() == "chrome":
            return browser_cookie3.chrome(domain_name=domain)
        elif browser.lower() == "firefox":
            return browser_cookie3.firefox(domain_name=domain)
        elif browser.lower() == "edge":
            return browser_cookie3.edge(domain_name=domain)
        elif browser.lower() == "brave":
            return browser_cookie3.brave(domain_name=domain)
        else:
            return None
    except Exception as e:
        console.print(f"[bold red]⚠️  Cookie Load Error:[/bold red] {e}")
        return None

@app.command()
def ingest(
    handler: str = typer.Argument(..., help="Instagram User Handler (without @)"),
    output: Path = typer.Option(Path.cwd(), "--output", "-o", help="Output directory"),
    browser: str = typer.Option("chrome", "--browser", "-b", help="Browser to steal cookies from (chrome, firefox, edge)"),
    limit: int = typer.Option(None, "--limit", "-l", help="Max number of posts to download"),
):
    """
    Download all images from a user profile using Instaloader.
    
    Uses Instaloader's built-in flags for:
    - --skip-existing: Skip already downloaded files
    - --rate-limit: Automatic delays between requests to avoid bans
    """
    clean_handler = sanitize_filename(handler)
    dest_dir = output / clean_handler
    if not dest_dir.exists():
        dest_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel(f"📸 [bold purple]Copycat Insta[/bold purple]\nTarget: [dim]@{handler}[/dim]\nSource: [dim]{browser}[/dim]\nDest: [blue]{dest_dir}[/blue]", style="purple"))

    # Create L with Instaloader flags for rate limiting and safety
    # These flags use Instaloader's built-in mechanisms:
    # - max_connection_attempts=3: Retry failed requests
    # - request_timeout=60: Longer timeout to prevent premature failures
    # - user_agent: Linux-based UA to avoid 429 bans
    L = instaloader.Instaloader(
        download_pictures=True,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        max_connection_attempts=3,
        request_timeout=60,
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Inject cookies for authenticated access
    if browser.lower() != "none":
        with console.status(f"[bold purple]🍪 Loading cookies from {browser}...[/bold purple]"):
            cj = get_cookies(browser)
            if cj:
                L.context._session.cookies.update(cj)
                try:
                    username = L.test_login()
                    if username:
                        console.print(f"[green]✅ Authenticated as: {username}[/green]")
                    else:
                        console.print(f"[bold yellow]⚠️  Cookies loaded but login check failed.[/bold yellow]")
                except Exception as e:
                    console.print(f"[bold yellow]⚠️  Session check failed ({e}).[/bold yellow]")
            else:
                console.print(f"[bold red]❌ Could not load cookies from {browser}.[/bold red]")

    # Fetch Profile with retry logic for rate limit errors (429)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with console.status("[bold purple]🔍 Fetching profile...[/bold purple]"):
                profile = instaloader.Profile.from_username(L.context, handler)
                console.print(f"[cyan]ℹ️  Found profile: {profile.full_name} ({profile.mediacount} posts)[/cyan]")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5
                console.print(f"[yellow]⚠️  Request failed, retrying in {wait_time}s... ({e})[/yellow]")
                time.sleep(wait_time)
            else:
                console.print(f"[bold red]❌ Could not fetch profile after {max_retries} attempts:[/bold red] {e}")
                sys.exit(1)

    # Download using Instaloader's built-in --skip-existing behavior
    try:
        with console.status("[bold purple]⬇️  Downloading images...[/bold purple]"):
            post_count = limit if limit else profile.mediacount
            
            for post in instaloader.PostIterator(L.context, profile.get_posts(), post_count):
                if post.typename == 'GraphImage':
                    # Instaloader automatically skips existing files (skip-existing)
                    L.download_post(post, target=dest_dir)
                elif post.typename == 'GraphSidecar':
                    # Download only images from carousels (skip videos)
                    for node in post.get_sidecar_nodes():
                        if not node.is_video:
                            L.download_pic(node, target=dest_dir)

        console.print(f"\n[bold green]✅ Ingest finished! Images saved to {dest_dir}[/bold green]")
        
    except instaloader.InstaloaderException as e:
        console.print(f"[bold red]❌ Instaloader error:[/bold red] {e}")
        sys.exit(1)

if __name__ == "__main__":
    app()