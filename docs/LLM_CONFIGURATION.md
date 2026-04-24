# LLM Configuration Guide

This document provides comprehensive instructions for configuring Large Language Models (LLMs) in JOULE using LiteLLM as the provider abstraction layer.

## Overview

JOULE uses **LiteLLM** to support multiple LLM providers through a unified interface. LiteLLM handles authentication, request formatting, and response parsing across dozens of providers including OpenAI, Anthropic, Groq, Ollama, vLLM, and many others.

## Quick Start

### 1. Install LLM Dependencies

```bash
# If installing from source
pip install -e ".[llm]"

# Or add to your environment
pip install litellm>=1.48.0
```

### 2. Set Your API Key

```bash
# For OpenAI
export OPENAI_API_KEY="sk-..."

# For other providers, see Provider-Specific Setup below
```

### 3. Configure the Model

**Option A: Environment Variable**
```bash
export JOULE_LLM_MODEL="openai/gpt-4o-mini"
```

**Option B: `pyproject.toml`**
```toml
[tool.joule]
llm_model = "openai/gpt-4o-mini"
```

### 4. Verify Setup

```bash
joule doctor
```

Expected output:
```
✓ llm-model: openai/gpt-4o-mini
✓ litellm: ok
```

---

## Configuration Methods

### Method 1: `pyproject.toml` (Recommended)

Add configuration under `[tool.joule]`:

```toml
[tool.joule]
llm_model = "openai/gpt-4o-mini"
enable_llm_operators = true
```

**Advantages:**
- Version controlled with your project
- Consistent across team members
- Self-documenting

### Method 2: Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `JOULE_LLM_MODEL` | Model identifier | `openai/gpt-4o-mini` |
| `OPENAI_API_KEY` | OpenAI authentication | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic authentication | `sk-ant-...` |
| `GROQ_API_KEY` | Groq authentication | `gsk_...` |
| `OPENAI_API_BASE` | Custom endpoint URL | `http://localhost:8000/v1` |

**Environment variables take precedence** over `pyproject.toml` settings.

### Method 3: Profile-Specific Configuration

Create multiple configuration profiles:

```toml
[tool.joule]
# Default profile
llm_model = "openai/gpt-4o-mini"

# Override via environment for CI
# JOULE_PROFILE=ci overrides settings
```

---

## Supported Providers

### OpenAI

```bash
export OPENAI_API_KEY="sk-..."
```

```toml
[tool.joule]
llm_model = "openai/gpt-4o-mini"        # or gpt-4o, gpt-4-turbo, etc.
```

### Anthropic (Claude)

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

```toml
[tool.joule]
llm_model = "anthropic/claude-3-5-sonnet-20241022"
```

### Groq (Fast Inference)

```bash
export GROQ_API_KEY="gsk_..."
```

```toml
[tool.joule]
llm_model = "groq/llama-3.3-70b-versatile"
# or "groq/qwen/qwen3-32b"
# or "groq/deepseek-r1-distill-llama-70b"
```

### Ollama (Local Models)

```bash
# Ollama runs locally, no API key needed
# Ensure Ollama is running on your machine
```

```toml
[tool.joule]
llm_model = "ollama/llama3.1"
# or "ollama/codellama"
# or "ollama/mistral"
```

### Azure OpenAI

```bash
export AZURE_API_KEY="..."
export AZURE_API_BASE="https://your-resource.openai.azure.com"
export AZURE_API_VERSION="2024-02-15-preview"
```

```toml
[tool.joule]
llm_model = "azure/your-deployment-name"
```

### OpenRouter (Aggregated Access)

```bash
export OPENROUTER_API_KEY="sk-or-..."
```

```toml
[tool.joule]
llm_model = "openrouter/anthropic/claude-3.5-sonnet"
```

### vLLM (Self-Hosted)

```bash
export OPENAI_API_KEY="not-needed"  # vLLM may not require auth
export OPENAI_API_BASE="http://localhost:8000/v1"
```

```toml
[tool.joule]
llm_model = "openai/your-model-name"
```

### Other Providers

LiteLLM supports 100+ providers. See [LiteLLM Providers Documentation](https://docs.litellm.ai/docs/providers) for the complete list.

---

## Custom/OpenAI-Compatible Endpoints

For any OpenAI-compatible API (vLLM, text-generation-inference, etc.):

### Configuration

```bash
# Required environment variables
export OPENAI_API_BASE="http://your-endpoint:port/v1"
export OPENAI_API_KEY="your-key-if-required"  # May be optional

# JOULE model configuration
export JOULE_LLM_MODEL="openai/your-model-name"
```

### Common Local Deployment Patterns

#### vLLM Server
```bash
# Terminal 1: Start vLLM server
python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Llama-3.1-8B-Instruct \
    --port 8000

# Terminal 2: Configure JOULE
export OPENAI_API_BASE="http://localhost:8000/v1"
export JOULE_LLM_MODEL="openai/meta-llama/Llama-3.1-8B-Instruct"
```

#### Ollama with Custom Host
```bash
# Start Ollama server (custom host)
OLLAMA_HOST=0.0.0.0:11434 ollama serve

# Configure JOULE
export OPENAI_API_BASE="http://localhost:11434/v1"
export OPENAI_API_KEY="ollama"  # Ollama requires any non-empty key
export JOULE_LLM_MODEL="openai/llama3.1"
```

#### Text Generation Inference (TGI)
```bash
# Configure JOULE for TGI endpoint
export OPENAI_API_BASE="http://localhost:8080/v1"
export JOULE_LLM_MODEL="openai/tgi-model"
```

---

## Model Selection Guidelines

### For Cost-Effective Optimization

| Model | Provider | Use Case |
|-------|----------|----------|
| `gpt-4o-mini` | OpenAI | Good balance of quality and cost |
| `llama-3.3-70b-versatile` | Groq | Fast inference, competitive quality |
| `claude-3-5-haiku-20241022` | Anthropic | Fast, cost-effective |

### For Maximum Quality

| Model | Provider | Use Case |
|-------|----------|----------|
| `gpt-4o` | OpenAI | Best overall quality |
| `claude-3-5-sonnet-20241022` | Anthropic | Excellent code understanding |
| `deepseek-r1-distill-llama-70b` | Groq | Strong reasoning capabilities |

### For Local/Privacy-Sensitive Work

| Model | Setup | Hardware Requirements |
|-------|-------|----------------------|
| `ollama/llama3.1` | Ollama | 8GB+ VRAM (8B model) |
| `ollama/codellama:13b` | Ollama | 16GB+ VRAM |

---

## Advanced Configuration

### Disabling LLM Operators

If you want to run JOULE without LLM features:

```toml
[tool.joule]
llm_model = ""  # Empty string disables LLM
enable_llm_operators = false
```

### Testing Without an LLM

Use fake responses for testing or CI environments:

```bash
export JOULE_FAKE_LLM_RESPONSE='{"candidate_source": "def optimized(): pass", "reasoning": "Test optimization", "dependencies": [], "proposal_rank": 1, "feature_hints": {}}'
```

### Fallback Mock Backend

If no LLM is configured, JOULE uses the `mock` backend for energy measurements:

```toml
[tool.joule]
default_backend = "mock"  # Used when LLM is unavailable
```

---

## Troubleshooting

### Common Issues

#### 1. "litellm is not installed"

**Symptom:** `LLMUnavailableError: litellm is not installed`

**Solution:**
```bash
pip install litellm>=1.48.0
# or
pip install -e ".[llm]"
```

#### 2. "No LLM model configured"

**Symptom:** `LLMUnavailableError: No LLM model configured`

**Solution:**
```bash
# Set via environment
export JOULE_LLM_MODEL="openai/gpt-4o-mini"

# Or check your pyproject.toml has:
# [tool.joule]
# llm_model = "openai/gpt-4o-mini"
```

#### 3. Authentication Errors

**Symptom:** API key errors from the provider

**Solution:**
```bash
# Verify your API key is set
echo $OPENAI_API_KEY  # or relevant provider key

# For OpenAI specifically, test with:
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

#### 4. Custom Endpoint Not Working

**Symptom:** Connection errors or timeouts with custom endpoints

**Solution:**
```bash
# Verify the endpoint is accessible
curl $OPENAI_API_BASE/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Ensure /v1 is included in the base URL
export OPENAI_API_BASE="http://localhost:8000/v1"  # Correct
export OPENAI_API_BASE="http://localhost:8000"    # Incorrect
```

#### 5. Model Format Issues

**Symptom:** "Model not found" or provider errors

**Solution:**

Ensure correct `provider/model` format:
```toml
# Correct
llm_model = "openai/gpt-4o-mini"
llm_model = "groq/llama-3.3-70b-versatile"
llm_model = "anthropic/claude-3-5-sonnet-20241022"

# Incorrect (missing provider prefix)
llm_model = "gpt-4o-mini"
```

### Debug Mode

Enable verbose logging to diagnose issues:

```bash
# LiteLLM debug logging
export LITELLM_LOG="DEBUG"

# Run JOULE command
joule doctor
```

### Checking Current Configuration

```bash
# Show resolved configuration
joule config show

# Verify LLM availability
joule doctor
```

---

## Security Best Practices

### API Key Management

1. **Never commit API keys to version control**
   ```bash
   # Use .env files (add to .gitignore!)
   echo ".env" >> .gitignore
   ```

2. **Use environment variables in production**
   ```bash
   # Load from .env file
   export $(grep -v '^#' .env | xargs)
   ```

3. **Rotate keys regularly**
   - Set calendar reminders to rotate API keys
   - Monitor usage dashboards for unexpected activity

### Local Development

Create a `.env` file in your project root:

```bash
# .env
OPENAI_API_KEY=sk-...
JOULE_LLM_MODEL=openai/gpt-4o-mini
```

Load it before running JOULE:
```bash
set -a; source .env; set +a
joule run <target>
```

---

## Reference: Environment Variable Quick Reference

| Variable | Provider | Required | Description |
|----------|----------|----------|-------------|
| `JOULE_LLM_MODEL` | All | Yes | Model in `provider/model` format |
| `OPENAI_API_KEY` | OpenAI, Azure | Yes | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic | Yes | Claude API key |
| `GROQ_API_KEY` | Groq | Yes | Groq API key |
| `AZURE_API_KEY` | Azure | Yes | Azure OpenAI key |
| `AZURE_API_BASE` | Azure | Yes | Azure endpoint URL |
| `OPENAI_API_BASE` | Custom | Sometimes | Custom OpenAI-compatible endpoint |
| `OPENROUTER_API_KEY` | OpenRouter | Yes | OpenRouter API key |
| `JOULE_FAKE_LLM_RESPONSE` | Testing | No | Fake response for testing |

---

## Example Configurations

### Complete OpenAI Setup

```bash
# .env
export OPENAI_API_KEY="sk-..."
export JOULE_LLM_MODEL="openai/gpt-4o-mini"
```

### Complete Groq Setup

```bash
# .env
export GROQ_API_KEY="gsk_..."
export JOULE_LLM_MODEL="groq/llama-3.3-70b-versatile"
```

### Complete Local Ollama Setup

```bash
# No API key needed
export JOULE_LLM_MODEL="ollama/llama3.1"

# Ensure Ollama is running
ollama run llama3.1
```

### Complete vLLM Self-Hosted Setup

```bash
# Terminal 1: Start server
python -m vllm.entrypoints.openai.api_server \
    --model unsloth/llama-3-8b-bnb-4bit \
    --port 8000

# Terminal 2: Configure JOULE
export OPENAI_API_BASE="http://localhost:8000/v1"
export OPENAI_API_KEY="dummy"  # vLLM may ignore this
export JOULE_LLM_MODEL="openai/unsloth/llama-3-8b-bnb-4bit"
```

### Team Shared Configuration (pyproject.toml)

```toml
[tool.joule]
llm_model = "groq/llama-3.3-70b-versatile"  # Cost-effective default
enable_llm_operators = true
optimization_budget = 6
```

Each team member provides their own `GROQ_API_KEY` via environment variable.

---

## Further Resources

- [LiteLLM Documentation](https://docs.litellm.ai/docs/)
- [LiteLLM Supported Providers](https://docs.litellm.ai/docs/providers)
- [JOULE Transformations Guide](TRANSFORMATIONS.md)
- [JOULE Architecture](ARCHITECTURE.md)
