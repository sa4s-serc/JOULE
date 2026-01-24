"""Configuration management command for HEDGE CLI."""

import os
import json
import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from cli.utils.banner import print_success, print_error, print_info, print_warning
from src.utils.config import (
    load_config, merge_config, save_config, 
    GLOBAL_CONFIG as CONFIG_FILE, get_default_config
)

DEFAULT_CONFIG = get_default_config()

console = Console()


@click.group()
def config_cmd():
    """Manage HEDGE configuration settings."""
    pass

@config_cmd.command('show')
@click.option('--section', type=str, help='Show specific configuration section')
def show_config(section):
    """Show current configuration."""
    console.print("\n[bold cyan]HEDGE Configuration[/bold cyan]\n")
    
    config = load_config()
    
    if section:
        if section in config:
            _display_config_section(section, config[section])
        else:
            print_error(f"Configuration section '{section}' not found")
            return 1
    else:
        _display_full_config(config)
    
    return 0

@config_cmd.command('set')
@click.argument('key', type=str)
@click.argument('value', type=str)
def set_config(key, value):
    """Set a configuration value."""
    config = load_config()
    
    # Parse nested key (e.g., "llm.default_provider")
    keys = key.split('.')
    current = config
    
    # Navigate to the parent of the target key
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]
    
    # Convert value to appropriate type
    parsed_value = _parse_value(value)
    current[keys[-1]] = parsed_value
    
    # Save configuration
    save_config(config)
    
    print_success(f"Set {key} = {parsed_value}")
    return 0

@config_cmd.command('get')
@click.argument('key', type=str)
def get_config(key):
    """Get a configuration value."""
    config = load_config()
    
    # Parse nested key
    keys = key.split('.')
    current = config
    
    try:
        for k in keys:
            current = current[k]
        console.print(f"[cyan]{key}[/cyan] = [green]{current}[/green]")
    except KeyError:
        print_error(f"Configuration key '{key}' not found")
        return 1
    
    return 0

@config_cmd.command('reset')
@click.option('--confirm', is_flag=True, help='Skip confirmation prompt')
def reset_config(confirm):
    """Reset configuration to defaults."""
    if not confirm:
        if not click.confirm("This will reset all configuration to defaults. Continue?"):
            console.print("Configuration reset cancelled.")
            return 0
    
    save_config(DEFAULT_CONFIG)
    print_success("Configuration reset to defaults")
    return 0

@config_cmd.command('init')
def init_config():
    """Initialize configuration with guided setup."""
    console.print("\n[bold cyan]HEDGE Configuration Setup[/bold cyan]")
    console.print("[dim]Configure HEDGE for optimal performance.[/dim]\n")
    
    config = load_config()
    
    # Welcome and overview
    console.print(Panel(
        "[bold]Welcome to HEDGE Setup[/bold]\n\n"
        "This wizard will help you configure:\n"
        "• LLM integration for advanced optimization\n"
        "• Default optimization settings\n"
        "• Output and visualization preferences\n"
        "• User interface options",
        title="Setup Overview",
        border_style="cyan"
    ))
    
    # LLM Configuration
    console.print("\n[bold]LLM Configuration[/bold]")
    console.print("[dim]Configure AI integration for semantic-level optimizations[/dim]")
    
    provider = click.prompt(
        "Default LLM provider",
        type=click.Choice(['openai', 'gemini']),
        default=config['llm']['default_provider'],
        show_choices=True
    )
    config['llm']['default_provider'] = provider
    
    # Initialize provider section if missing
    if provider not in config['llm']:
        config['llm'][provider] = {}
    
    # Check for API keys with helpful guidance
    if provider == 'openai':
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print_warning("OPENAI_API_KEY not found in environment")
            console.print("To enable advanced features, add to your .env file:")
            console.print("   [cyan]OPENAI_API_KEY=your-key-here[/cyan]")
            console.print("   Get your key at: https://platform.openai.com/api-keys")
        else:
            print_success("OpenAI API key found!")
    elif provider == 'gemini':
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print_warning("GEMINI_API_KEY not found in environment")
            console.print("To enable advanced features, add to your .env file:")
            console.print("   [cyan]GEMINI_API_KEY=your-key-here[/cyan]")
            console.print("   Get your key at: https://makersuite.google.com/app/apikey")
        else:
            print_success("Gemini API key found!")
    
    # Optimization defaults
    console.print("\n[bold]Optimization Defaults[/bold]")
    console.print("[dim]Set your preferred optimization settings[/dim]")
    
    level = click.prompt(
        "Default optimization level",
        type=click.Choice(['micro', 'basic', 'standard', 'advanced', 'aggressive']),
        default=config['optimization']['default_level'],
        show_choices=True
    )
    config['optimization']['default_level'] = level
    
    # Show level explanation
    level_descriptions = {
        'micro': 'Fast, safe optimizations (constant folding, dead code)',
        'basic': 'Micro + Python idioms and patterns',
        'standard': 'Basic + algorithmic improvements (recommended)',
        'advanced': 'Standard + AI-powered semantic optimization',
        'aggressive': 'All optimizations enabled (experimental)'
    }
    console.print(f"   {level_descriptions[level]}")
    
    generations = click.prompt(
        "Default generations",
        type=int,
        default=config['optimization']['default_generations']
    )
    config['optimization']['default_generations'] = generations
    
    # Output preferences
    console.print("\n[bold]Output Preferences[/bold]")
    console.print("[dim]Configure visualization and output settings[/dim]")
    
    auto_viz = click.confirm(
        "Auto-generate visualizations after optimization?",
        default=config['output']['auto_visualize']
    )
    config['output']['auto_visualize'] = auto_viz
    
    theme = click.prompt(
        "Visualization theme",
        type=click.Choice(['light', 'dark', 'auto']),
        default=config.get('ui', {}).get('theme', 'auto'),
        show_choices=True
    )
    if 'ui' not in config:
        config['ui'] = {}
    config['ui']['theme'] = theme
    
    # Save configuration to global config by default
    save_config(config)
    
    # Success summary
    console.print("\n" + "="*60)
    print_success("Configuration initialized successfully!")
    console.print(f"Configuration saved to: [cyan]{CONFIG_FILE}[/cyan]")
    
    # Show next steps
    console.print(Panel(
        "[bold]Next Steps:[/bold]\n\n"
        "1. Try optimizing code:\n"
        f"   [cyan]hedge optimize examples/target_fib.py examples/test_target_fib.py[/cyan]\n\n"
        "2. Create a new project:\n"
        "   [cyan]hedge project init my_optimization_project[/cyan]\n\n"
        "3. Run benchmarks:\n"
        "   [cyan]hedge benchmark --quick[/cyan]\n\n"
        "4. View your configuration:\n"
        "   [cyan]hedge config show[/cyan]",
        title="Ready to Optimize",
        border_style="green"
    ))
    
    return 0

@config_cmd.command('validate')
def validate_config():
    """Validate current configuration."""
    console.print("\n[bold cyan]Validating Configuration[/bold cyan]\n")
    
    config = load_config()
    issues = []
    
    # Validate LLM configuration
    provider = config['llm']['default_provider']
    api_key_var = f"{provider.upper()}_API_KEY"
    
    if not os.getenv(api_key_var):
        issues.append(f"Missing environment variable: {api_key_var}")
    
    # Validate paths
    exp_dir = Path(config['output']['experiment_base_dir'])
    if not exp_dir.exists():
        try:
            exp_dir.mkdir(parents=True, exist_ok=True)
            print_info(f"Created experiment directory: {exp_dir}")
        except Exception as e:
            issues.append(f"Cannot create experiment directory: {e}")
    
    # Validate numeric values
    if config['optimization']['default_generations'] < 1:
        issues.append("default_generations must be >= 1")
    
    if config['optimization']['default_population_size'] < 1:
        issues.append("default_population_size must be >= 1")
    
    if config['optimization']['default_timeout'] < 5:
        issues.append("default_timeout should be >= 5 seconds")
    
    # Display results
    if issues:
        console.print("[bold red]Configuration Issues Found:[/bold red]")
        for issue in issues:
            console.print(f"  • {issue}")
        return 1
    else:
        print_success("Configuration is valid!")
        return 0

def _parse_value(value_str):
    """Parse string value to appropriate type."""
    # Try boolean
    if value_str.lower() in ('true', 'false'):
        return value_str.lower() == 'true'
    
    # Try integer
    try:
        return int(value_str)
    except ValueError:
        pass
    
    # Try float
    try:
        return float(value_str)
    except ValueError:
        pass
    
    # Return as string
    return value_str

def _display_full_config(config):
    """Display the full configuration."""
    for section_name, section_data in config.items():
        _display_config_section(section_name, section_data)
        console.print()

def _display_config_section(section_name, section_data):
    """Display a configuration section."""
    table = Table(title=f"{section_name.title()} Configuration", 
                  show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="yellow")
    table.add_column("Value", style="green")
    
    for key, value in section_data.items():
        table.add_row(key, str(value))
    
    console.print(table)