import click
import uvicorn
from rich.console import Console

console = Console()


@click.command()
@click.option("--port", default=8000, help="Port to run the server on")
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload")
def serve_cmd(port, host, reload):
    """Start the HEDGE API server."""
    console.print(f"[bold green]Starting HEDGE API server on http://{host}:{port}[/bold green]")
    uvicorn.run("api.main:app", host=host, port=port, reload=reload)
