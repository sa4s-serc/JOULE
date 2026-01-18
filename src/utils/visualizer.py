"""
Comprehensive Visualization Suite for HEDGE

Generates charts, graphs, and HTML reports from optimization results.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ResultVisualizer:
    """
    Creates visualizations from HEDGE optimization results.
    
    Generates:
    - Pareto front plots
    - Evolution progress charts
    - Mutation effectiveness graphs
    - Energy/time improvement charts
    - Interactive HTML reports
    """
    
    def __init__(self, results_dir: Path):
        """
        Initialize visualizer.
        
        Args:
            results_dir: Directory containing experiment results
        """
        self.results_dir = Path(results_dir)
        self.output_dir = self.results_dir / "visualizations"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initializing visualizer for {results_dir}")
    
    def generate_all(self):
        """Generate all visualizations."""
        logger.info("Generating all visualizations...")
        
        try:
            # Generate individual plots
            self.generate_pareto_front()
            self.generate_evolution_progress()
            self.generate_mutation_effectiveness()
            self.generate_metrics_comparison()
            self.generate_metrics_history()
            
            # Generate HTML report
            self.generate_comprehensive_report()
            
            logger.info(f"✓ All visualizations saved to {self.output_dir}")
        except Exception as e:
            logger.error(f"Failed to generate visualizations: {e}")
    
    def generate_pareto_front(self):
        """Generate Pareto front scatter plot."""
        try:
            import matplotlib.pyplot as plt
            
            # Load results
            results_file = self.results_dir / "pareto_results.json"
            if not results_file.exists():
                logger.warning("No pareto_results.json found, skipping Pareto front plot")
                return
            
            with open(results_file) as f:
                results = json.load(f)
            
            # Extract metrics
            energies = [r['metrics'].get('energy_joules', 0) for r in results]
            times = [r['metrics'].get('duration_seconds', 0) for r in results]
            mutations = [r['mutation'] for r in results]
            
            # Create figure
            plt.figure(figsize=(10, 6))
            scatter = plt.scatter(energies, times, c=range(len(energies)), 
                                 cmap='viridis', s=100, alpha=0.6, edgecolors='black', zorder=2)
            
            # Add trajectory path to show movement
            if len(energies) > 1:
                plt.plot(energies, times, color='gray', alpha=0.3, linestyle='--', zorder=1, label='Optimization Path')
                
                # Mark Start and Current Best
                plt.scatter(energies[0], times[0], c='red', s=150, marker='X', label='Initial', zorder=3)
                
                # Find best energy solution
                min_energy = min(energies)
                best_idx = energies.index(min_energy)
                plt.scatter(energies[best_idx], times[best_idx], c='lime', s=150, marker='*', label='Best Energy', zorder=3)
                
                plt.legend()
            
            # Annotations
            for i, (e, t, m) in enumerate(zip(energies, times, mutations)):
                plt.annotate(f"{i}", (e, t), fontsize=8, ha='center')
            
            plt.xlabel('Energy (Joules)', fontsize=12)
            plt.ylabel('Time (Seconds)', fontsize=12)
            plt.title('Pareto Front - Energy vs Time Trade-off', fontsize=14, fontweight='bold')
            plt.grid(True, alpha=0.3)
            plt.colorbar(scatter, label='Solution Index')
            
            # Save
            output_file = self.output_dir / "pareto_front.png"
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"✓ Pareto front plot saved to {output_file}")
        except ImportError:
            logger.warning("matplotlib not installed, skipping plots")
        except Exception as e:
            logger.error(f"Failed to generate Pareto front: {e}")
    
    def generate_evolution_progress(self):
        """Generate evolution progress over generations."""
        try:
            import matplotlib.pyplot as plt
            
            stats_file = self.results_dir / "statistics.json"
            if not stats_file.exists():
                logger.warning("No statistics.json found, skipping progress plot")
                return
            
            with open(stats_file) as f:
                stats = json.load(f)
            
            # Create figure
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
            
            # Plot success rate
            ax1.bar(['Total', 'Successful', 'Failed Val', 'Failed Exec'], 
                   [stats.get('total_mutations', 0),
                    stats.get('successful_mutations', 0),
                    stats.get('failed_validations', 0),
                    stats.get('failed_executions', 0)],
                   color=['#3498db', '#2ecc71', '#e74c3c', '#f39c12'])
            ax1.set_ylabel('Count')
            ax1.set_title('Mutation Statistics')
            ax1.grid(axis='y', alpha=0.3)
            
            # Plot rates
            success_rate = float(stats.get('success_rate', '0').rstrip('%'))
            improvement_rate = float(stats.get('improvement_rate', '0').rstrip('%'))
            
            ax2.bar(['Success Rate', 'Improvement Rate'], 
                   [success_rate, improvement_rate],
                   color=['#27ae60', '#8e44ad'])
            ax2.set_ylabel('Percentage (%)')
            ax2.set_title('Performance Metrics')
            ax2.set_ylim(0, 100)
            ax2.grid(axis='y', alpha=0.3)
            
            plt.tight_layout()
            output_file = self.output_dir / "evolution_progress.png"
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"✓ Evolution progress plot saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to generate evolution progress: {e}")
    
    def generate_mutation_effectiveness(self):
        """Generate mutation strategy effectiveness chart."""
        try:
            import matplotlib.pyplot as plt
            from collections import Counter
            
            results_file = self.results_dir / "pareto_results.json"
            if not results_file.exists():
                return
            
            with open(results_file) as f:
                results = json.load(f)
            
            # Count mutations by type
            mutation_counts = Counter(r['mutation'] for r in results)
            
            # Create pie chart
            plt.figure(figsize=(10, 6))
            colors = plt.cm.Set3(range(len(mutation_counts)))
            plt.pie(mutation_counts.values(), labels=mutation_counts.keys(), 
                   autopct='%1.1f%%', colors=colors, startangle=90)
            plt.title('Mutation Strategy Distribution in Pareto Front', 
                     fontsize=14, fontweight='bold')
            
            output_file = self.output_dir / "mutation_effectiveness.png"
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"✓ Mutation effectiveness chart saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to generate mutation effectiveness: {e}")
    
    def generate_metrics_comparison(self):
        """Generate metrics comparison bar chart."""
        try:
            import matplotlib.pyplot as plt
            import numpy as np
            
            results_file = self.results_dir / "pareto_results.json"
            if not results_file.exists():
                return
            
            with open(results_file) as f:
                results = json.load(f)
            
            if len(results) < 2:
                logger.info("Not enough solutions for comparison")
                return
            
            # Get baseline (first solution) and best (min energy)
            baseline = results[0]
            best = min(results[1:], key=lambda r: r['metrics'].get('energy_joules', float('inf')))
            
            baseline_energy = baseline['metrics'].get('energy_joules', 0)
            baseline_time = baseline['metrics'].get('duration_seconds', 0)
            best_energy = best['metrics'].get('energy_joules', 0)
            best_time = best['metrics'].get('duration_seconds', 0)
            
            # Create comparison
            fig, ax = plt.subplots(figsize=(10, 6))
            
            x = np.arange(2)
            width = 0.35
            
            ax.bar(x - width/2, [baseline_energy, best_energy], width, 
                  label='Energy (J)', color='#e74c3c', alpha=0.8)
            ax.bar(x + width/2, [baseline_time, best_time], width, 
                  label='Time (s)', color='#3498db', alpha=0.8)
            
            ax.set_xlabel('Solution')
            ax.set_ylabel('Value')
            ax.set_title('Baseline vs Best Solution Metrics', fontsize=14, fontweight='bold')
            ax.set_xticks(x)
            ax.set_xticklabels(['Baseline', 'Best'])
            ax.legend()
            ax.grid(axis='y', alpha=0.3)
            
            # Add improvement percentage
            energy_improvement = ((baseline_energy - best_energy) / baseline_energy * 100) if baseline_energy > 0 else 0
            time_improvement = ((baseline_time - best_time) / baseline_time * 100) if baseline_time > 0 else 0
            
            plt.text(0.5, 0.95, f'Energy ↓{energy_improvement:.1f}%  |  Time ↓{time_improvement:.1f}%',
                    ha='center', transform=ax.transAxes, fontsize=12, 
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            
            output_file = self.output_dir / "metrics_comparison.png"
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"✓ Metrics comparison chart saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to generate metrics comparison: {e}")
    
    def generate_metrics_history(self):
        """Generate metrics history over iterations."""
        try:
            import matplotlib.pyplot as plt
            
            results_file = self.results_dir / "pareto_results.json"
            if not results_file.exists():
                return
            
            with open(results_file) as f:
                results = json.load(f)
                
            iterations = range(1, len(results) + 1)
            energies = [r['metrics'].get('energy_joules', 0) for r in results]
            times = [r['metrics'].get('duration_seconds', 0) for r in results]
            
            # Create figure with secondary y-axis
            fig, ax1 = plt.subplots(figsize=(12, 6))
            
            # Plot Energy
            color = '#e74c3c'  # Red
            ax1.set_xlabel('Iteration/Generation')
            ax1.set_ylabel('Energy (Joules)', color=color, fontweight='bold')
            l1 = ax1.plot(iterations, energies, color=color, marker='o', label='Energy', alpha=0.8)
            ax1.tick_params(axis='y', labelcolor=color)
            ax1.grid(True, alpha=0.3)
            
            # Plot Time
            ax2 = ax1.twinx()
            color = '#3498db'  # Blue
            ax2.set_ylabel('Time (Seconds)', color=color, fontweight='bold')
            l2 = ax2.plot(iterations, times, color=color, marker='s', linestyle='--', label='Time', alpha=0.8)
            ax2.tick_params(axis='y', labelcolor=color)
            
            # Combine legends
            lns = l1 + l2
            labs = [l.get_label() for l in lns]
            ax1.legend(lns, labs, loc='upper right')
            
            plt.title('Metrics Improvement Over Generations', fontsize=14, fontweight='bold')
            
            output_file = self.output_dir / "metrics_history.png"
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"✓ Metrics history chart saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to generate metrics history: {e}")
    
    def generate_comprehensive_report(self):
        """Generate comprehensive HTML report."""
        try:
            # Load all data
            results_file = self.results_dir / "pareto_results.json"
            stats_file = self.results_dir / "statistics.json"
            
            results = []
            stats = {}
            
            if results_file.exists():
                with open(results_file) as f:
                    results = json.load(f)
            
            if stats_file.exists():
                with open(stats_file) as f:
                    stats = json.load(f)
            
            # Generate HTML
            html = self._generate_html_content(results, stats)
            
            output_file = self.output_dir / "report.html"
            with open(output_file, 'w') as f:
                f.write(html)
            
            logger.info(f"✓ HTML report saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to generate HTML report: {e}")
    
    def _generate_html_content(self, results: List[Dict], stats: Dict) -> str:
        """Generate HTML content for report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate improvements
        baseline_energy = results[0]['metrics'].get('energy_joules', 0) if results else 0
        best_energy = min((r['metrics'].get('energy_joules', float('inf')) for r in results[1:]), default=baseline_energy) if len(results) > 1 else baseline_energy
        energy_improvement = ((baseline_energy - best_energy) / baseline_energy * 100) if baseline_energy > 0 else 0
        
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HEDGE Optimization Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header .subtitle {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .content {{
            padding: 40px;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .metric-card {{
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .metric-card .label {{
            font-size: 0.9em;
            color: #666;
            margin-bottom: 10px;
        }}
        .metric-card .value {{
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }}
        .metric-card .improvement {{
            font-size: 1.2em;
            color: #27ae60;
            margin-top: 10px;
        }}
        .section {{
            margin-bottom: 40px;
        }}
        .section h2 {{
            font-size: 1.8em;
            margin-bottom: 20px;
            color: #333;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }}
        .visualization {{
            margin: 20px 0;
            text-align: center;
        }}
        .visualization img {{
            max-width: 100%;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #667eea;
            color: white;
            font-weight: bold;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #666;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 HEDGE Optimization Report</h1>
            <div class="subtitle">Generated: {timestamp}</div>
        </div>
        
        <div class="content">
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="label">Total Solutions</div>
                    <div class="value">{len(results)}</div>
                </div>
                <div class="metric-card">
                    <div class="label">Success Rate</div>
                    <div class="value">{stats.get('success_rate', 'N/A')}</div>
                </div>
                <div class="metric-card">
                    <div class="label">Energy Improvement</div>
                    <div class="value">↓{energy_improvement:.1f}%</div>
                    <div class="improvement">✓ Optimized</div>
                </div>
                <div class="metric-card">
                    <div class="label">Cache Hits</div>
                    <div class="value">{stats.get('cache_hits', 0)}</div>
                </div>
            </div>
            
            <div class="section">
                <h2>📊 Visualizations</h2>
                <div class="visualization">
                    <h3>Pareto Front</h3>
                    <img src="pareto_front.png" alt="Pareto Front">
                </div>
                <div class="visualization">
                    <h3>Evolution Progress</h3>
                    <img src="evolution_progress.png" alt="Evolution Progress">
                </div>
                <div class="visualization">
                    <h3>Mutation Effectiveness</h3>
                    <img src="mutation_effectiveness.png" alt="Mutation Effectiveness">
                </div>
                <div class="visualization">
                    <h3>Metrics Comparison</h3>
                    <img src="metrics_comparison.png" alt="Metrics Comparison">
                </div>
                <div class="visualization">
                    <h3>History & Improvement</h3>
                    <img src="metrics_history.png" alt="Metrics History">
                </div>
            </div>
            
            <div class="section">
                <h2>📋 Detailed Results</h2>
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Mutation Type</th>
                            <th>Energy (J)</th>
                            <th>Time (s)</th>
                            <th>Code Size</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(f'''
                        <tr>
                            <td>{i+1}</td>
                            <td>{r['mutation']}</td>
                            <td>{r['metrics'].get('energy_joules', 'N/A'):.4f}</td>
                            <td>{r['metrics'].get('duration_seconds', 'N/A'):.4f}</td>
                            <td>{len(r.get('code', ''))} chars</td>
                        </tr>
                        ''' for i, r in enumerate(results))}
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="footer">
            <p>Generated by HEDGE - Hierarchical Evolutionary Darwin-Green Engine</p>
            <p>IR-Only Optimization System | State-of-the-Art Implementation</p>
        </div>
    </div>
</body>
</html>
"""
        return html
