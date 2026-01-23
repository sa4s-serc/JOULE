"""Project management utilities for HEDGE CLI."""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree

from cli.utils.banner import print_success, print_error, print_info, print_warning

console = Console()

@click.group()
def project_cmd():
    """Project management utilities."""
    pass

@project_cmd.command('init')
@click.argument('name', type=str)
@click.option('--template', type=click.Choice(['basic', 'advanced', 'research']), default='basic', help='Project template')
@click.option('--force', is_flag=True, help='Overwrite existing project')
def init_project(name, template, force):
    """Initialize a new HEDGE optimization project."""
    project_dir = Path(name)
    
    if project_dir.exists() and not force:
        print_error(f"Project directory '{name}' already exists. Use --force to overwrite.")
        return 1
    
    console.print(f"\n[bold cyan]Creating HEDGE Project: {name}[/bold cyan]\n")
    
    # Create project structure
    _create_project_structure(project_dir, template)
    
    # Create project configuration
    _create_project_config(project_dir, name, template)
    
    # Create example files based on template
    _create_template_files(project_dir, template)
    
    print_success(f"Project '{name}' created successfully!")
    console.print(f"\nNext steps:")
    console.print(f"  1. cd {name}")
    console.print(f"  2. Edit src/target.py with your code")
    console.print(f"  3. Edit tests/test_target.py with your tests")
    console.print(f"  4. Run: hedge optimize src/target.py tests/test_target.py")
    
    return 0

@project_cmd.command('status')
@click.option('--project-dir', type=click.Path(path_type=Path), default='.', help='Project directory')
def project_status(project_dir):
    """Show project status and recent experiments."""
    console.print("\n[bold cyan]Project Status[/bold cyan]\n")
    
    # Check if this is a HEDGE project
    config_file = project_dir / ".hedge-project.json"
    if not config_file.exists():
        print_warning("This doesn't appear to be a HEDGE project directory.")
        console.print("Run 'hedge project init <name>' to create a new project.")
        return 1
    
    # Load project config
    with open(config_file) as f:
        config = json.load(f)
    
    # Display project info
    console.print(Panel.fit(
        f"[bold]Project:[/bold] {config['name']}\n"
        f"[bold]Template:[/bold] {config['template']}\n"
        f"[bold]Created:[/bold] {config['created']}\n"
        f"[bold]Last Modified:[/bold] {config.get('last_modified', 'Unknown')}",
        title="Project Information",
        border_style="cyan"
    ))
    
    # Show project structure
    _show_project_tree(project_dir)
    
    # Show recent experiments
    _show_recent_experiments(project_dir)
    
    return 0

@project_cmd.command('clean')
@click.option('--project-dir', type=click.Path(path_type=Path), default='.', help='Project directory')
@click.option('--experiments', is_flag=True, help='Clean experiment results')
@click.option('--cache', is_flag=True, help='Clean cache files')
@click.option('--all', is_flag=True, help='Clean everything')
@click.option('--confirm', is_flag=True, help='Skip confirmation')
def clean_project(project_dir, experiments, cache, all, confirm):
    """Clean project artifacts and temporary files."""
    console.print("\n[bold cyan]Cleaning Project[/bold cyan]\n")
    
    items_to_clean = []
    
    if all or experiments:
        exp_dir = project_dir / "experiments"
        if exp_dir.exists():
            items_to_clean.append(("Experiment results", exp_dir))
    
    if all or cache:
        cache_dirs = [
            project_dir / "__pycache__",
            project_dir / "src" / "__pycache__",
            project_dir / "tests" / "__pycache__",
            project_dir / ".pytest_cache"
        ]
        for cache_dir in cache_dirs:
            if cache_dir.exists():
                items_to_clean.append(("Cache directory", cache_dir))
    
    if all:
        # Add other temporary files
        temp_files = list(project_dir.glob("*.pyc")) + list(project_dir.glob("*_optimized.py"))
        for temp_file in temp_files:
            items_to_clean.append(("Temporary file", temp_file))
    
    if not items_to_clean:
        print_info("Nothing to clean.")
        return 0
    
    # Show what will be cleaned
    console.print("Items to be cleaned:")
    for item_type, item_path in items_to_clean:
        console.print(f"  • {item_type}: {item_path}")
    
    if not confirm:
        if not click.confirm("\nProceed with cleaning?"):
            console.print("Cleaning cancelled.")
            return 0
    
    # Perform cleaning
    cleaned_count = 0
    for item_type, item_path in items_to_clean:
        try:
            if item_path.is_dir():
                shutil.rmtree(item_path)
            else:
                item_path.unlink()
            cleaned_count += 1
        except Exception as e:
            print_error(f"Failed to clean {item_path}: {e}")
    
    print_success(f"Cleaned {cleaned_count} items.")
    return 0

@project_cmd.command('archive')
@click.argument('experiment_id', type=str)
@click.option('--project-dir', type=click.Path(path_type=Path), default='.', help='Project directory')
@click.option('--output', '-o', type=click.Path(path_type=Path), help='Archive output path')
def archive_experiment(experiment_id, project_dir, output):
    """Archive an experiment for long-term storage."""
    console.print(f"\n[bold cyan]Archiving Experiment: {experiment_id}[/bold cyan]\n")
    
    exp_dir = project_dir / "experiments" / experiment_id
    if not exp_dir.exists():
        print_error(f"Experiment '{experiment_id}' not found.")
        return 1
    
    # Create archive
    if not output:
        output = project_dir / "archives" / f"{experiment_id}.tar.gz"
    
    output.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        shutil.make_archive(str(output.with_suffix('')), 'gztar', exp_dir)
        print_success(f"Experiment archived to: {output}")
        
        # Optionally remove original
        if click.confirm("Remove original experiment directory?"):
            shutil.rmtree(exp_dir)
            print_info("Original experiment directory removed.")
        
    except Exception as e:
        print_error(f"Failed to archive experiment: {e}")
        return 1
    
    return 0

def _create_project_structure(project_dir, template):
    """Create the basic project directory structure."""
    dirs_to_create = [
        "src",
        "tests", 
        "experiments",
        "docs",
        "config"
    ]
    
    if template in ['advanced', 'research']:
        dirs_to_create.extend([
            "benchmarks",
            "scripts",
            "notebooks"
        ])
    
    for dir_name in dirs_to_create:
        (project_dir / dir_name).mkdir(parents=True, exist_ok=True)

def _create_project_config(project_dir, name, template):
    """Create project configuration file."""
    config = {
        "name": name,
        "template": template,
        "created": datetime.now().isoformat(),
        "settings": {
            "default_target": "src/target.py",
            "default_tests": "tests/test_target.py",
            "default_level": "standard"
        }
    }
    
    config_file = project_dir / ".hedge-project.json"
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

def _create_template_files(project_dir, template):
    """Create template files based on project type."""
    
    # Basic target file
    target_content = '''def example_function(n):
    """
    Example function to optimize.
    Replace this with your own code.
    """
    result = 0
    for i in range(n):
        result += i * i
    return result

def inefficient_search(items, target):
    """
    Inefficient linear search that HEDGE can optimize.
    """
    found = False
    for i in range(len(items)):
        if items[i] == target:
            found = True
            break
    
    if found:
        return True
    else:
        return False
'''
    
    # Basic test file
    test_content = '''import pytest
from src.target import example_function, inefficient_search

def test_example_function():
    """Test the example function."""
    assert example_function(0) == 0
    assert example_function(1) == 0
    assert example_function(3) == 5  # 0 + 1 + 4
    assert example_function(5) == 30  # 0 + 1 + 4 + 9 + 16

def test_inefficient_search():
    """Test the search function."""
    items = [1, 2, 3, 4, 5]
    assert inefficient_search(items, 3) == True
    assert inefficient_search(items, 6) == False
    assert inefficient_search([], 1) == False
'''
    
    # Write files
    with open(project_dir / "src" / "target.py", 'w') as f:
        f.write(target_content)
    
    with open(project_dir / "tests" / "test_target.py", 'w') as f:
        f.write(test_content)
    
    # Create __init__.py files
    (project_dir / "src" / "__init__.py").touch()
    (project_dir / "tests" / "__init__.py").touch()
    
    # Create README
    readme_content = f'''# {project_dir.name}

HEDGE Optimization Project

## Getting Started

1. Edit `src/target.py` with your code to optimize
2. Edit `tests/test_target.py` with your test cases
3. Run optimization:
   ```bash
   hedge optimize src/target.py tests/test_target.py
   ```

## Project Structure

- `src/` - Source code to optimize
- `tests/` - Test files
- `experiments/` - Optimization results
- `docs/` - Documentation
- `config/` - Configuration files

## Template: {template}

Generated by HEDGE
'''
    
    with open(project_dir / "README.md", 'w') as f:
        f.write(readme_content)
    
    # Template-specific files
    if template == 'advanced':
        _create_advanced_template_files(project_dir)
    elif template == 'research':
        _create_research_template_files(project_dir)

def _create_advanced_template_files(project_dir):
    """Create additional files for advanced template."""
    # Benchmark script
    benchmark_script = '''#!/usr/bin/env python3
"""
Benchmark script for this project.
"""
import subprocess
import sys

def run_benchmark():
    """Run optimization benchmark."""
    cmd = [
        "hedge", "optimize", 
        "src/target.py", "tests/test_target.py",
        "--level", "advanced",
        "--visualize"
    ]
    
    result = subprocess.run(cmd)
    return result.returncode

if __name__ == "__main__":
    sys.exit(run_benchmark())
'''
    
    with open(project_dir / "scripts" / "benchmark.py", 'w') as f:
        f.write(benchmark_script)
    
    # Make it executable
    (project_dir / "scripts" / "benchmark.py").chmod(0o755)

def _create_research_template_files(project_dir):
    """Create additional files for research template."""
    _create_advanced_template_files(project_dir)
    
    # Jupyter notebook template
    notebook_content = '''{
 "cells": [
  {
   "cell_type": "markdown",
   "metadata": {},
   "source": [
    "# HEDGE Optimization Analysis\\n",
    "\\n",
    "This notebook analyzes optimization results from HEDGE."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": null,
   "metadata": {},
   "outputs": [],
   "source": [
    "import json\\n",
    "import pandas as pd\\n",
    "import matplotlib.pyplot as plt\\n",
    "from pathlib import Path"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 4
}'''
    
    with open(project_dir / "notebooks" / "analysis.ipynb", 'w') as f:
        f.write(notebook_content)

def _show_project_tree(project_dir):
    """Display project directory tree."""
    tree = Tree(f"[bold cyan]{project_dir.name}/[/bold cyan]")
    
    for item in sorted(project_dir.iterdir()):
        if item.name.startswith('.'):
            continue
        
        if item.is_dir():
            dir_tree = tree.add(f"[blue]{item.name}/[/blue]")
            # Show first level of subdirectories
            try:
                for subitem in sorted(item.iterdir()):
                    if subitem.is_dir():
                        dir_tree.add(f"[dim blue]{subitem.name}/[/dim blue]")
                    else:
                        dir_tree.add(f"[dim]{subitem.name}[/dim]")
            except PermissionError:
                dir_tree.add("[dim red]Permission denied[/dim red]")
        else:
            tree.add(f"[green]{item.name}[/green]")
    
    console.print(tree)

def _show_recent_experiments(project_dir):
    """Show recent experiments."""
    exp_dir = project_dir / "experiments"
    if not exp_dir.exists():
        return
    
    experiments = []
    for exp_path in exp_dir.iterdir():
        if exp_path.is_dir():
            config_file = exp_path / "config.json"
            if config_file.exists():
                try:
                    with open(config_file) as f:
                        config = json.load(f)
                    experiments.append({
                        'name': exp_path.name,
                        'timestamp': config.get('timestamp', 'Unknown'),
                        'level': config.get('level', 'Unknown'),
                        'generations': config.get('generations', 'Unknown')
                    })
                except:
                    pass
    
    if experiments:
        console.print("\n[bold]Recent Experiments:[/bold]")
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Experiment", style="yellow")
        table.add_column("Timestamp", style="dim")
        table.add_column("Level", style="green")
        table.add_column("Generations", style="blue")
        
        # Sort by timestamp and show last 5
        experiments.sort(key=lambda x: x['timestamp'], reverse=True)
        for exp in experiments[:5]:
            table.add_row(
                exp['name'],
                exp['timestamp'][:19] if len(exp['timestamp']) > 19 else exp['timestamp'],
                exp['level'],
                str(exp['generations'])
            )
        
        console.print(table)
    else:
        console.print("\n[dim]No experiments found.[/dim]")