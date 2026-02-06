"""
Configuration Management System for HEDGE
==========================================

Centralized configuration management with YAML support, environment variable
overrides, and validation. This module consolidates all configuration functionality.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

# Configuration file paths in order of priority
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


def merge_config(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursive merge of two dictionaries."""
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = value

    return result


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


def get_llm_config() -> Dict[str, Any]:
    """Get LLM-specific configuration."""
    config = load_config()
    llm_settings = config.get("llm", {})
    provider = llm_settings.get("default_provider", "gemini")

    provider_settings = llm_settings.get(provider, {})

    return {"provider": provider, **provider_settings}


@dataclass
class ConfigManager:
    """Manages HEDGE configuration from multiple sources."""

    config_data: Dict[str, Any] = field(default_factory=dict)
    config_sources: list = field(default_factory=list)

    def __post_init__(self):
        """Initialize configuration from default sources."""
        self.load_default_config()
        self.load_user_config()
        self.apply_environment_overrides()

    def load_default_config(self):
        """Load default configuration."""
        default_config_path = Path(__file__).parent.parent.parent / "config" / "default.yaml"

        if default_config_path.exists():
            with open(default_config_path) as f:
                default_config = yaml.safe_load(f)

            self.config_data = default_config
            self.config_sources.append(f"default:{default_config_path}")

    def load_user_config(self):
        """Load user-specific configuration."""
        user_config_paths = [
            Path.home() / ".hedge" / "config.yaml",
            Path.home() / ".hedge" / "config.json",
            Path(".hedge.yaml"),
            Path(".hedge.json"),
        ]

        for config_path in user_config_paths:
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        if config_path.suffix == ".yaml":
                            user_config = yaml.safe_load(f)
                        else:
                            user_config = json.load(f)

                    self.config_data = self._merge_configs(self.config_data, user_config)
                    self.config_sources.append(f"user:{config_path}")
                    break
                except Exception as e:
                    print(f"Warning: Failed to load {config_path}: {e}")

    def apply_environment_overrides(self):
        """Apply environment variable overrides."""
        env_overrides = {}

        # Map environment variables to config keys
        env_mappings = {
            "HEDGE_OPTIMIZATION_LEVEL": "optimization.default_level",
            "HEDGE_GENERATIONS": "optimization.default_generations",
            "HEDGE_POPULATION_SIZE": "optimization.default_population_size",
            "HEDGE_TIMEOUT": "optimization.default_timeout",
            "HEDGE_LLM_PROVIDER": "llm.default_provider",
            "HEDGE_EXPERIMENT_DIR": "output.experiment_base_dir",
            "HEDGE_LOG_LEVEL": "logging.level",
            "HEDGE_PARALLEL": "performance.parallel_mutations",
            "HEDGE_CACHE_ENABLED": "performance.cache_enabled",
        }

        for env_var, config_key in env_mappings.items():
            if env_var in os.environ:
                value = self._parse_env_value(os.environ[env_var])
                self._set_nested_value(env_overrides, config_key, value)

        if env_overrides:
            self.config_data = self._merge_configs(self.config_data, env_overrides)
            self.config_sources.append("environment")

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
        keys = key.split(".")
        current = self.config_data

        try:
            for k in keys:
                current = current[k]
            return current
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any):
        """Set configuration value using dot notation."""
        self._set_nested_value(self.config_data, key, value)

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section."""
        return self.get(section, {})

    def save_user_config(self, config_path: Optional[Path] = None):
        """Save current configuration to user config file."""
        if config_path is None:
            config_path = Path.home() / ".hedge" / "config.yaml"

        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            yaml.dump(self.config_data, f, default_flow_style=False, indent=2)

    def validate(self) -> list:
        """Validate configuration and return list of issues."""
        issues = []

        # Validate optimization settings
        if self.get("optimization.default_generations", 0) < 1:
            issues.append("optimization.default_generations must be >= 1")

        if self.get("optimization.default_population_size", 0) < 1:
            issues.append("optimization.default_population_size must be >= 1")

        if self.get("optimization.default_timeout", 0) < 5:
            issues.append("optimization.default_timeout should be >= 5 seconds")

        # Validate LLM settings
        provider = self.get("llm.default_provider")
        if provider not in ["openai", "gemini"]:
            issues.append(f"Invalid LLM provider: {provider}")

        # Validate paths
        exp_dir = Path(self.get("output.experiment_base_dir", "experiments"))
        if not exp_dir.exists():
            try:
                exp_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                issues.append(f"Cannot create experiment directory: {e}")

        return issues

    def _merge_configs(self, base: Dict, override: Dict) -> Dict:
        """Recursively merge configuration dictionaries."""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def _set_nested_value(self, config: Dict, key: str, value: Any):
        """Set nested configuration value using dot notation."""
        keys = key.split(".")
        current = config

        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        current[keys[-1]] = value

    def _parse_env_value(self, value: str) -> Union[str, int, float, bool]:
        """Parse environment variable value to appropriate type."""
        # Boolean values
        if value.lower() in ("true", "false"):
            return value.lower() == "true"

        # Integer values
        try:
            return int(value)
        except ValueError:
            pass

        # Float values
        try:
            return float(value)
        except ValueError:
            pass

        # String values
        return value

    def to_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary."""
        return self.config_data.copy()

    def __str__(self) -> str:
        """String representation of configuration."""
        return f"ConfigManager(sources={self.config_sources})"


# Global configuration instance
_config_manager = None


def get_config() -> ConfigManager:
    """Get global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def reload_config():
    """Reload configuration from all sources."""
    global _config_manager
    _config_manager = ConfigManager()
    return _config_manager
