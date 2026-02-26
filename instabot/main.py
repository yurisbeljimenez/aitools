#!/usr/bin/env python3
import sys
import re
import typer
import browser_cookie3
import instaloader
import requests
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

app = typer.Typer(help="Copycat Insta: Profile Ingestor", no_args_is_help=True)
console = Console()

def sanitize_filename(name: str, max_len: int = 50) -> str:
    """Sanitizes strings for safe filenames."""
    if not name: return "untitled"
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
    write_meta: bool = typer.Option(True, help="Generate Markdown metadata file"),
):
    """
    Download all images from a user profile using browser session.
    """
    clean_handler = sanitize_filename(handler)
    dest_dir = output / clean_handler
    if not dest_dir.exists():
        dest_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%m%d%Y-%H%M%S")
    console.print(Panel(f"📸 [bold purple]Copycat Insta[/bold purple]\nTarget: [dim]@{handler}[/dim]\nSource: [dim]{browser}[/dim]\nDest: [blue]{dest_dir}[/blue]", style="purple"))

    # CRITICAL FIX: Use Linux User-Agent to match your OS and avoid 429 Bans
    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False, 
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        max_connection_attempts=1,
        request_timeout=30,
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Inject Cookies
    if browser.lower() != "none":
        with console.status(f"[bold purple]🍪 Stealing cookies from {browser}...[/bold purple]"):
            cj = get_cookies(browser)
            if cj:
                L.context._session.cookies = cj
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

    # Fetch Profile
    try:
        with console.status("[bold purple]🔍 Fetching profile metadata...[/bold purple]"):
            profile = instaloader.Profile.from_username(L.context, handler)
            console.print(f"[cyan]ℹ️  Found profile: {profile.full_name} ({profile.mediacount} posts)[/cyan]")
    except Exception as e:
        console.print(f"[bold red]❌ Could not fetch profile:[/bold red] {e}")
        sys.exit(1)

    # Iterate and Download
    count = 0
    downloaded_count = 0
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console
    ) as progress:
        
        total = limit if limit else profile.mediacount
        task_id = progress.add_task(f"Scanning posts...", total=total)
        
        for post in profile.get_posts():
            if limit and count >= limit:
                break
            
            count += 1
            progress.update(task_id, advance=1, description=f"Processing post {count}...")

            targets = []
            if post.typename == 'GraphImage':
                targets.append((post.url, ""))
            elif post.typename == 'GraphSidecar':
                for i, node in enumerate(post.get_sidecar_nodes()):
                    if not node.is_video:
                        targets.append((node.display_url, f"_slide{i+1}"))
            
            if not targets:
                continue

            post_date = post.date_utc.strftime("%Y%m%d")
            
            for img_url, suffix in targets:
                fname = f"{post_date}_{clean_handler}_{post.shortcode}{suffix}.jpg"
                fpath = dest_dir / fname
                
                if fpath.exists():
                    continue

                try:
                    # Use the session to download (inherits the safe User-Agent)
                    resp = L.context._session.get(img_url, timeout=10)
                    if resp.status_code == 200:
                        fpath.write_bytes(resp.content)
                        downloaded_count += 1
                        
                        if write_meta:
                            mpath = dest_dir / f"{post_date}_{clean_handler}_{post.shortcode}{suffix}_meta.md"
                            capt = post.caption if post.caption else ""
                            capt = capt.replace('"""', "'''") 
                            capt = "\n> ".join(capt.splitlines())
                            
                            md = f"# Image Metadata\n- Source: https://www.instagram.com/p/{post.shortcode}/\n"
                            md += f"- Date: {datetime.now()}\n- Path: {fpath}\n\n## Details\n"
                            md += f"```text\nUploader: {profile.username}\nDate: {post.date_local}\nLikes: {post.likes}\nResolution: {post.width}x{post.height}\n```\n"
                            md += f"\n## Caption\n> {capt}\n"
                            
                            mpath.write_text(md, encoding='utf-8')

                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")

    console.print(f"[bold green]✅ Ingest finished. Downloaded {downloaded_count} images.[/bold green]")

if __name__ == "__main__":
    app()