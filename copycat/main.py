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
        # 1. Get uploader (like the bash script)
        with console.status("[bold purple]🔍 Fetching metadata...[/bold purple]"):
            uploader_result = subprocess.run([
                str(yt_dlp_exe), '--print', 'uploader', '--ignore-errors',
                '--no-warnings', '--age-limit', '0', '--geo-bypass', url
            ], capture_output=True, text=True)

            if uploader_result.returncode == 0 and uploader_result.stdout.strip():
                raw_uploader = uploader_result.stdout.strip().split('\n')[0]
            else:
                raw_uploader = 'unknown_user'

        # 2. Construct Custom Filename
        clean_uploader = sanitize_filename(raw_uploader)
        final_filename = f"{timestamp}_{clean_uploader}.mp4"
        final_path = output / final_filename
        meta_path = output / f"{timestamp}_{clean_uploader}_meta.md"

        # 3. Download
        console.print(f"[cyan]⬇️  Downloading: {final_filename}[/cyan]")
        download_result = subprocess.run([
            str(yt_dlp_exe),
            '--cookies-from-browser', browser,
            '--ignore-errors',
            '--no-warnings',
            '--progress',
            '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '--merge-output-format', 'mp4',
            '-o', str(final_path),
            '--restrict-filenames',
            '--age-limit', '0',
            '--geo-bypass',
            url
        ], capture_output=True, text=True)

        if download_result.returncode != 0:
            console.print(f"[bold red]❌ Download failed:[/bold red] {download_result.stderr}")
            sys.exit(1)

        if not final_path.exists():
            console.print("[bold red]❌ Download failed: File not created[/bold red]")
            sys.exit(1)

        # 4. Get metadata for markdown
        info = {}
        meta_fields = ['title', 'uploader', 'upload_date', 'duration_string', 'description']
        for field in meta_fields:
            if field == 'description':
                result = subprocess.run([str(yt_dlp_exe), '--get-description', '--ignore-errors', '--no-warnings', url],
                                      capture_output=True, text=True)
                info[field] = result.stdout.strip() if result.returncode == 0 else ''
            else:
                result = subprocess.run([str(yt_dlp_exe), '--print', f'%({field})s', '--ignore-errors', '--no-warnings', url],
                                      capture_output=True, text=True)
                info[field] = result.stdout.strip() if result.returncode == 0 else 'N/A'

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

    except Exception as e:
        console.print(f"[bold red]❌ Unexpected Error:[/bold red] {e}")
        sys.exit(1)

if __name__ == "__main__":
    app()
