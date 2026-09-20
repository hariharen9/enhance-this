"""Resolver that turns a config dict into the active provider client.

Also owns writing the user's chosen provider/model selection back to config
so the choice is remembered across runs.
"""
import yaml
from typing import Dict, Any, Optional

from .config import (
    DEFAULT_CONFIG,
    get_config_path,
)
from .providers.base import BaseProvider
from .providers.ollama import OllamaProvider
from .providers.openai_compatible import (
    OpenAICompatibleProvider,
    resolve_api_config,
)


class NoProviderConfiguredError(Exception):
    """Raised when the configured provider is unknown."""


def build_provider(
    config: Dict[str, Any],
    timeout: Optional[int] = None,
    provider: Optional[str] = None,
) -> BaseProvider:
    """Instantiate the provider selected by the config.

    ``provider`` overrides config's ``provider`` key when supplied.
    """
    provider = (provider or config.get("provider") or "ollama").lower().strip()
    timeout = timeout if timeout is not None else int(config.get("timeout", 30))

    if provider in ("ollama", "local"):
        host = config.get("ollama_host") or DEFAULT_CONFIG["ollama_host"]
        return OllamaProvider(host=host, timeout=timeout)

    if provider in ("api", "openrouter", "openai", "groq", "together", "deepseek", "mistral"):
        resolved = resolve_api_config(config)
        return OpenAICompatibleProvider(
            base_url=resolved["base_url"],
            api_key=resolved["api_key"],
            timeout=timeout,
        )

    raise NoProviderConfiguredError(
        f"Unknown provider '{provider}'. Use 'ollama' or 'api' in config."
    )


def default_api_model_for(config: Dict[str, Any]) -> str:
    """The API model to use when none was explicitly chosen yet."""
    resolved = resolve_api_config(config)
    return resolved["remembered_model"] or resolved["default_model"]


def resolve_api_model(config: Dict[str, Any], explicit: Optional[str]) -> Optional[str]:
    """Pick the API model, favouring an explicit CLI choice, then a remembered
    one, then the configured default."""
    if explicit:
        return explicit
    return default_api_model_for(config) or None


def persist_provider_selection(
    config_path: Optional[str],
    *,
    provider: Optional[str] = None,
    api_model: Optional[str] = None,
    api_provider: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base_url: Optional[str] = None,
) -> None:
    """Persist the chosen provider / API model so they are remembered.

    Reads the existing config file (or starts from defaults), applies the
    provided overrides, and writes it back. Missing keys are preserved.
    """
    path = get_config_path(config_path)
    current: Dict[str, Any] = {}
    if path.exists():
        try:
            with open(path, "r") as f:
                loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                current = loaded
        except (yaml.YAMLError, IOError):
            current = {}

    if provider is not None:
        current["provider"] = provider
    if api_provider is not None:
        current["api_provider"] = api_provider
    if api_model is not None:
        current["api_model"] = api_model
    if api_key is not None:
        current["api_key"] = api_key
    if api_base_url is not None:
        current["api_base_url"] = api_base_url

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(current, f, default_flow_style=False, sort_keys=False)