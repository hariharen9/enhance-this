"""Provider abstraction layer.

All AI backends (local Ollama, OpenAI-compatible APIs such as OpenRouter,
OpenAI, Groq, Together, ...) implement the same small interface so the CLI
does not care which one is active. See each subclass for details.
"""
from abc import ABC, abstractmethod
from typing import Iterator, List


class ProviderError(Exception):
    """Base error for any provider communication failure."""


class ProviderConnectionError(ProviderError):
    """The provider endpoint could not be reached / is not running."""


class ProviderTimeoutError(ProviderError):
    """A request to the provider exceeded its timeout."""


class ProviderAuthError(ProviderError):
    """The provider rejected our API key / credentials."""


class ProviderModelNotFoundError(ProviderError):
    """The requested model does not exist on the provider."""


class BaseProvider(ABC):
    """Common interface every provider must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """A stable, human-friendly identifier for the provider (e.g. 'ollama')."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the backend can be reached (and auth works, when relevant).

        This should never raise; it returns False on any failure.
        """

    @abstractmethod
    def list_models(self) -> List[str]:
        """Return the list of currently usable model identifiers.

        Returns an empty list when the backend is unreachable or errors out.
        """

    @abstractmethod
    def generate_stream(
        self,
        model: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> Iterator[str]:
        """Stream generated text chunks for the given prompt.

        Raises ProviderError subclasses on transport/auth failures so callers
        can present actionable messages; KeyboardInterrupt is left to the caller.
        """