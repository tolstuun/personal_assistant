"""
Configuration loader.

Loads YAML config files and provides unified access.
Supports:
- Multiple config files merged together
- Environment variable substitution
- Default values
"""

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"


def _substitute_env_vars(obj: Any) -> Any:
    """Recursively substitute environment variables in config."""
    if isinstance(obj, str):
        if obj.startswith("${") and "}" in obj:
            var_part = obj[2:obj.index("}")]
            
            if ":-" in var_part:
                var_name, default = var_part.split(":-", 1)
            else:
                var_name, default = var_part, ""
            
            value = os.environ.get(var_name, default)
            
            if obj == f"${{{var_part}}}":
                return value
            
            return obj.replace(f"${{{var_part}}}", value)
        
        return obj
    
    elif isinstance(obj, dict):
        return {k: _substitute_env_vars(v) for k, v in obj.items()}
    
    elif isinstance(obj, list):
        return [_substitute_env_vars(item) for item in obj]
    
    return obj


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a single YAML file."""
    if not path.exists():
        logger.warning(f"Config file not found: {path}")
        return {}
    
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    
    return _substitute_env_vars(data)


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries. Override takes precedence."""
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


@lru_cache(maxsize=1)
def get_config(config_dir: str | None = None) -> dict[str, Any]:
    """Load and merge all config files."""
    base_dir = Path(config_dir) if config_dir else CONFIG_DIR
    
    config: dict[str, Any] = {}
    
    for filename in ["llm.example.yaml", "llm.yaml", "storage.yaml"]:
        file_path = base_dir / filename
        if file_path.exists():
            file_config = load_yaml(file_path)
            config = deep_merge(config, file_config)
            logger.debug(f"Loaded config: {filename}")
    
    agents_dir = base_dir / "agents"
    if agents_dir.exists():
        config["agents"] = {}
        for agent_file in agents_dir.glob("*.yaml"):
            agent_name = agent_file.stem
            config["agents"][agent_name] = load_yaml(agent_file)
            logger.debug(f"Loaded agent config: {agent_name}")
    
    sources_dir = base_dir / "sources"
    if sources_dir.exists():
        config["sources"] = {}
        for source_file in sources_dir.glob("*.yaml"):
            source_name = source_file.stem
            config["sources"][source_name] = load_yaml(source_file)
            logger.debug(f"Loaded sources config: {source_name}")
    
    return config


def reload_config() -> dict[str, Any]:
    """Force reload config (clears cache)."""
    get_config.cache_clear()
    return get_config()


def get_agent_config(agent_name: str) -> dict[str, Any]:
    """Get config for specific agent."""
    config = get_config()
    return config.get("agents", {}).get(agent_name, {})


def get_sources_config(source_name: str) -> dict[str, Any]:
    """Get config for specific source type."""
    config = get_config()
    return config.get("sources", {}).get(source_name, {})
