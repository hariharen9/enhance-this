"""OpenAI-compatible API provider.

Talks to any backend that implements the OpenAI Chat Completions streaming
API (server-sent events over POST /chat/completions). This covers OpenRouter,
OpenAI, Groq, Together, DeepSeek, Mistral, and many others — the user only
needs to supply a base URL and an API key.

The provider emits a standard OpenAI-style event stream:

    data: {"id":"...","choices":[{"delta":{"content":"Hello "},"index":0,...}]}
    data: {"id":"...","choices":[{"delta":{},"finish_reason":"stop","index":0,...}]}
    data: [DONE]
"""
import json
import os
from typing import Iterator, List, Optional

import requests
from requests.adapters import HTTPAdapter, Retry
from rich.console import Console

from .base import (
    BaseProvider,
    ProviderAuthError,
    ProviderConnectionError,
    ProviderError,
    ProviderModelNotFoundError,
    ProviderTimeoutError,
)

console = Console()

# Standard-compliant endpoints that are known to support /chat/completions.
KNOWN_API_BASES = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "together": "https://api.together.xyz/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "mistral": "https://api.mistral.ai/v1",
}

# Known-good, cheap models per provider to suggest as defaults. These are
# fast and inexpensive, which is plenty for prompt enhancement.
DEFAULT_API_MODELS = {
    "openrouter": "qwen/qwen3.8-27b:free",
    "openai": "gpt-4o-mini",
    "groq": "llama-3.1-8b-instant",
    "together": "meta-llama/Llama-3.1-8B-Instruct-Turbo",
    "deepseek": "deepseek-chat",
    "mistral": "mistral-small-latest",
}

OPENAI_COMPAT_DEFAULTS = {
    "openai": {
        "base_url": KNOWN_API_BASES["openai"],
        "default_model": DEFAULT_API_MODELS["openai"],
        "env_key": "OPENAI_API_KEY",
    },
    "openrouter": {
        "base_url": KNOWN_API_BASES["openrouter"],
        "default_model": DEFAULT_API_MODELS["openrouter"],
        "env_key": "OPENROUTER_API_KEY",
    },
    "groq": {
        "base_url": KNOWN_API_BASES["groq"],
        "default_model": DEFAULT_API_MODELS["groq"],
        "env_key": "GROQ_API_KEY",
    },
    "together": {
        "base_url": KNOWN_API_BASES["together"],
        "default_model": DEFAULT_API_MODELS["together"],
        "env_key": "TOGETHER_API_KEY",
    },
    "deepseek": {
        "base_url": KNOWN_API_BASES["deepseek"],
        "default_model": DEFAULT_API_MODELS["deepseek"],
        "env_key": "DEEPSEEK_API_KEY",
    },
    "mistral": {
        "base_url": KNOWN_API_BASES["mistral"],
        "default_model": DEFAULT_API_MODELS["mistral"],
        "env_key": "MISTRAL_API_KEY",
    },
}


def resolve_api_config(config: dict) -> dict:
    """Resolve provider_type, base_url, api_key and default model from config.

    Values explicitly present in the config file take precedence, then a
    well-known environment variable (e.g. OPENROUTER_API_KEY) is used as a
    fallback, then a provider default.

    Returns a dict with keys: provider_type, base_url, api_key (may be None),
    default_model, env_key.
    """
    provider_type = config.get("api_provider") or "openrouter"

    spec = OPENAI_COMPAT_DEFAULTS.get(provider_type, {})
    default_base_url = spec.get("base_url", "https://openrouter.ai/api/v1")
    default_model = spec.get("default_model", DEFAULT_API_MODELS["openrouter"])
    env_key = spec.get("env_key")
    if provider_type == "openrouter":
        env_key = env_key or "OPENROUTER_API_KEY"

    base_url = (
        config.get("api_base_url")
        or os.environ.get("ENHANCE_THIS_API_BASE_URL")
        or default_base_url
    )
    base_url = base_url.rstrip("/")

    api_key = config.get("api_key") or (os.environ.get(env_key) if env_key else None)

    default_model = (
        config.get("api_default_model") or default_model
    )

    # The last model the user actually chose, if any.
    remembered_model = config.get("api_model")

    return {
        "provider_type": provider_type,
        "base_url": base_url,
        "api_key": api_key,
        "env_key": env_key,
        "default_model": default_model,
        "remembered_model": remembered_model,
    }


class OpenAICompatibleProvider(BaseProvider):
    name = "api"

    def __init__(self, base_url: str, api_key: Optional[str], timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self.session.headers.update(headers)
        retries = Retry(total=2, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount("http://", HTTPAdapter(max_retries=retries))
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    @property
    def _chat_endpoint(self) -> str:
        return f"{self.base_url}/chat/completions"

    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            # A cheap models-list call verifies auth + connectivity.
            self._list_models_request()
            return True
        except (ProviderAuthError, ProviderConnectionError, ProviderTimeoutError):
            return False
        except ProviderError:
            # 404 on /models is fine for some gateways; auth still worked.
            return True

    def list_models(self) -> List[str]:
        if not self.api_key:
            console.print(
                "[yellow]⚠[/yellow] No API key configured. Set it in "
                "`~/.enhance-this/config.yaml` (api_key) or via the "
                "OPENROUTER_API_KEY/OPENAI_API_KEY environment variable."
            )
            return []
        try:
            return self._list_models_request()
        except ProviderAuthError as e:
            console.print(f"[yellow]⚠[/yellow] {e}")
            return []
        except ProviderConnectionError as e:
            console.print(f"[yellow]⚠[/yellow] {e}")
            return []
        except ProviderTimeoutError as e:
            console.print(f"[yellow]⚠[/yellow] {e}")
            return []
        except ProviderError as e:
            console.print(f"[yellow]⚠[/yellow] Error listing models from API: {e}")
            return []

    def _list_models_request(self) -> List[str]:
        url = f"{self.base_url}/models"
        try:
            response = self.session.get(url, timeout=self.timeout)
        except requests.exceptions.ConnectionError:
            raise ProviderConnectionError(
                f"Could not connect to API provider at {self.base_url}. "
                "Check the base URL and your internet connection."
            ) from None
        except requests.exceptions.Timeout:
            raise ProviderTimeoutError(
                f"API provider request timed out after {self.timeout}s."
            ) from None
        except requests.RequestException as e:
            raise ProviderConnectionError(
                f"Error contacting API provider: {e}"
            ) from e

        if response.status_code in (401, 403):
            raise ProviderAuthError(
                "API provider rejected the key (HTTP %d). Check the API key "
                "in config or the provider environment variable." % response.status_code
            )
        if response.status_code == 404:
            # Gateway does not expose /models; that is okay for chat usage.
            return []
        if response.status_code != 200:
            raise ProviderError(
                f"API provider returned HTTP {response.status_code} listing models."
            )
        try:
            data = response.json()
        except ValueError:
            return []

        models = data.get("data") or []
        names = []
        for m in models:
            mid = m.get("id")
            if mid:
                names.append(mid)
        return names

    def _validate_key(self) -> None:
        if not self.api_key:
            raise ProviderAuthError(
                "No API key configured. Add `api_key` to `~/.enhance-this/config.yaml` "
                "or set the OPENROUTER_API_KEY/OPENAI_API_KEY environment variable."
            )

    def generate_stream(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Iterator[str]:
        self._validate_key()
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        try:
            response = self.session.post(
                self._chat_endpoint, json=payload, stream=True, timeout=self.timeout
            )
        except requests.exceptions.ConnectionError:
            raise ProviderConnectionError(
                f"Could not connect to API provider at {self.base_url}. "
                "Check the base URL and your internet connection."
            ) from None
        except requests.exceptions.Timeout:
            raise ProviderTimeoutError(
                f"API provider request timed out after {self.timeout}s. "
                "Try increasing the timeout in your config."
            ) from None
        except requests.RequestException as e:
            raise ProviderConnectionError(f"Error contacting API provider: {e}") from e

        if response.status_code in (401, 403):
            raise ProviderAuthError(
                "API provider rejected the key (HTTP %d). Check the API key "
                "in config or the provider environment variable." % response.status_code
            )
        if response.status_code == 404:
            raise ProviderModelNotFoundError(
                f"Model '{model}' was not found on the provider "
                f"(HTTP 404). Check the model name."
            )
        if response.status_code != 200:
            raise ProviderError(
                f"API provider returned HTTP {response.status_code}: "
                f"{response.text[:400]}"
            )

        try:
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                data_str = line[len("data:"):].strip()
                if not data_str or data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                choices = data.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield content
                finish = choices[0].get("finish_reason")
                if finish:
                    break
        except requests.exceptions.ConnectionError:
            raise ProviderConnectionError(
                f"Connection lost while streaming from {self.base_url}."
            ) from None
        except requests.exceptions.Timeout:
            raise ProviderTimeoutError(
                f"Stream from API provider timed out after {self.timeout}s."
            ) from None