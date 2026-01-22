#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import typer
import psutil
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

# --- CONFIGURATION ---
# Dynamic path: Works for /home/master, /home/ubuntu, etc.
TOOLKIT_DIR = Path.home() / "ai-toolkit"
UI_DIR = TOOLKIT_DIR / "ui"
PID_FILE = Path("/tmp/ostris.pid")
LOG_FILE = Path("/tmp/ostris.log")
PORT = 9000

app = typer.Typer(help="Ostris AI Toolkit Manager (Web UI)", no_args_is_help=True)
console = Console()

def get_port_process(port):
    """Finds the process listening on a specific port."""
    for conn in psutil.net_connections():
        if conn.laddr.port == port and conn.status == 'LISTEN':
            if conn.pid:
                try:
                    return psutil.Process(conn.pid)
                except psutil.NoSuchProcess:
                    pass
    return None

@app.command()
def start(
    detach: bool = typer.Option(True, "--detach/--foreground", "-d", help="Run in background"),
):
    """Start the AI Toolkit Web UI."""
    # 1. Pre-Flight Check (Port Collision)
    existing_proc = get_port_process(PORT)
    if existing_proc:
        proc_name = existing_proc.name()
        # If it's Node/Next, we are likely already running
        if "node" in proc_name or "next" in proc_name:
            console.print(f"[yellow]⚠️  Ostris is already running (PID: {existing_proc.pid})[/yellow]")
            return
        else:
            # If it's python/comfy, it's a conflict
            console.print(f"[bold red]❌ CRITICAL: Port {PORT} is busy![/bold red]")
            console.print(f"[yellow]Process '{proc_name}' (PID: {existing_proc.pid}) is holding the port.[/yellow]")
            console.print("This is likely ComfyUI or FluxGym. Stop them first.")
            raise typer.Exit(1)

    # 2. Verify Install
    if not UI_DIR.exists():
        console.print(f"[red]❌ Error: AI Toolkit UI not found at {UI_DIR}[/red]")
        raise typer.Exit(1)

    # 3. Patch package.json (Future Proofing)
    pkg_json = UI_DIR / "package.json"
    if pkg_json.exists():
        content = pkg_json.read_text()
        # Check if we need to patch the port
        if "next start --port 8675" in content:
            console.print(f"[cyan]🔧 Patching package.json to force Port {PORT}...[/cyan]")
            content = content.replace("next start --port 8675", f"next start --port {PORT}")
            pkg_json.write_text(content)

    console.print(Panel(f"🚀 Launching Ostris AI-Toolkit\nPath: [dim]{TOOLKIT_DIR}[/dim]\nPort: [bold cyan]{PORT}[/bold cyan]", style="blue"))

    # 4. Activation & Command
    # We use 'setsid' behavior via start_new_session=True to detach fully
    cmd = ["npm", "run", "build_and_start"]
    
    if detach:
        with open(LOG_FILE, "w") as log:
            proc = subprocess.Popen(
                cmd, 
                cwd=UI_DIR, 
                stdout=log, 
                stderr=log, 
                start_new_session=True 
            )
        PID_FILE.write_text(str(proc.pid))
        
        # 5. Wait for Ready State (The Health Check)
        with console.status(f"[bold green]⏳ Waiting for UI on port {PORT}...[/bold green]", spinner="dots"):
            max_retries = 60
            for _ in range(max_retries):
                check = get_port_process(PORT)
                if check:
                    # Verify it's us
                    if "node" in check.name() or "next" in check.name():
                        console.print(f"[green]✅ Ready! Dashboard: http://localhost:{PORT}[/green]")
                        return
                    else:
                        console.print(f"[red]❌ Error: Port hijacked by {check.name()}![/red]")
                        proc.kill()
                        raise typer.Exit(1)
                time.sleep(1)
        
        console.print(f"[red]⚠️  Timed out waiting for port {PORT}. Check logs: {LOG_FILE}[/red]")
    else:
        # Foreground mode
        try:
            subprocess.run(cmd, cwd=UI_DIR)
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping...[/yellow]")

@app.command()
def stop():
    """Stop Ostris (Recursive Supervisor Kill)."""
    target_proc = get_port_process(PORT)
    
    if not target_proc:
        console.print(f"[yellow]No process found on port {PORT}.[/yellow]")
        if PID_FILE.exists(): PID_FILE.unlink()
        return

    console.print(f"[bold red]🛑 Found process: {target_proc.name()} (PID: {target_proc.pid})[/bold red]")

    # RECURSIVE SUPERVISOR KILLER LOGIC
    # Walk up the tree to find 'npm' or 'concurrently' to stop auto-restarts
    to_kill = [target_proc]
    try:
        parent = target_proc.parent()
        while parent:
            name = parent.name()
            cmdline = " ".join(parent.cmdline())
            if "npm" in name or "concurrently" in cmdline or "sh" in name:
                console.print(f"   🔥 Found Supervisor: {name} (PID: {parent.pid})")
                to_kill.append(parent)
                parent = parent.parent()
            else:
                break
    except psutil.NoSuchProcess:
        pass

    # Kill them all
    for p in to_kill:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass

    # Cleanup Python workers (The 'run.py' backend)
    # This ensures no phantom training jobs are left running
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmd = " ".join(proc.cmdline())
            if "python" in proc.name() and "run.py" in cmd and str(TOOLKIT_DIR) in cmd:
                console.print(f"   🧹 Cleaning backend worker: {proc.pid}")
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if PID_FILE.exists(): PID_FILE.unlink()
    console.print("[green]Ostris stopped.[/green]")

@app.command()
def status():
    """Check status (and owner) of Port 9000."""
    proc = get_port_process(PORT)
    
    if proc:
        name = proc.name()
        if "node" in name or "next" in name:
            console.print(Panel(f"✅ [bold green]RUNNING[/bold green]\nPID: {proc.pid}\nApp: Ostris AI-Toolkit\nURL: http://localhost:{PORT}", title="Ostris Status"))
        else:
            console.print(Panel(f"🛑 [bold red]BLOCKED[/bold red]\nPID: {proc.pid}\nApp: [yellow]{name} (ComfyUI?)[/yellow]\nPort {PORT} is busy.", title="Ostris Status"))
    else:
        console.print(Panel("[dim]STOPPED[/dim]\nPort 9000 is free.", title="Ostris Status"))

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
