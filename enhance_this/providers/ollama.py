"""Ollama provider — wraps the existing OllamaClient behind BaseProvider.

Keeps all of the existing local-model functionality (model download, preload,
streaming) intact while exposing the common provider interface.
"""
from typing import Iterator, List

from ..ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaError,
    OllamaTimeoutError,
)
from .base import (
    BaseProvider,
    ProviderConnectionError,
    ProviderError,
    ProviderTimeoutError,
)


class OllamaProvider(BaseProvider):
    name = "ollama"

    def __init__(self, host: str, timeout: int = 30):
        self.host = host
        self.timeout = timeout
        self._client = OllamaClient(host=host, timeout=timeout)

    @property
    def client(self) -> OllamaClient:
        """Access the underlying OllamaClient for Ollama-only features
        (e.g. download_model, preload_model)."""
        return self._client

    def is_available(self) -> bool:
        return self._client.is_running()

    def list_models(self) -> List[str]:
        return self._client.list_models()

    def generate_stream(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Iterator[str]:
        try:
            yield from self._client.generate_stream(
                model, prompt, temperature, max_tokens
            )
        except OllamaConnectionError as e:
            raise ProviderConnectionError(str(e)) from e
        except OllamaTimeoutError as e:
            raise ProviderTimeoutError(str(e)) from e
        except OllamaError as e:
            raise ProviderError(str(e)) from e