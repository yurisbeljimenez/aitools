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
from rich.text import Text

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
    """Create or reuse venv for a tool."""
    venv_dir = tool_dir / "venv"
    python_exe = venv_dir / "bin" / "python"
    requirements_file = tool_dir / "requirements.txt"

    # Check if venv exists and is functional
    if venv_dir.exists() and python_exe.exists():
        try:
            # Test if python works
            run_command([str(python_exe), "--version"], cwd=tool_dir)
            # Check if key packages are installed (check typer as proxy)
            result = run_command([str(python_exe), "-c", "import typer"], cwd=tool_dir, check=False)
            if result.returncode == 0:
                progress.update(task, description=f"✅ Reusing existing venv for {tool_dir.name}...")
                return python_exe
        except:
            pass  # Fall through to recreation

    # Remove broken/old venv
    if venv_dir.exists():
        progress.update(task, description=f"🗑️  Removing old venv for {tool_dir.name}...")
        shutil.rmtree(venv_dir)

    # Create new venv
    progress.update(task, description=f"🐍 Creating venv for {tool_dir.name}...")
    run_command([sys.executable, "-m", "venv", str(venv_dir)], cwd=tool_dir)

    if not python_exe.exists():
        raise FileNotFoundError(f"Python executable not found in {venv_dir}")

    # Upgrade pip
    progress.update(task, description=f"⬆️  Upgrading pip for {tool_dir.name}...")
    run_command([str(python_exe), "-m", "pip", "install", "--upgrade", "pip"], cwd=tool_dir)

    # Install requirements
    progress.update(task, description=f"📦 Installing deps for {tool_dir.name}...")
    run_command([str(python_exe), "-m", "pip", "install", "-r", str(requirements_file)], cwd=tool_dir)

    return python_exe

def create_wrapper_script(tool_name: str, main_py: Path, python_exe: Path):
    """Create a wrapper script that runs the tool with its venv python."""
    script_path = Path("/usr/local/bin") / tool_name

    # Check if we can write to /usr/local/bin
    if not os.access("/usr/local/bin", os.W_OK):
        raise PermissionError(f"No write permission for /usr/local/bin. Run installer with sudo.")

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
    console.print(Panel.fit("🚀 [bold blue]AI Tools Universal Installer[/bold blue]\nSetting up isolated environments for all tools", style="blue"))

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
            tool_task = progress.add_task(f"Setting up {tool_dir.name}", total=2)

            try:
                # 1. Setup venv
                python_exe = setup_venv(tool_dir, progress, tool_task)
                progress.update(tool_task, advance=1)

                # 2. Create wrapper script
                progress.update(tool_task, description=f"🔧 Creating wrapper script for {tool_dir.name}...")
                main_py = tool_dir / "main.py"
                create_wrapper_script(tool_dir.name, main_py, python_exe)
                progress.update(tool_task, advance=1)

                console.print(f"[green]✅ {tool_dir.name} setup complete![/green]")

            except Exception as e:
                console.print(f"[red]❌ Failed to setup {tool_dir.name}: {e}[/red]")
                continue

            progress.update(overall_task, advance=1)

    console.print(Panel.fit("🎉 [bold green]Installation Complete![/bold green]\nAll tools are now available globally.\nRun 'tool_name --help' to get started.", style="green"))

if __name__ == "__main__":
    main()
