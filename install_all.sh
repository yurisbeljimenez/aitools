#!/usr/bin/env python3
"""
Universal AI Tools Installer
Scans tool directories, sets up isolated venvs, installs dependencies,
patches shebangs, and creates global symlinks.
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID

console = Console()

def run_command(cmd: list, cwd: Path = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Command failed: {' '.join(cmd)}[/red]")
        console.print(f"[red]Error: {e.stderr}[/red]")
        raise

def get_tool_dirs() -> list[Path]:
    """Find all tool directories (those with main.py and requirements.txt)."""
    current_dir = Path.cwd()
    tools = []
    for item in current_dir.iterdir():
        if item.is_dir() and (item / "main.py").exists() and (item / "requirements.txt").exists():
            tools.append(item)
    return sorted(tools)

def setup_venv(tool_dir: Path, progress: Progress, task: TaskID) -> Path:
    """Create or update venv for a tool, ensuring all requirements are met."""
    venv_dir = tool_dir / "venv"
    python_exe = venv_dir / "bin" / "python"
    requirements_file = tool_dir / "requirements.txt"

    # 1. Create venv if missing
    if not venv_dir.exists() or not python_exe.exists():
        progress.update(task, description=f"🐍 Creating venv for {tool_dir.name}...")
        run_command([sys.executable, "-m", "venv", str(venv_dir)], cwd=tool_dir)

    # 2. Sync Dependencies
    # We remove the "check if typer exists" shortcut to ensure new deps like 'textual' are caught.
    progress.update(task, description=f"📦 Syncing deps for {tool_dir.name}...")
    
    # Upgrade pip first
    run_command([str(python_exe), "-m", "pip", "install", "--upgrade", "pip"], cwd=tool_dir)
    
    # Install/Update requirements
    run_command([str(python_exe), "-m", "pip", "install", "-r", str(requirements_file)], cwd=tool_dir)

    return python_exe

def create_wrapper_script(tool_name: str, main_py: Path, python_exe: Path):
    """Create a wrapper script that runs the tool with its venv python."""
    script_path = Path("/usr/local/bin") / tool_name

    # Remove existing script/symlink
    if script_path.exists():
        script_path.unlink()

    # Create wrapper script
    wrapper_content = f"""#!/bin/bash
exec "{python_exe}" "{main_py}" "$@"
"""
    script_path.write_text(wrapper_content)
    script_path.chmod(0o755)
    console.print(f"🔗 Created wrapper script: {script_path}")

def main():
    # Immediate check for Sudo
    if os.geteuid() != 0:
        console.print(Panel("[bold red]Permission Denied[/bold red]\nThis script must be run with [bold]sudo[/bold] to modify /usr/local/bin", style="red"))
        sys.exit(1)

    console.print(Panel.fit("🚀 [bold blue]AI Tools Universal Installer[/bold blue]\nEnsuring isolated environments are fully synced", style="blue"))

    tools = get_tool_dirs()
    if not tools:
        console.print("[red]❌ No tool directories found![/red]")
        sys.exit(1)

    console.print(f"📂 Found {len(tools)} tools: {', '.join(t.name for t in tools)}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:

        overall_task = progress.add_task("Overall Progress", total=len(tools))

        for tool_dir in tools:
            tool_task = progress.add_task(f"Processing {tool_dir.name}", total=2)

            try:
                # 1. Setup/Update venv
                python_exe = setup_venv(tool_dir, progress, tool_task)
                progress.update(tool_task, advance=1)

                # 2. Create/Update wrapper script
                progress.update(tool_task, description=f"🔧 Updating wrapper for {tool_dir.name}...")
                main_py = tool_dir / "main.py"
                create_wrapper_script(tool_dir.name, main_py, python_exe)
                progress.update(tool_task, advance=1)

                console.print(f"[green]✅ {tool_dir.name} is ready![/green]")

            except Exception as e:
                console.print(f"[red]❌ Failed to setup {tool_dir.name}: {e}[/red]")
                continue

            progress.update(overall_task, advance=1)

    console.print(Panel.fit("🎉 [bold green]Sync Complete![/bold green]\nAll tools are now updated and available globally.", style="green"))

if __name__ == "__main__":
    main()