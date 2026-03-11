#!/usr/bin/env python3
import re
import sys
from pathlib import Path
from datetime import datetime

import typer
import yt_dlp
from rich.console import Console
from rich.panel import Panel


def version_callback(value: bool):
    """Display version information."""
    if value:
        console.print("[bold cyan]copycat v1.0 - Social Media Ingestor for AI Reference[/bold cyan]")
        raise typer.Exit()


app = typer.Typer(help="Copycat: Social Media Ingestor for AI Reference", no_args_is_help=True, rich_markup_mode="rich")

@app.callback()
def callback(version: bool = typer.Option(False, "--version", "-v", callback=version_callback, help="Show version")):
    pass


console = Console()

# Get the yt-dlp executable from the same venv
venv_bin = Path(sys.executable).parent
yt_dlp_exe = venv_bin / 'yt-dlp'


def sanitize_filename(name: str, max_len: int = 50) -> str:
    """Replicates your sed 's/[^a-zA-Z0-9]/_/g' logic."""
    # Replace non-alphanumeric with underscore
    clean = re.sub(r'[^a-zA-Z0-9]', '_', name)
    # Remove repeated underscores
    clean = re.sub(r'_+', '_', clean)
    # Remove trailing underscore
    clean = clean.strip('_')
    return clean[:max_len]


def _print_progress(d: dict):
    """Helper for yt_dlp progress callback."""
    if d['status'] == 'downloading':
        pass  # Rich handles progress via status context manager


@app.command()
def ingest(
    url: str = typer.Argument(..., help="Video URL (YouTube, TikTok, Instagram, etc)"),
    output: Path = typer.Option(Path.cwd(), "--output", "-o", help="Output directory"),
    browser: str = typer.Option("chrome", "--browser", "-b", help="Browser to steal cookies from"),
    write_meta: bool = typer.Option(True, help="Generate Markdown metadata file"),
):
    """
    Download video reference and generate AI-ready metadata.
    
    Uses yt_dlp for efficient single-call metadata extraction and download.
    Supports YouTube, TikTok, Instagram, and 1000+ other sites.
    """
    if not output.exists():
        output.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%m%d%Y-%H%M%S")

    console.print(Panel(f"🐱 [bold purple]Copycat Ingest[/bold purple]\nURL: [dim]{url}[/dim]\nDest: [blue]{output}[/blue]", style="purple"))

    try:
        # Use yt_dlp's extract_info() for efficient metadata extraction (single call vs multiple subprocesses)
        with console.status("[bold purple]🔍 Fetching video metadata...[/bold purple]"):
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            # First pass: extract all metadata without downloading
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            
            uploader = info.get('uploader') or 'unknown_user'
            title = info.get('title', 'N/A')
            upload_date = info.get('upload_date', 'N/A')
            duration = info.get('duration', 0)
            duration_string = str(duration) if duration else 'N/A'
            description = info.get('description') or ''
            
            # Extract resolution from format if available
            formats = info.get('formats', [])
            width, height = 0, 0
            for fmt in formats:
                w = fmt.get('width') or fmt.get('w')
                h = fmt.get('height') or fmt.get('h')
                if w and h:
                    width, height = w, h
                    break
            
        # Construct filename from metadata
        clean_uploader = sanitize_filename(uploader)
        final_filename = f"{timestamp}_{clean_uploader}.mp4"
        final_path = output / final_filename
        meta_path = output / f"{timestamp}_{clean_uploader}_meta.md"

        # Download video
        console.print(f"[cyan]⬇️  Downloading: {final_filename}[/cyan]")
        download_opts = {
            'cookiesfrombrowser': browser,
            'ignoreerrors': True,
            'nowarnings': True,
            'progress_hooks': [_print_progress],
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'mergeoutputformat': 'mp4',
            'outtmpl': str(final_path),
            'restrictfilenames': True,
            'age_limit': 0,
            'geo_bypass': True,
        }
        
        with yt_dlp.YoutubeDL(download_opts) as ydl:
            ydl.download([url])

        if not final_path.exists():
            console.print("[bold red]❌ Download failed: File not created[/bold red]")
            sys.exit(1)

        # Generate Markdown metadata file
        if write_meta:
            desc_formatted = "\n> ".join(description.splitlines()) if description else "No description."

            md_content = f"""# Video Metadata
- **Source URL:** {url}
- **Ingest Date:** {datetime.now()}
- **Local Path:** {final_path}

## Details
```text
Title: {title}
Uploader: {uploader}
Upload Date: {upload_date}
Duration: {duration_string}
Resolution: {width}x{height}
```

## Description
> {desc_formatted}
"""

            meta_path.write_text(md_content, encoding='utf-8')
            console.print(f"[green]📝 Metadata saved: {meta_path.name}[/green]")

        console.print(f"[bold green]✅ Copycat finished successfully.[/bold green]")

    except Exception as e:
        console.print(f"[bold red]❌ Unexpected Error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    app()