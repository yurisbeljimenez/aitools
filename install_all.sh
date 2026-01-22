#!/usr/bin/env python3
import os
import sys
import re
import typer
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
import yt_dlp

# Define the app
app = typer.Typer(help="Copycat: Social Media Ingestor for AI Reference", no_args_is_help=True)
console = Console()

def sanitize_filename(name: str, max_len: int = 50) -> str:
    """Sanitizes the uploader name for the filesystem."""
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
    output: Path = typer.Option(None, "--output", "-o", help="Target folder (Defaults to current dir)"),
    browser: str = typer.Option("chrome", "--browser", "-b", help="Browser to steal cookies from"),
    write_meta: bool = typer.Option(True, help="Generate Markdown metadata file"),
):
    """
    Download video reference and generate AI-ready metadata.
    """
    # 1. Determine Output Directory
    # If no output specified, use the Current Working Directory (where the user is standing)
    if output is None:
        target_dir = Path.cwd()
    else:
        target_dir = output.resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%m%d%Y-%H%M%S")
    
    console.print(Panel(f"🐱 [bold purple]Copycat Ingest[/bold purple]\nURL: [dim]{url}[/dim]\nDest: [blue]{target_dir}[/blue]", style="purple"))

    # 2. Configure yt-dlp
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'merge_output_format': 'mp4',
        'cookiesfrombrowser': (browser, None, None, None), # Tuple format required by lib
        'quiet': True,
        'no_warnings': True,
        'outtmpl': f'{target_dir}/temp_{timestamp}.%(ext)s', # Temp name
        'restrictfilenames': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 3. Extract Info (Fast)
            with console.status("[bold purple]🔍 Fetching metadata...[/bold purple]"):
                info = ydl.extract_info(url, download=False)

            # 4. Construct Final Filename
            # Logic: TIMESTAMP_UPLOADER.mp4
            raw_uploader = info.get('uploader', 'unknown_user')
            clean_uploader = sanitize_filename(raw_uploader)
            
            final_filename = f"{timestamp}_{clean_uploader}.mp4"
            final_path = target_dir / final_filename
            meta_path = target_dir / f"{timestamp}_{clean_uploader}_meta.md"

            # Update the download path to the final name
            ydl.params['outtmpl']['default'] = str(final_path)

            # 5. Download
            console.print(f"[cyan]⬇️  Downloading: {final_filename}[/cyan]")
            ydl.download([url])
            
            # 6. Generate Markdown Metadata
            if write_meta:
                description = info.get('description', '')
                # Indent description for blockquote formatting
                desc_formatted = "\n> ".join(description.splitlines()) if description else "No description."

                # We construct the Markdown string carefully
                md_content = (
                    f"# Video Metadata\n"
                    f"- **Source URL:** {url}\n"
                    f"- **Ingest Date:** {datetime.now()}\n"
                    f"- **Local Path:** {final_path}\n\n"
                    f"## Details\n"
                    f"```text\n"
                    f"Title: {info.get('title', 'N/A')}\n"
                    f"Uploader: {info.get('uploader', 'N/A')}\n"
                    f"Upload Date: {info.get('upload_date', 'N/A')}\n"
                    f"Duration: {info.get('duration_string', 'N/A')}\n"
                    f"Resolution: {info.get('width', 0)}x{info.get('height', 0)}\n"
                    f"```\n\n"
                    f"## Description\n"
                    f"> {desc_formatted}\n"
                )
                
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