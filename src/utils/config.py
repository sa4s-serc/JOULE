"""Configuration utility for HEDGE."""

import json
import os
from pathlib import Path
from typing import Any, Dict

CONFIG_FILE = Path.home() / ".hedge" / "config.json"
DEFAULT_CONFIG = {
    "llm": {
        "default_provider": "gemini",
        "openai_model": "gpt-4o",
        "gemini_model": "gemini-2.5-flash"
    },
    "optimization": {
        "default_level": "standard",
        "default_generations": 10,
        "default_population_size": 8,
        "default_timeout": 30
    },
    "output": {
        "auto_visualize": False,
        "save_ir_snapshots": False,
        "experiment_base_dir": "experiments"
    },
    "ui": {
        "theme": "auto",
        "show_progress": True,
        "verbose_by_default": False
    },
    "logging": {
        "log_to_file": True,
        "log_file": "hedge.log",
        "log_to_console": False,
        "level": "INFO"
    }
}

def load_config() -> Dict[str, Any]:
    """Load configuration from file or return defaults."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
            # Merge with defaults to ensure all keys exist
            return merge_config(DEFAULT_CONFIG, config)
        except Exception:
            pass
    
    return DEFAULT_CONFIG.copy()

def merge_config(default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    """Merge user config with defaults."""
    result = default.copy()
    
    for key, value in user.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value
    
    return result

def get_llm_config() -> Dict[str, str]:
    """Get LLM-specific configuration."""
    config = load_config()
    llm_config = config.get("llm", {})
    provider = llm_config.get("default_provider", "gemini")
    
    if provider == "openai":
        model = llm_config.get("openai_model", "gpt-4o")
    else:
        model = llm_config.get("gemini_model", "gemini-2.5-flash")
        
    return {
        "provider": provider,
        "model": model
    }

def save_config(config: Dict[str, Any]):
    """Save configuration to file."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
