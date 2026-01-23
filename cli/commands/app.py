
import click
import subprocess
import os
from pathlib import Path
from rich.console import Console

console = Console()

@click.command()
@click.option('--port', default=5173, help='Port to run the web interface on')
def app_cmd(port):
    """Start the HEDGE Interactive Web Interface."""
    web_dir = Path(__file__).parent.parent.parent / "web"
    
    if not web_dir.exists():
        console.print("[bold red]Error: Web directory not found.[/bold red]")
        return

    console.print("[bold green]Starting HEDGE Interactive Web Interface...[/bold green]")
    console.print(f"[dim]Working directory: {web_dir}[/dim]")
    
    try:
        # Check if node_modules exists, if not suggest npm install
        if not (web_dir / "node_modules").exists():
            console.print("[yellow]node_modules not found. Running npm install...[/yellow]")
            subprocess.run(["npm", "install"], cwd=web_dir, check=True)
        
        # Start the dev server
        console.print(f"[cyan]Access the interface at http://localhost:{port}[/cyan]")
        subprocess.run(["npm", "run", "dev", "--", "--port", str(port)], cwd=web_dir)
    except FileNotFoundError:
        console.print("[bold red]Error: 'npm' command not found. Please install Node.js and npm.[/bold red]")
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error: Failed to start the web interface. {e}[/bold red]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Web interface stopped.[/yellow]")
