"""Tests for the provider abstraction + OpenAI-compatible client.

These tests intentionally avoid pytest's ``tmp_path`` fixture (which the DSH
sandbox denies) and instead create throwaway temp dirs inside the workspace,
cleaning them up afterwards.
"""
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from enhance_this.providers import (
    OpenAICompatibleProvider,
    OllamaProvider,
    ProviderAuthError,
    ProviderModelNotFoundError,
    ProviderTimeoutError,
)
from enhance_this.providers.openai_compatible import (
    KNOWN_API_BASES,
    DEFAULT_API_MODELS,
    resolve_api_config,
)
from enhance_this import provider_manager as pm


# ---------------------------------------------------------------------------
# resolve_api_config
# ---------------------------------------------------------------------------

def test_resolve_defaults_to_openrouter():
    r = resolve_api_config({})
    assert r["provider_type"] == "openrouter"
    assert r["base_url"] == "https://openrouter.ai/api/v1"
    assert r["api_key"] is None
    assert r["default_model"] == "qwen/qwen3.8-27b:free"


def test_resolve_known_provider_spec():
    r = resolve_api_config({"api_provider": "groq", "api_key": "gk",
                            "api_model": "llama-3.1-8b-instant"})
    assert r["base_url"] == "https://api.groq.com/openai/v1"
    assert r["api_key"] == "gk"
    assert r["remembered_model"] == "llama-3.1-8b-instant"
    assert r["env_key"] == "GROQ_API_KEY"


def test_resolve_env_key_fallback(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    r = resolve_api_config({"api_provider": "openrouter"})
    assert r["api_key"] == "env-key"


def test_resolve_config_trumps_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-key")
    r = resolve_api_config({"api_provider": "openrouter", "api_key": "cfg-key"})
    assert r["api_key"] == "cfg-key"


def test_resolve_remembered_model_wins():
    r = resolve_api_config({"api_provider": "openai", "api_model": "gpt-4o-mini"})
    assert r["remembered_model"] == "gpt-4o-mini"
    assert r["default_model"] == "gpt-4o-mini"


# ---------------------------------------------------------------------------
# OpenAICompatibleProvider streaming
# ---------------------------------------------------------------------------

def _sse(lines, status_code=200, headers_auth=True):
    m = MagicMock()
    m.status_code = status_code
    # Real iter_lines(decode_unicode=True) yields str.
    m.iter_lines.return_value = lines
    return m


def test_generate_stream_chunks():
    prov = OpenAICompatibleProvider("https://x/v1", "KEY", timeout=5)
    sess = MagicMock()
    prov.session = sess
    lines = [
        'data: ' + json.dumps({"choices": [{"delta": {"content": "Hi "}}]}),
        'data: ' + json.dumps({"choices": [{"delta": {"content": "there"}}]}),
        'data: ' + json.dumps({"choices": [{"delta": {}, "finish_reason": "stop"}]}),
    ]
    sess.post.return_value = _sse(lines)
    chunks = list(prov.generate_stream("m", "p", 0.7, 100))
    assert chunks == ["Hi ", "there"]

    payload = sess.post.call_args.kwargs["json"]
    assert payload["model"] == "m"
    assert payload["stream"] is True
    assert payload["messages"] == [{"role": "user", "content": "p"}]
    assert prov._chat_endpoint == "https://x/v1/chat/completions"


def test_generate_stream_auth_error():
    prov = OpenAICompatibleProvider("https://x/v1", "KEY", timeout=5)
    sess = MagicMock()
    prov.session = sess
    sess.post.return_value = _sse([], status_code=401)
    with pytest.raises(ProviderAuthError):
        list(prov.generate_stream("m", "p", 0.7, 100))


def test_generate_stream_model_not_found():
    prov = OpenAICompatibleProvider("https://x/v1", "KEY", timeout=5)
    sess = MagicMock()
    prov.session = sess
    sess.post.return_value = _sse([], status_code=404)
    with pytest.raises(ProviderModelNotFoundError):
        list(prov.generate_stream("m", "p", 0.7, 100))


def test_generate_stream_missing_key():
    prov = OpenAICompatibleProvider("https://x/v1", None, timeout=5)
    with pytest.raises(ProviderAuthError):
        list(prov.generate_stream("m", "p", 0.7, 100))


def test_generate_stream_timeout():
    import requests
    prov = OpenAICompatibleProvider("https://x/v1", "KEY", timeout=5)
    sess = MagicMock()
    prov.session = sess
    sess.post.side_effect = requests.exceptions.Timeout
    with pytest.raises(ProviderTimeoutError):
        list(prov.generate_stream("m", "p", 0.7, 100))


def test_list_models_parses_data():
    prov = OpenAICompatibleProvider("https://x/v1", "KEY", timeout=5)
    sess = MagicMock()
    prov.session = sess
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": [{"id": "a"}, {"id": "b", "discarded": 1}]}
    sess.get.return_value = resp
    assert prov.list_models() == ["a", "b"]


def test_list_models_missing_key_returns_empty():
    prov = OpenAICompatibleProvider("https://x/v1", None, timeout=5)
    assert prov.list_models() == []


# ---------------------------------------------------------------------------
# provider_manager
# ---------------------------------------------------------------------------

def test_build_provider_ollama():
    p = pm.build_provider({"provider": "ollama", "ollama_host": "http://h:1234", "timeout": 5})
    assert isinstance(p, OllamaProvider)
    assert p.host == "http://h:1234"


def test_build_provider_api():
    p = pm.build_provider({"provider": "api", "api_key": "k", "timeout": 5})
    assert isinstance(p, OpenAICompatibleProvider)


def test_build_provider_unknown_raises():
    with pytest.raises(pm.NoProviderConfiguredError):
        pm.build_provider({"provider": "bogus"}, timeout=5)


def test_default_api_model_for(monkeypatch):
    cfg = {"api_provider": "openai", "api_model": "gpt-4o-mini"}
    assert pm.default_api_model_for(cfg) == "gpt-4o-mini"


@pytest.fixture
def workdir():
    """A throwaway dir inside the workspace (sandbox-writable).

    Uses Path.mkdir rather than tempfile.mkdtemp because the latter creates
    directories the DSH sandbox refuses to write into.
    """
    d = Path("pmtest_work") / "cfg"
    d.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d.parent, ignore_errors=True)


def test_persist_provider_selection(workdir):
    p = workdir / "config.yaml"
    pm.persist_provider_selection(str(p), provider="api",
                                  api_model="anthropic/claude-3.5-sonnet")
    import yaml
    data = yaml.safe_load(p.read_text())
    assert data["provider"] == "api"
    assert data["api_model"] == "anthropic/claude-3.5-sonnet"


def test_persist_merges_not_clobber(workdir):
    p = workdir / "config.yaml"
    pm.persist_provider_selection(str(p), provider="api", api_model="m1")
    pm.persist_provider_selection(str(p), api_key="sk-123")
    import yaml
    data = yaml.safe_load(p.read_text())
    assert data["api_model"] == "m1"          # preserved
    assert data["api_key"] == "sk-123"        # added
    assert data["provider"] == "api"          # preserved