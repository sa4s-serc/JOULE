# HEDGE Quick Start Guide

Get up and running with HEDGE in 5 minutes.

## Installation

### Option 1: Automated Setup (Recommended)
```bash
git clone <repository-url>
cd HEDGE
python scripts/setup.py
```

### Option 2: Manual Setup
```bash
git clone <repository-url>
cd HEDGE

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
# Edit .env and add your API keys (optional)
```

## First Optimization

### Basic Usage
```bash
# Activate virtual environment
source .venv/bin/activate

# Try HEDGE
python hedge.py optimize examples/target_fib.py examples/test_target_fib.py

# Or create a new project
python hedge.py project init my_first_project
cd my_first_project
python ../hedge.py optimize src/target.py tests/test_target.py
```

## Understanding Results

After optimization, you'll see:

1. **Pareto-Optimal Solutions** - Multiple optimized versions balancing energy vs time
2. **Best Solution** - Saved as `*_optimized.py`
3. **Experiment Results** - Detailed metrics in `experiments/run_TIMESTAMP/`

### Example Output
```
Optimization Complete
┌─────────────────────────┐
│ Time: 45.2s             │
│ Solutions: 8            │
│ Success Rate: 85.3%     │
│ Cache Hits: 12          │
└─────────────────────────┘

Best solution saved: target_fib_optimized.py
  94.2% energy improvement
```

## Optimization Levels

Choose the right level for your needs:

- **`micro`** - Fast, safe optimizations (constant folding, dead code removal)
- **`basic`** - Micro + Python idioms and patterns
- **`standard`** - Basic + algorithmic improvements (recommended)
- **`advanced`** - Standard + AI-powered semantic optimization (requires API key)
- **`aggressive`** - All optimizations enabled

## Configuration

### Quick Config
```bash
python hedge.py config init  # Guided setup
python hedge.py config set optimization.default_level advanced
python hedge.py config show
```

### API Keys (for Advanced Features)
Add to your `.env` file:
```bash
# For OpenAI GPT-4
OPENAI_API_KEY=your_openai_key_here

# For Google Gemini (recommended)
GEMINI_API_KEY=your_gemini_key_here
```

## Visualization

Generate beautiful charts and reports:
```bash
python hedge.py optimize examples/target_fib.py examples/test_target_fib.py --visualize
```

View the HTML report at `experiments/run_TIMESTAMP/visualizations/report.html`

## Benchmarking

Test HEDGE on built-in problems:
```bash
# Quick benchmark
python hedge.py benchmark --quick

# Full benchmark suite
python hedge.py benchmark

# Compare optimization levels
python hedge.py benchmark --compare-levels
```

## Code Analysis

Analyze your code before optimization:
```bash
python hedge.py analyze mycode.py
python hedge.py analyze mycode.py --detailed --format json
```

## Project Management

Create organized optimization projects:
```bash
# Create new project
python hedge.py project init my_optimization_project --template advanced

# Check project status
cd my_optimization_project
python ../hedge.py project status

# Clean up old experiments
python ../hedge.py project clean --experiments --keep-recent 3
```

## Troubleshooting

### Common Issues

**Import Errors**
```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

**No Improvements Found**
- Try a higher optimization level: `--level advanced`
- Your code might already be optimal!
- Check the analysis: `python hedge.py analyze yourcode.py`

**LLM Errors (Advanced Level)**
- Check your API key in `.env`
- Try a different provider: `--llm-provider openai`
- Fall back to standard level: `--level standard`

**Timeout Issues**
- Increase timeout: `--timeout 60`
- Reduce generations: `--generations 5`

### Getting Help
```bash
python hedge.py --help
python hedge.py optimize --help
python hedge.py config --help
```

## Next Steps

1. **Read the Architecture Guide** - `docs/ARCHITECTURE.md`
2. **Explore Examples** - `examples/` directory
3. **Try Advanced Features** - Custom layers, LLM optimization
4. **Contribute** - `docs/CONTRIBUTING.md`

## Key Commands Reference

```bash
# Optimization
hedge.py optimize <target> <tests> [options]

# Analysis
hedge.py analyze <code> [options]

# Visualization
hedge.py visualize <results_dir>

# Benchmarking
hedge.py benchmark [options]

# Configuration
hedge.py config show|set|init

# Project Management
hedge.py project init|status|clean
```

Professional code optimization tool.