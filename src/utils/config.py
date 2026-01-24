"""Configuration utility for HEDGE."""

from pathlib import Path
from typing import Any, Dict

import yaml

# Configuration file paths in order of priority (last one wins if we were doing simple merge,
# but we usually load first found or merge them)
# Priority:
# 1. hedge.yaml (local)
# 2. ~/.hedge/config.yaml (global)
# 3. config/default.yaml (project default)

PROJECT_ROOT = Path(__file__).parent.parent.parent
LOCAL_CONFIG = Path.cwd() / "hedge.yaml"
GLOBAL_CONFIG = Path.home() / ".hedge" / "config.yaml"
DEFAULT_PROJECT_CONFIG = PROJECT_ROOT / "config" / "default.yaml"


def get_default_config() -> Dict[str, Any]:
    """Load the default configuration from the project's default.yaml."""
    if DEFAULT_PROJECT_CONFIG.exists():
        try:
            with open(DEFAULT_PROJECT_CONFIG, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass

    # Minimal fallback if default.yaml is missing
    return {
        "optimization": {"default_level": "standard", "default_generations": 10},
        "llm": {"default_provider": "gemini"},
        "output": {"experiment_base_dir": "experiments"},
        "logging": {"level": "INFO"},
    }


def load_config(config_path: Path = None) -> Dict[str, Any]:
    """
    Load configuration.
    If config_path is provided, load from there.
    Otherwise, search in order: hedge.yaml, ~/.hedge/config.yaml, project's default.yaml.
    """
    base_config = get_default_config()

    # If a specific path is provided, use it
    if config_path and config_path.exists():
        try:
            with open(config_path, "r") as f:
                user_config = yaml.safe_load(f) or {}
                return merge_config(base_config, user_config)
        except Exception:
            return base_config

    # Otherwise, merge from global and then local
    config = base_config

    if GLOBAL_CONFIG.exists():
        try:
            with open(GLOBAL_CONFIG, "r") as f:
                global_user_config = yaml.safe_load(f) or {}
                config = merge_config(config, global_user_config)
        except Exception:
            pass

    if LOCAL_CONFIG.exists():
        try:
            with open(LOCAL_CONFIG, "r") as f:
                local_user_config = yaml.safe_load(f) or {}
                config = merge_config(config, local_user_config)
        except Exception:
            pass

    return config


def merge_config(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursive merge of two dictionaries."""
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value

    return result


def get_llm_config() -> Dict[str, Any]:
    """Get LLM-specific configuration."""
    config = load_config()
    llm_settings = config.get("llm", {})
    provider = llm_settings.get("default_provider", "gemini")

    provider_settings = llm_settings.get(provider, {})

    return {"provider": provider, **provider_settings}


def save_config(config: Dict[str, Any], path: Path = GLOBAL_CONFIG):
    """Save configuration to the specified YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


def get_config_setting(dot_key: str, default: Any = None) -> Any:
    """Get a configuration setting using dot notation (e.g., 'llm.openai.model')."""
    config = load_config()
    keys = dot_key.split(".")

    current = config
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default

    return current
