"""
Config File Loader for CascadeFlow

Load CascadeFlow configuration from YAML or JSON files.

Supports:
- Model configurations
- Domain-specific configurations
- Quality thresholds
- Agent settings

Example YAML config (cascadeflow.yaml):
    ```yaml
    models:
      - name: gpt-4o-mini
        provider: openai
        cost: 0.00015
      - name: gpt-4o
        provider: openai
        cost: 0.0025

    domains:
      code:
        drafter: deepseek-coder
        verifier: gpt-4o
        threshold: 0.85
        temperature: 0.2

    settings:
      enable_cascade: true
      enable_domain_detection: true
      verbose: false
    ```

Usage:
    >>> from cascadeflow.config_loader import load_config, create_agent_from_config
    >>>
    >>> # Load config
    >>> config = load_config("cascadeflow.yaml")
    >>>
    >>> # Create agent from config
    >>> agent = create_agent_from_config(config)
    >>> result = await agent.run("Write a Python function")
"""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

from .schema import DomainConfig, DomainValidationMethod, ModelConfig

if TYPE_CHECKING:
    from .agent import CascadeAgent


def load_yaml(path: Union[str, Path]) -> dict[str, Any]:
    """Load a YAML file."""
    try:
        import yaml
    except ImportError:
        raise ImportError(
            "PyYAML is required for YAML config loading. " "Install it with: pip install pyyaml"
        )

    with open(path) as f:
        return yaml.safe_load(f)


def load_json(path: Union[str, Path]) -> dict[str, Any]:
    """Load a JSON file."""
    with open(path) as f:
        return json.load(f)


def load_config(path: Union[str, Path], file_format: Optional[str] = None) -> dict[str, Any]:
    """
    Load configuration from a file.

    Args:
        path: Path to config file (YAML or JSON)
        file_format: Explicit format ('yaml' or 'json'). If None, infers from extension.

    Returns:
        Parsed configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If format is unknown
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    # Infer format from extension if not specified
    if file_format is None:
        suffix = path.suffix.lower()
        if suffix in (".yaml", ".yml"):
            file_format = "yaml"
        elif suffix == ".json":
            file_format = "json"
        else:
            raise ValueError(
                f"Unknown config file format: {suffix}. "
                "Use .yaml, .yml, or .json extension, or specify format explicitly."
            )

    if file_format == "yaml":
        return load_yaml(path)
    elif file_format == "json":
        return load_json(path)
    else:
        raise ValueError(f"Unknown format: {file_format}. Use 'yaml' or 'json'.")


def parse_model_config(config: dict[str, Any]) -> ModelConfig:
    """
    Parse a model configuration dictionary into a ModelConfig object.

    Args:
        config: Dictionary with model configuration

    Returns:
        ModelConfig object
    """
    # Only include fields that are actually provided
    model_kwargs = {
        "name": config["name"],
        "provider": config["provider"],
        "cost": config.get("cost", 0.001),
    }

    # Add optional fields only if provided
    if "supports_tools" in config:
        model_kwargs["supports_tools"] = config["supports_tools"]
    if "max_tokens" in config:
        model_kwargs["max_tokens"] = config["max_tokens"]
    if "temperature" in config:
        model_kwargs["temperature"] = config["temperature"]
    if "base_url" in config:
        model_kwargs["base_url"] = config["base_url"]
    if "api_key" in config:
        model_kwargs["api_key"] = config["api_key"]

    return ModelConfig(**model_kwargs)


def parse_domain_config(config: dict[str, Any]) -> DomainConfig:
    """
    Parse a domain configuration dictionary into a DomainConfig object.

    Args:
        config: Dictionary with domain configuration

    Returns:
        DomainConfig object
    """
    # Handle validation_method as string or enum
    validation_method = config.get("validation_method", "quality")
    if isinstance(validation_method, str):
        validation_method = DomainValidationMethod(validation_method)

    return DomainConfig(
        drafter=config["drafter"],
        verifier=config["verifier"],
        threshold=config.get("threshold", 0.70),
        validation_method=validation_method,
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens", 1000),
        fallback_models=config.get("fallback_models", []),
        require_verifier=config.get("require_verifier", False),
        adaptive_threshold=config.get("adaptive_threshold", True),
        skip_on_simple=config.get("skip_on_simple", True),
        enabled=config.get("enabled", True),
        description=config.get("description", ""),
    )


def parse_models(models_config: list[dict[str, Any]]) -> list[ModelConfig]:
    """Parse a list of model configurations."""
    return [parse_model_config(m) for m in models_config]


def parse_domains(domains_config: dict[str, dict[str, Any]]) -> dict[str, DomainConfig]:
    """Parse domain configurations."""
    return {domain: parse_domain_config(config) for domain, config in domains_config.items()}


def create_agent_from_config(config: dict[str, Any], **overrides) -> "CascadeAgent":
    """
    Create a CascadeAgent from a configuration dictionary.

    Args:
        config: Configuration dictionary (from load_config)
        **overrides: Override any config values

    Returns:
        Configured CascadeAgent instance

    Example:
        >>> config = load_config("cascadeflow.yaml")
        >>> agent = create_agent_from_config(config, verbose=True)
    """
    # Import here to avoid circular imports
    from .agent import CascadeAgent

    # Parse models (required)
    if "models" not in config:
        raise ValueError("Config must include 'models' list")

    models = parse_models(config["models"])

    # Parse domains (optional)
    domain_configs = None
    if "domains" in config:
        domain_configs = parse_domains(config["domains"])

    # Get settings
    settings = config.get("settings", {})

    # Build agent kwargs
    agent_kwargs = {
        "models": models,
        "enable_cascade": settings.get("enable_cascade", True),
        "verbose": settings.get("verbose", False),
    }

    # Add domain config if present
    if domain_configs:
        agent_kwargs["domain_configs"] = domain_configs
        agent_kwargs["enable_domain_detection"] = settings.get("enable_domain_detection", True)

    # Apply overrides
    agent_kwargs.update(overrides)

    return CascadeAgent(**agent_kwargs)


def load_agent(config_path: Union[str, Path], **overrides) -> "CascadeAgent":
    """
    Convenience function to load config and create agent in one step.

    Args:
        config_path: Path to config file
        **overrides: Override any config values

    Returns:
        Configured CascadeAgent instance

    Example:
        >>> agent = load_agent("cascadeflow.yaml", verbose=True)
        >>> result = await agent.run("Hello")
    """
    config = load_config(config_path)
    return create_agent_from_config(config, **overrides)


# Default config search paths
DEFAULT_CONFIG_PATHS = [
    "cascadeflow.yaml",
    "cascadeflow.yml",
    "cascadeflow.json",
    ".cascadeflow.yaml",
    ".cascadeflow.yml",
    ".cascadeflow.json",
    "config/cascadeflow.yaml",
    "config/cascadeflow.yml",
    "config/cascadeflow.json",
]


def find_config() -> Optional[Path]:
    """
    Find a cascadeflow config file in default locations.

    Searches in order:
    1. Current directory
    2. Home directory

    Returns:
        Path to config file if found, None otherwise
    """
    # Check current directory
    for name in DEFAULT_CONFIG_PATHS:
        path = Path(name)
        if path.exists():
            return path

    # Check home directory
    home = Path.home()
    for name in DEFAULT_CONFIG_PATHS:
        path = home / name
        if path.exists():
            return path

    return None


def load_default_agent(**overrides) -> "CascadeAgent":
    """
    Load agent from default config location.

    Searches for config file in standard locations and loads it.

    Args:
        **overrides: Override any config values

    Returns:
        Configured CascadeAgent instance

    Raises:
        FileNotFoundError: If no config file found
    """
    config_path = find_config()
    if config_path is None:
        raise FileNotFoundError(
            "No cascadeflow config file found. "
            f"Create one of: {', '.join(DEFAULT_CONFIG_PATHS[:3])}"
        )

    return load_agent(config_path, **overrides)


# Export example config as string for documentation
EXAMPLE_YAML_CONFIG = """# CascadeFlow Configuration
# Save as: cascadeflow.yaml

# Model cascade configuration (required)
models:
  # Drafter model (cheap, fast)
  - name: gpt-4o-mini
    provider: openai
    cost: 0.00015
    supports_tools: true

  # Verifier model (capable, expensive)
  - name: gpt-4o
    provider: openai
    cost: 0.0025
    supports_tools: true

# Domain-specific configurations (optional)
domains:
  code:
    drafter: deepseek-coder
    verifier: gpt-4o
    threshold: 0.85
    temperature: 0.2
    validation_method: syntax

  medical:
    drafter: gpt-4o-mini
    verifier: gpt-4
    threshold: 0.95
    temperature: 0.1
    validation_method: fact
    require_verifier: true

  general:
    drafter: gpt-4o-mini
    verifier: gpt-4o
    threshold: 0.70
    temperature: 0.7
    validation_method: quality

# Agent settings (optional)
settings:
  enable_cascade: true
  enable_domain_detection: true
  verbose: false
"""


EXAMPLE_JSON_CONFIG = """{
  "models": [
    {"name": "gpt-4o-mini", "provider": "openai", "cost": 0.00015},
    {"name": "gpt-4o", "provider": "openai", "cost": 0.0025}
  ],
  "domains": {
    "code": {
      "drafter": "deepseek-coder",
      "verifier": "gpt-4o",
      "threshold": 0.85,
      "temperature": 0.2,
      "validation_method": "syntax"
    }
  },
  "settings": {
    "enable_cascade": true,
    "enable_domain_detection": true,
    "verbose": false
  }
}
"""
