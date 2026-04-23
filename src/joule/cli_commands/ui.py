from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from joule.config import load_settings


def run_ui(
    path: Path = typer.Argument(..., help="Path to project root"),
    host: str = typer.Option("127.0.0.1", "--host", help="UI server host"),
    port: Optional[int] = typer.Option(None, "--port", help="UI server port"),
    backend_only: bool = typer.Option(False, "--backend-only", help="Start only the backend API server"),
    frontend_only: bool = typer.Option(False, "--frontend-only", help="Start only the frontend dev server"),
    verbose: bool = typer.Option(False, "--verbose", help="Print detailed events"),
    quiet: bool = typer.Option(False, "--quiet", help="Reduce terminal output"),
) -> None:
    """Launch the JOULE web interface."""
    console = Console()
    
    try:
        # Load settings to get default port
        settings = load_settings(path)
        default_port = settings.dashboard_port if port is None else port
        
        if backend_only and frontend_only:
            console.print("[red]Error: Cannot specify both --backend-only and --frontend-only[/red]")
            raise typer.Exit(1)
        
        # Get the web UI directory
        current_file = Path(__file__)
        web_ui_dir = current_file.parent.parent / "web_ui"
        backend_dir = web_ui_dir / "backend"
        frontend_dir = web_ui_dir / "frontend"
        
        if not backend_dir.exists():
            console.print(f"[red]Error: Web UI backend not found at {backend_dir}[/red]")
            console.print("[yellow]Please ensure the web UI is properly installed.[/yellow]")
            raise typer.Exit(1)
        
        if not frontend_only and not frontend_dir.exists():
            console.print(f"[red]Error: Web UI frontend not found at {frontend_dir}[/red]")
            console.print("[yellow]Please ensure the web UI is properly installed.[/yellow]")
            raise typer.Exit(1)
        
        # Start servers
        processes = []
        
        try:
            if not frontend_only:
                # Start backend server
                console.print(f"[blue]Starting JOULE API server on {host}:{default_port}...[/blue]")
                backend_cmd = [
                    sys.executable, "-m", "uvicorn",
                    "main:app",
                    "--host", host,
                    "--port", str(default_port),
                    "--reload" if verbose else "",
                ]
                backend_cmd = [cmd for cmd in backend_cmd if cmd]  # Remove empty strings
                
                backend_process = subprocess.Popen(
                    backend_cmd,
                    cwd=backend_dir,
                    stdout=subprocess.PIPE if quiet else None,
                    stderr=subprocess.PIPE if quiet else None,
                )
                processes.append(("backend", backend_process))
                
                if not quiet:
                    console.print(f"[green]✓ API server started at http://{host}:{default_port}[/green]")
            
            if not backend_only:
                # Check if frontend dependencies are installed
                node_modules = frontend_dir / "node_modules"
                if not node_modules.exists():
                    if not quiet:
                        console.print("[yellow]Installing frontend dependencies...[/yellow]")
                    install_process = subprocess.run(
                        ["npm", "install"],
                        cwd=frontend_dir,
                        capture_output=quiet,
                    )
                    if install_process.returncode != 0:
                        console.print("[red]Error: Failed to install frontend dependencies[/red]")
                        raise typer.Exit(1)
                
                # Start frontend dev server
                frontend_port = 3000  # Default frontend port
                console.print(f"[blue]Starting frontend dev server on port {frontend_port}...[/blue]")
                
                frontend_cmd = ["npm", "run", "dev"]
                frontend_process = subprocess.Popen(
                    frontend_cmd,
                    cwd=frontend_dir,
                    stdout=subprocess.PIPE if quiet else None,
                    stderr=subprocess.PIPE if quiet else None,
                )
                processes.append(("frontend", frontend_process))
                
                if not quiet:
                    console.print(f"[green]✓ Frontend server started at http://localhost:{frontend_port}[/green]")
            
            if not quiet:
                console.print("\n[bold green]JOULE Web UI is running![/bold green]")
                if not backend_only:
                    console.print(f"🌐 Frontend: [link]http://localhost:3000[/link]")
                if not frontend_only:
                    console.print(f"🔧 Backend API: [link]http://{host}:{default_port}[/link]")
                console.print("\n[yellow]Press Ctrl+C to stop the servers[/yellow]")
            
            # Wait for processes
            try:
                for name, process in processes:
                    process.wait()
            except KeyboardInterrupt:
                if not quiet:
                    console.print("\n[yellow]Stopping servers...[/yellow]")
                for name, process in processes:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                
                if not quiet:
                    console.print("[green]✓ All servers stopped[/green]")
        
        except Exception as e:
            # Clean up processes on error
            for name, process in processes:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except:
                    process.kill()
            raise e
            
    except Exception as e:
        console.print(f"[red]Error starting web UI: {e}[/red]")
        raise typer.Exit(1)
