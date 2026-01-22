#!/usr/bin/env python3
import os
import sys
import time
import signal
import subprocess
import typer
import psutil
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

# --- CONFIGURATION ---
# Points strictly to ~/ComfyUI as requested
INSTALL_DIR = Path.home() / "ComfyUI"
PID_FILE = Path("/tmp/comfyui.pid")
LOG_FILE = Path("/tmp/comfyui.log")
PORT = 9000
HOST = "0.0.0.0"

app = typer.Typer(help="ComfyUI Process Manager", no_args_is_help=True)
console = Console()

def get_running_pid():
    """Reads PID file and verifies the process actually exists."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            if psutil.pid_exists(pid):
                return pid
        except ValueError:
            pass
    return None

def is_port_busy(port: int) -> bool:
    """Checks if a port is currently occupied."""
    for conn in psutil.net_connections():
        if conn.laddr.port == port:
            return True
    return False

@app.command()
def start(
    detach: bool = typer.Option(True, "--detach/--foreground", "-d", help="Run in background"),
):
    """Start the ComfyUI Server (Checks Port 9000)."""
    # 1. Check if already running
    pid = get_running_pid()
    if pid:
        console.print(f"[yellow]⚠️  ComfyUI is already running (PID: {pid})[/yellow]")
        return

    # 2. Safety Check: Is Ostris/FluxGym using the GPU?
    if is_port_busy(PORT):
        console.print(f"[bold red]❌ START FAILED: Port {PORT} is busy![/bold red]")
        console.print("[yellow]Another GPU-heavy app (Ostris/FluxGym?) is active.[/yellow]")
        console.print("Please stop it first to free the VRAM.")
        raise typer.Exit(1)

    # 3. Verify Install Path
    if not INSTALL_DIR.exists():
        console.print(f"[bold red]❌ Error: ComfyUI not found at {INSTALL_DIR}[/bold red]")
        raise typer.Exit(1)

    console.print(Panel(f"🚀 Starting ComfyUI (RTX 5090 Mode)\nPath: [dim]{INSTALL_DIR}[/dim]\nPort: [bold cyan]{PORT}[/bold cyan]", style="blue"))

    # 4. Prepare Command (Uses Comfy's internal venv)
    venv_python = INSTALL_DIR / "venv" / "bin" / "python"
    main_py = INSTALL_DIR / "main.py"
    
    # Fallback to system python if venv doesn't exist (rare)
    exe = str(venv_python) if venv_python.exists() else "python3"

    cmd = [
        exe, 
        str(main_py), 
        "--listen", HOST, 
        "--port", str(PORT)
    ]

    # 5. Execute
    if detach:
        with open(LOG_FILE, "w") as log:
            # start_new_session=True is the Python equivalent of 'nohup'
            proc = subprocess.Popen(
                cmd, 
                cwd=INSTALL_DIR, 
                stdout=log, 
                stderr=log, 
                start_new_session=True
            )
        PID_FILE.write_text(str(proc.pid))
        console.print(f"[green]✅ Started in background (PID: {proc.pid})[/green]")
        console.print(f"Logs: [dim]tail -f {LOG_FILE}[/dim]")
    else:
        # Foreground mode for debugging
        try:
            subprocess.run(cmd, cwd=INSTALL_DIR)
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping...[/yellow]")

@app.command()
def stop():
    """Stop the ComfyUI Server."""
    pid = get_running_pid()
    if not pid:
        console.print("[yellow]ComfyUI is not running.[/yellow]")
        if PID_FILE.exists(): PID_FILE.unlink()
        return

    try:
        console.print(f"[bold red]🛑 Stopping ComfyUI (PID: {pid})...[/bold red]")
        os.kill(pid, signal.SIGTERM)
        
        # Wait up to 5 seconds for it to close gracefully
        for _ in range(5):
            if not psutil.pid_exists(pid): break
            time.sleep(1)
        
        # Force kill if still stubborn
        if psutil.pid_exists(pid):
             os.kill(pid, signal.SIGKILL)

        if PID_FILE.exists(): PID_FILE.unlink()
        console.print("[green]Stopped.[/green]")
        
    except ProcessLookupError:
        console.print("[yellow]Process already dead.[/yellow]")
        if PID_FILE.exists(): PID_FILE.unlink()

@app.command()
def status():
    """Check server status."""
    pid = get_running_pid()
    if pid:
        console.print(Panel(f"✅ [bold green]RUNNING[/bold green]\nPID: {pid}\nURL: http://localhost:{PORT}", title="ComfyUI Status"))
    else:
        status_msg = "[bold red]STOPPED[/bold red]"
        if is_port_busy(PORT):
            status_msg += " [yellow](⚠️ Port 9000 Busy - Ostris/FluxGym?)[/yellow]"
        console.print(Panel(status_msg, title="ComfyUI Status"))

@app.command()
def logs(
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines to show")
):
    """Stream server logs."""
    if not LOG_FILE.exists():
        console.print("[red]No log file found.[/red]")
        return
        
    console.print(f"[dim]Tailing {LOG_FILE}... (Ctrl+C to exit)[/dim]")
    try:
        subprocess.run(["tail", "-f", "-n", str(lines), str(LOG_FILE)])
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    app()