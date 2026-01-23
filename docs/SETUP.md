# Setup & Configuration

This guide provides instructions for installing and configuring HEDGE for optimal performance.

## Prerequisites

- Python 3.8 or higher
- Linux recommended (for hardware energy monitoring via CodeCarbon)
- Valid API keys for OpenAI or Google Gemini (optional, for semantic optimizations)

## Installation

### 1. Environment Setup

It is recommended to use a virtual environment to manage dependencies:

```bash
# Clone the repository
git clone <repository-url>
cd HEDGE

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Dependency Installation

Install the required core and optional components:

```bash
# Install core dependencies
pip install -r requirements.txt

# Install optional visualization and UI components
pip install rich matplotlib
```

## Configuration

### API Keys for Semantic Optimization

HEDGE utilizes LLMs for high-level semantic transformations. Configure your environment by creating a `.env` file in the project root.

```bash
# Example .env content
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
```

### Resource Monitoring

HEDGE tracks energy consumption using the `CodeCarbon` library. On Linux systems, this typically requires access to Intel RAPL or NVIDIA NVML. If hardware sensors are unavailable, the system will fall back to execution time as the primary fitness metric.

## Verification

To verify the installation, run the built-in benchmark suite:

```bash
python hedge.py benchmark --quick
```

---
*For more information on usage, see the [CLI Reference](CLI.md).*
