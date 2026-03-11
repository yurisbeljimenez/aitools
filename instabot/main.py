#!/usr/bin/env python3
import sys
import subprocess
import os

from rich.console import Console
from rich.panel import Panel


def version_callback(value: bool):
    """Display version information."""
    if value:
        console.print("[bold cyan]instabot v1.0 - Simple Instaloader Wrapper[/bold cyan]")
        raise typer.Exit()


console = Console()

import typer

app = typer.Typer(
    help="instabot: Thin wrapper around instaloader", 
    no_args_is_help=True, 
    rich_markup_mode="rich"
)

@app.callback()
def callback(version: bool = typer.Option(False, "--version", "-v", callback=version_callback, help="Show version")):
    pass


def main(
    handler: str = typer.Argument(..., help="Instagram User Handler (without @)")
):
    """
    instabot: Thin wrapper around instaloader.

    Usage: instabot <username>

    This matches your macOS script behavior exactly:
    --load-cookies chrome --no-videos --fast-update --no-captions --no-metadata-json --no-compress-json
    
    Simply calls the installed instaloader CLI with identical arguments.
    """
    console.print(Panel(f"📸 [bold]instabot[/bold]\nTarget: @{handler}", style="purple"))

    # Use python -m instaloader to ensure we use the venv-installed version
    cmd = [
        sys.executable, "-m", "instaloader",
        "--load-cookies", "chrome",
        "--no-videos",
        "--fast-update", 
        "--no-captions",
        "--no-metadata-json",
        "--no-compress-json",
        handler
    ]

    console.print(f"[dim]Running: {' '.join(cmd)}[/dim]\n")

    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    typer.run(main)