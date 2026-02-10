#!/usr/bin/env python3
"""
Comprehensive Visualization Generator for EvoEval Benchmark Results

Creates detailed charts, graphs, and analysis visualizations from benchmark results.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from datetime import datetime

# Try to import seaborn for better styling
try:
    import seaborn as sns
    sns.set_style("whitegrid")
    sns.set_palette("husl")
    SEABORN_AVAILABLE = True
except ImportError:
    SEABORN_AVAILABLE = False
    print("Warning: seaborn not available. Install with: pip install seaborn")


class EvoEvalVisualizer:
    """Generate comprehensive visualizations for EvoEval benchmark results."""
    
    def __init__(self, results_dir: Path):
        self.results_dir = Path(results_dir)
        self.results_file = self.results_dir / "benchmark_results.json"
        
        if not self.results_file.exists():
            raise FileNotFoundError(f"Results file not found: {self.results_file}")
        
        with open(self.results_file) as f:
            self.data = json.load(f)
        
        self.viz_dir = self.results_dir / "visualizations"
        self.viz_dir.mkdir(exist_ok=True)
    
    def generate_all_visualizations(self):
        """Generate all visualization types."""
        print("Generating comprehensive visualizations...")
        
        self.plot_improvement_comparison()
        self.plot_pareto_solutions_distribution()
        self.plot_execution_time_analysis()
        self.plot_success_rate_by_problem()
        self.plot_latency_comparison()
        self.plot_mutation_statistics()
        self.generate_summary_dashboard()
        
        print(f"\n✓ All visualizations saved to: {self.viz_dir}")
    
    def plot_improvement_comparison(self):
        """Bar chart comparing improvements across problems."""
        fig, ax = plt.subplots(figsize=(14, 8))
        
        problems = []
        improvements = []
        colors = []
        
        for problem, data in self.data["results"].items():
            if data.get("status") == "success" and "improvement_percent" in data:
                problems.append(problem.replace("EvoEval_difficult_", "P"))
                improvements.append(data["improvement_percent"])
                
                # Color code by improvement level
                imp = data["improvement_percent"]
                if imp >= 50:
                    colors.append('#2ecc71')  # Green
                elif imp >= 25:
                    colors.append('#f39c12')  # Orange
                elif imp >= 10:
                    colors.append('#3498db')  # Blue
                else:
                    colors.append('#95a5a6')  # Gray
        
        bars = ax.bar(problems, improvements, color=colors, edgecolor='black', linewidth=1.5)
        
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}%',
                   ha='center', va='bottom', fontweight='bold', fontsize=10)
        
        ax.set_xlabel('Problem', fontsize=14, fontweight='bold')
        ax.set_ylabel('Performance Improvement (%)', fontsize=14, fontweight='bold')
        ax.set_title('HEDGE Performance Improvements on EvoEval Benchmark', 
                    fontsize=16, fontweight='bold', pad=20)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        # Add legend
        legend_elements = [
            mpatches.Patch(color='#2ecc71', label='Excellent (≥50%)'),
            mpatches.Patch(color='#f39c12', label='Good (25-50%)'),
            mpatches.Patch(color='#3498db', label='Moderate (10-25%)'),
            mpatches.Patch(color='#95a5a6', label='Minor (<10%)')
        ]
        ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
        
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(self.viz_dir / "improvement_comparison.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        print("✓ Generated: improvement_comparison.png")
    
    def plot_pareto_solutions_distribution(self):
        """Distribution of Pareto solutions found per problem."""
        fig, ax = plt.subplots(figsize=(14, 8))
        
        problems = []
        pareto_counts = []
        
        for problem, data in self.data["results"].items():
            if data.get("status") == "success":
                problems.append(problem.replace("EvoEval_difficult_", "P"))
                pareto_counts.append(data.get("pareto_count", 0))
        
        bars = ax.bar(problems, pareto_counts, color='#3498db', edgecolor='black', linewidth=1.5)
        
        # Add value labels
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height)}',
                   ha='center', va='bottom', fontweight='bold', fontsize=10)
        
        ax.set_xlabel('Problem', fontsize=14, fontweight='bold')
        ax.set_ylabel('Number of Pareto-Optimal Solutions', fontsize=14, fontweight='bold')
        ax.set_title('Pareto-Optimal Solutions Found per Problem', 
                    fontsize=16, fontweight='bold', pad=20)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        # Add average line
        if pareto_counts:
            avg_pareto = np.mean(pareto_counts)
            ax.axhline(y=avg_pareto, color='red', linestyle='--', linewidth=2, 
                      label=f'Average: {avg_pareto:.1f}')
            ax.legend(fontsize=12)
        
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(self.viz_dir / "pareto_distribution.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        print("✓ Generated: pareto_distribution.png")
    
    def plot_execution_time_analysis(self):
        """Execution time analysis."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        
        problems = []
        exec_times = []
        
        for problem, data in self.data["results"].items():
            if "execution_time" in data:
                problems.append(problem.replace("EvoEval_difficult_", "P"))
                exec_times.append(data["execution_time"])
        
        # Bar chart
        bars = ax1.bar(problems, exec_times, color='#9b59b6', edgecolor='black', linewidth=1.5)
        
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}s',
                    ha='center', va='bottom', fontweight='bold', fontsize=9)
        
        ax1.set_xlabel('Problem', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Execution Time (seconds)', fontsize=12, fontweight='bold')
        ax1.set_title('Optimization Time per Problem', fontsize=14, fontweight='bold')
        ax1.grid(axis='y', alpha=0.3, linestyle='--')
        ax1.tick_params(axis='x', rotation=45)
        
        # Pie chart for time distribution
        if exec_times:
            total_time = sum(exec_times)
            percentages = [(t/total_time)*100 for t in exec_times]
            
            # Only show top 5 and group others
            if len(problems) > 5:
                sorted_data = sorted(zip(problems, percentages), key=lambda x: x[1], reverse=True)
                top_5 = sorted_data[:5]
                others_sum = sum(p for _, p in sorted_data[5:])
                
                pie_labels = [p for p, _ in top_5]
                pie_values = [pct for _, pct in top_5]
                
                if others_sum > 0:
                    pie_labels.append('Others')
                    pie_values.append(others_sum)
            else:
                pie_labels = problems
                pie_values = percentages
            
            colors_pie = plt.cm.Set3(np.linspace(0, 1, len(pie_labels)))
            wedges, texts, autotexts = ax2.pie(pie_values, labels=pie_labels, autopct='%1.1f%%',
                                                colors=colors_pie, startangle=90)
            
            for autotext in autotexts:
                autotext.set_color('white')
                autotext.set_fontweight('bold')
                autotext.set_fontsize(10)
            
            ax2.set_title('Time Distribution Across Problems', fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(self.viz_dir / "execution_time_analysis.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        print("✓ Generated: execution_time_analysis.png")
    
    def plot_success_rate_by_problem(self):
        """Success rate visualization."""
        fig, ax = plt.subplots(figsize=(10, 6))
        
        total = self.data["summary"]["total_problems"]
        successful = self.data["summary"]["successful"]
        failed = self.data["summary"]["failed"]
        
        categories = ['Successful', 'Failed']
        values = [successful, failed]
        colors = ['#2ecc71', '#e74c3c']
        
        bars = ax.bar(categories, values, color=colors, edgecolor='black', linewidth=2, width=0.6)
        
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height)}\n({height/total*100:.1f}%)',
                   ha='center', va='bottom', fontweight='bold', fontsize=14)
        
        ax.set_ylabel('Number of Problems', fontsize=14, fontweight='bold')
        ax.set_title(f'Benchmark Success Rate ({successful}/{total} problems)', 
                    fontsize=16, fontweight='bold', pad=20)
        ax.set_ylim(0, total + 2)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        plt.savefig(self.viz_dir / "success_rate.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        print("✓ Generated: success_rate.png")
    
    def plot_latency_comparison(self):
        """Baseline vs optimized latency comparison."""
        fig, ax = plt.subplots(figsize=(14, 8))
        
        problems = []
        baseline_latencies = []
        optimized_latencies = []
        
        for problem, data in self.data["results"].items():
            if data.get("status") == "success" and "baseline_latency_ms" in data:
                problems.append(problem.replace("EvoEval_difficult_", "P"))
                baseline_latencies.append(data["baseline_latency_ms"])
                optimized_latencies.append(data["best_latency_ms"])
        
        x = np.arange(len(problems))
        width = 0.35
        
        bars1 = ax.bar(x - width/2, baseline_latencies, width, label='Baseline',
                      color='#e74c3c', edgecolor='black', linewidth=1.5)
        bars2 = ax.bar(x + width/2, optimized_latencies, width, label='Optimized',
                      color='#2ecc71', edgecolor='black', linewidth=1.5)
        
        ax.set_xlabel('Problem', fontsize=14, fontweight='bold')
        ax.set_ylabel('Latency (ms)', fontsize=14, fontweight='bold')
        ax.set_title('Baseline vs Optimized Latency Comparison', 
                    fontsize=16, fontweight='bold', pad=20)
        ax.set_xticks(x)
        ax.set_xticklabels(problems, rotation=45, ha='right')
        ax.legend(fontsize=12, loc='upper right')
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        plt.savefig(self.viz_dir / "latency_comparison.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        print("✓ Generated: latency_comparison.png")
    
    def plot_mutation_statistics(self):
        """Mutation statistics across problems."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        
        problems = []
        total_mutations = []
        success_rates = []
        
        for problem, data in self.data["results"].items():
            if data.get("status") == "success" and "statistics" in data:
                stats = data["statistics"]
                problems.append(problem.replace("EvoEval_difficult_", "P"))
                total_mutations.append(stats.get("total_mutations", 0))
                success_rates.append(stats.get("success_rate", 0))
        
        # Total mutations bar chart
        if total_mutations:
            bars1 = ax1.bar(problems, total_mutations, color='#3498db', 
                           edgecolor='black', linewidth=1.5)
            
            for bar in bars1:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(height)}',
                        ha='center', va='bottom', fontweight='bold', fontsize=9)
            
            ax1.set_xlabel('Problem', fontsize=12, fontweight='bold')
            ax1.set_ylabel('Total Mutations Attempted', fontsize=12, fontweight='bold')
            ax1.set_title('Mutation Attempts per Problem', fontsize=14, fontweight='bold')
            ax1.grid(axis='y', alpha=0.3, linestyle='--')
            ax1.tick_params(axis='x', rotation=45)
        
        # Success rate bar chart
        if success_rates:
            bars2 = ax2.bar(problems, success_rates, color='#2ecc71', 
                           edgecolor='black', linewidth=1.5)
            
            for bar in bars2:
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}%',
                        ha='center', va='bottom', fontweight='bold', fontsize=9)
            
            ax2.set_xlabel('Problem', fontsize=12, fontweight='bold')
            ax2.set_ylabel('Success Rate (%)', fontsize=12, fontweight='bold')
            ax2.set_title('Mutation Success Rate per Problem', fontsize=14, fontweight='bold')
            ax2.grid(axis='y', alpha=0.3, linestyle='--')
            ax2.tick_params(axis='x', rotation=45)
            ax2.set_ylim(0, 100)
        
        plt.tight_layout()
        plt.savefig(self.viz_dir / "mutation_statistics.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        print("✓ Generated: mutation_statistics.png")
    
    def generate_summary_dashboard(self):
        """Create a comprehensive summary dashboard."""
        fig = plt.figure(figsize=(20, 12))
        gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
        
        # Title
        fig.suptitle('HEDGE EvoEval Benchmark - Comprehensive Dashboard', 
                    fontsize=20, fontweight='bold', y=0.98)
        
        # 1. Success Rate Pie Chart
        ax1 = fig.add_subplot(gs[0, 0])
        successful = self.data["summary"]["successful"]
        failed = self.data["summary"]["failed"]
        ax1.pie([successful, failed], labels=['Success', 'Failed'], autopct='%1.1f%%',
               colors=['#2ecc71', '#e74c3c'], startangle=90)
        ax1.set_title('Success Rate', fontweight='bold', fontsize=12)
        
        # 2. Average Improvement
        ax2 = fig.add_subplot(gs[0, 1])
        improvements = self.data["summary"].get("improvements", [])
        if improvements:
            avg_imp = np.mean(improvements)
            max_imp = np.max(improvements)
            min_imp = np.min(improvements)
            
            ax2.bar(['Avg', 'Max', 'Min'], [avg_imp, max_imp, min_imp],
                   color=['#3498db', '#2ecc71', '#f39c12'], edgecolor='black', linewidth=2)
            ax2.set_ylabel('Improvement (%)', fontweight='bold')
            ax2.set_title('Performance Improvements', fontweight='bold', fontsize=12)
            ax2.grid(axis='y', alpha=0.3)
            
            for i, v in enumerate([avg_imp, max_imp, min_imp]):
                ax2.text(i, v, f'{v:.1f}%', ha='center', va='bottom', fontweight='bold')
        
        # 3. Total Time
        ax3 = fig.add_subplot(gs[0, 2])
        total_time = self.data["summary"]["total_time"]
        ax3.text(0.5, 0.5, f'{total_time:.1f}s', ha='center', va='center',
                fontsize=48, fontweight='bold', color='#9b59b6')
        ax3.text(0.5, 0.2, 'Total Execution Time', ha='center', va='center',
                fontsize=14, fontweight='bold')
        ax3.axis('off')
        ax3.set_title('Benchmark Duration', fontweight='bold', fontsize=12)
        
        # 4. Improvement by Problem
        ax4 = fig.add_subplot(gs[1, :])
        problems = []
        improvements_list = []
        
        for problem, data in self.data["results"].items():
            if data.get("status") == "success" and "improvement_percent" in data:
                problems.append(problem.replace("EvoEval_difficult_", "P"))
                improvements_list.append(data["improvement_percent"])
        
        if improvements_list:
            bars = ax4.barh(problems, improvements_list, color='#3498db', 
                           edgecolor='black', linewidth=1.5)
            ax4.set_xlabel('Improvement (%)', fontweight='bold', fontsize=12)
            ax4.set_title('Performance Improvement by Problem', fontweight='bold', fontsize=14)
            ax4.grid(axis='x', alpha=0.3)
            
            for i, bar in enumerate(bars):
                width = bar.get_width()
                ax4.text(width, bar.get_y() + bar.get_height()/2.,
                        f' {width:.1f}%', ha='left', va='center', fontweight='bold')
        
        # 5. Pareto Solutions
        ax5 = fig.add_subplot(gs[2, 0])
        pareto_counts = []
        for problem, data in self.data["results"].items():
            if data.get("status") == "success":
                pareto_counts.append(data.get("pareto_count", 0))
        
        if pareto_counts:
            ax5.hist(pareto_counts, bins=10, color='#e67e22', edgecolor='black', linewidth=1.5)
            ax5.set_xlabel('Pareto Solutions', fontweight='bold')
            ax5.set_ylabel('Frequency', fontweight='bold')
            ax5.set_title('Pareto Solutions Distribution', fontweight='bold', fontsize=12)
            ax5.grid(axis='y', alpha=0.3)
        
        # 6. Configuration Info
        ax6 = fig.add_subplot(gs[2, 1:])
        ax6.axis('off')
        
        config = self.data["configuration"]
        config_text = f"""
        Configuration:
        • Level: {config['level']}
        • Generations: {config['generations']}
        • Population Size: {config['population_size']}
        • LLM Provider: {config['llm_provider']}
        
        Summary:
        • Total Problems: {self.data['summary']['total_problems']}
        • Successful: {self.data['summary']['successful']}
        • Failed: {self.data['summary']['failed']}
        """
        
        ax6.text(0.1, 0.5, config_text, fontsize=12, verticalalignment='center',
                family='monospace', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.savefig(self.viz_dir / "summary_dashboard.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        print("✓ Generated: summary_dashboard.png")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate comprehensive visualizations for EvoEval benchmark results"
    )
    parser.add_argument(
        "results_dir",
        type=str,
        help="Directory containing benchmark_results.json"
    )
    
    args = parser.parse_args()
    
    try:
        visualizer = EvoEvalVisualizer(args.results_dir)
        visualizer.generate_all_visualizations()
        print("\n✓ All visualizations generated successfully!")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
