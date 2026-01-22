#!/usr/bin/env python3
import os
import sys
import re
import json
import typer
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import yt_dlp

app = typer.Typer(help="Copycat: Social Media Ingestor for AI Reference", no_args_is_help=True)
console = Console()

def sanitize_filename(name: str, max_len: int = 50) -> str:
    """Replicates your sed 's/[^a-zA-Z0-9]/_/g' logic."""
    # Replace non-alphanumeric with underscore
    clean = re.sub(r'[^a-zA-Z0-9]', '_', name)
    # Remove repeated underscores
    clean = re.sub(r'_+', '_', clean)
    # Remove trailing underscore
    clean = clean.strip('_')
    return clean[:max_len]

@app.command()
def ingest(
    url: str = typer.Argument(..., help="Video URL (YouTube, TikTok, Instagram, etc)"),
    output: Path = typer.Option(Path.cwd(), "--output", "-o", help="Output directory"),
    browser: str = typer.Option("chrome", "--browser", "-b", help="Browser to steal cookies from"),
    write_meta: bool = typer.Option(True, help="Generate Markdown metadata file"),
):
    """
    Download video reference and generate AI-ready metadata.
    """
    if not output.exists():
        output.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%m%d%Y-%H%M%S")

    console.print(Panel(f"🐱 [bold purple]Copycat Ingest[/bold purple]\nURL: [dim]{url}[/dim]\nDest: [blue]{output}[/blue]", style="purple"))

    try:
        # 1. Extract Info First (Lightweight) with minimal options
        temp_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(temp_opts) as temp_ydl:
            with console.status("[bold purple]🔍 Fetching metadata...[/bold purple]"):
                info = temp_ydl.extract_info(url, download=False)

        # 2. Construct Custom Filename (Your Logic)
        raw_uploader = info.get('uploader', 'unknown_user')
        clean_uploader = sanitize_filename(raw_uploader)

        final_filename = f"{timestamp}_{clean_uploader}.mp4"
        final_path = output / final_filename
        meta_path = output / f"{timestamp}_{clean_uploader}_meta.md"

        # 3. Configure yt-dlp with correct output template
        download_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'cookiesfrombrowser': (browser, None, None, None),
            'quiet': True,
            'no_warnings': True,
            'outtmpl': str(final_path),
            'restrictfilenames': True,
        }

        # 4. Download with correct filename
        console.print(f"[cyan]⬇️  Downloading: {final_filename}[/cyan]")
        with yt_dlp.YoutubeDL(download_opts) as ydl:
            ydl.download([url])

        # 5. Generate Markdown
        if write_meta:
            description = info.get('description', '')
            # Indent description for blockquote
            desc_formatted = "\n> ".join(description.splitlines()) if description else "No description."

            md_content = f"""# Video Metadata
- **Source URL:** {url}
- **Ingest Date:** {datetime.now()}
- **Local Path:** {final_path}

## Details
```text
Title: {info.get('title', 'N/A')}
Uploader: {info.get('uploader', 'N/A')}
Upload Date: {info.get('upload_date', 'N/A')}
Duration: {info.get('duration_string', 'N/A')}
Resolution: {info.get('width', 0)}x{info.get('height', 0)}
```

## Description
> {desc_formatted}
"""

            meta_path.write_text(md_content, encoding='utf-8')
            console.print(f"[green]📝 Metadata saved: {meta_path.name}[/green]")

        console.print(f"[bold green]✅ Copycat finished successfully.[/bold green]")

    except yt_dlp.utils.DownloadError as e:
        console.print(f"[bold red]❌ Download Error:[/bold red] {e}")
        if "cookie" in str(e).lower() or "sign in" in str(e).lower():
            console.print("[yellow]💡 Hint: Try changing browser with --browser firefox[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]❌ Unexpected Error:[/bold red] {e}")
        sys.exit(1)

if __name__ == "__main__":
    app()
