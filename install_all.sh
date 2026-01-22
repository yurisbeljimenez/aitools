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
    """Create or recreate venv for a tool."""
    venv_dir = tool_dir / "venv"

    # Remove old venv
    if venv_dir.exists():
        progress.update(task, description=f"🗑️  Removing old venv for {tool_dir.name}...")
        shutil.rmtree(venv_dir)

    # Create new venv
    progress.update(task, description=f"🐍 Creating venv for {tool_dir.name}...")
    run_command([sys.executable, "-m", "venv", str(venv_dir)], cwd=tool_dir)

    # Get python executable path
    python_exe = venv_dir / "bin" / "python"
    if not python_exe.exists():
        raise FileNotFoundError(f"Python executable not found in {venv_dir}")

    # Upgrade pip
    progress.update(task, description=f"⬆️  Upgrading pip for {tool_dir.name}...")
    run_command([str(python_exe), "-m", "pip", "install", "--upgrade", "pip"], cwd=tool_dir)

    # Install requirements
    progress.update(task, description=f"📦 Installing deps for {tool_dir.name}...")
    requirements_file = tool_dir / "requirements.txt"
    run_command([str(python_exe), "-m", "pip", "install", "-r", str(requirements_file)], cwd=tool_dir)

    return python_exe

def patch_shebang(main_py: Path, python_exe: Path):
    """Replace generic shebang with absolute path to venv python."""
    content = main_py.read_text()
    old_shebang = "#!/usr/bin/env python3"
    new_shebang = f"#!/usr/bin/env {python_exe}"
    if old_shebang in content:
        content = content.replace(old_shebang, new_shebang)
        main_py.write_text(content)
        console.print(f"🔧 Patched shebang in {main_py}")

def create_symlink(tool_name: str, main_py: Path):
    """Create symlink in /usr/local/bin."""
    symlink_path = Path("/usr/local/bin") / tool_name

    # Remove existing symlink
    if symlink_path.exists():
        symlink_path.unlink()

    # Create new symlink
    symlink_path.symlink_to(main_py)
    console.print(f"🔗 Created symlink: {symlink_path} -> {main_py}")

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
            tool_task = progress.add_task(f"Setting up {tool_dir.name}", total=4)

            try:
                # 1. Setup venv
                python_exe = setup_venv(tool_dir, progress, tool_task)
                progress.update(tool_task, advance=1)

                # 2. Patch shebang
                progress.update(tool_task, description=f"🔧 Patching shebang for {tool_dir.name}...")
                main_py = tool_dir / "main.py"
                patch_shebang(main_py, python_exe)
                progress.update(tool_task, advance=1)

                # 3. Make executable
                progress.update(tool_task, description=f"⚙️  Making {tool_dir.name} executable...")
                main_py.chmod(0o755)
                progress.update(tool_task, advance=1)

                # 4. Create symlink
                progress.update(tool_task, description=f"🔗 Creating symlink for {tool_dir.name}...")
                create_symlink(tool_dir.name, main_py)
                progress.update(tool_task, advance=1)

                console.print(f"[green]✅ {tool_dir.name} setup complete![/green]")

            except Exception as e:
                console.print(f"[red]❌ Failed to setup {tool_dir.name}: {e}[/red]")
                continue

            progress.update(overall_task, advance=1)

    console.print(Panel.fit("🎉 [bold green]Installation Complete![/bold green]\nAll tools are now available globally.\nRun 'tool_name --help' to get started.", style="green"))

if __name__ == "__main__":
    main()
