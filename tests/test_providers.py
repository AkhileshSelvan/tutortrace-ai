import io
import json
import socket
from http.client import IncompleteRead
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

from tutortrace.providers import adapters, http
from tutortrace.providers.adapters import OllamaProvider, RemoteProvider, OllamaEmbedder
from tutortrace.providers.llm import ProviderConfig, InferenceError, InferenceTimeout, ModelUnavailable


@pytest.mark.parametrize("kwargs", [{"provider":"unknown"}, {"model":""}, {"base_url":"https://user:secret@example.org"},
                                   {"base_url":"http://example.org"}, {"base_url":"https://example.org"},
                                   {"timeout":0}, {"output_tokens":20}, {"base_url":"http://localhost?key=secret"}])
def test_invalid_configuration(kwargs):
    with pytest.raises(InferenceError):
        ProviderConfig(**kwargs)


def test_key_is_not_exposed_in_config_repr():
    assert "test-secret-value" not in repr(ProviderConfig(api_key="test-secret-value"))


def test_remote_requires_explicit_credentials():
    provider = RemoteProvider(ProviderConfig(provider="openai-compatible", model="configured", base_url="https://example.org/v1"))
    assert not provider.status().available
    with pytest.raises(ModelUnavailable):
        provider.complete([], {})


def test_ollama_success_and_payload(monkeypatch):
    request = Mock(side_effect=[{"models":[{"name":"qwen3:4b","digest":"abc"}]},
                               {"done":True,"done_reason":"stop","message":{"content":"{}"}}])
    monkeypatch.setattr(adapters, "request_json", request)
    completion = OllamaProvider(ProviderConfig()).complete([], {"type":"object"})
    assert completion.provider == "ollama" and completion.content == "{}"
    payload = request.call_args.args[1]
    assert payload["think"] is False and payload["stream"] is False and payload["format"] == {"type":"object"}


def test_missing_and_cloud_models_are_not_used(monkeypatch):
    monkeypatch.setattr(adapters, "request_json", lambda *a, **k: {"models":[]})
    assert not OllamaProvider(ProviderConfig()).status().available
    monkeypatch.setattr(adapters, "request_json", lambda *a, **k: {"models":[{"name":"qwen3:4b", "remote_model":"remote"}]})
    with pytest.raises(ModelUnavailable, match="Cloud"):
        OllamaProvider(ProviderConfig()).complete([], {})


@pytest.mark.parametrize("response", [{"done":False}, {"done":True,"done_reason":"length"}, {"done":True,"message":{}},
                                      {"done":True,"message":{"content":123}}])
def test_incomplete_ollama_response(monkeypatch, response):
    provider = OllamaProvider(ProviderConfig())
    monkeypatch.setattr(provider, "model_info", lambda: {})
    monkeypatch.setattr(adapters, "request_json", lambda *a, **k: response)
    with pytest.raises(InferenceError):
        provider.complete([], {})


def test_remote_request_and_response(monkeypatch):
    request = Mock(return_value={"choices":[{"finish_reason":"stop","message":{"content":"{}"}}]})
    monkeypatch.setattr(adapters, "request_json", request)
    provider = RemoteProvider(ProviderConfig(provider="openai-compatible", model="chosen", base_url="https://example.org/v1", api_key="test-only"))
    assert provider.complete([], {}).content == "{}"
    assert request.call_args.args[0] == "https://example.org/v1/chat/completions"
    assert request.call_args.kwargs["api_key"] == "test-only"


@pytest.mark.parametrize("exception,error", [(socket.timeout(), InferenceTimeout), (URLError(socket.timeout()), InferenceTimeout),
                                           (URLError("offline"), ModelUnavailable),
                                           (HTTPError("url",404,"secret",{},io.BytesIO(b"secret")), ModelUnavailable),
                                           (HTTPError("url",401,"secret",{},io.BytesIO(b"secret")), InferenceError)])
def test_transport_failures_are_safe(monkeypatch, exception, error):
    monkeypatch.setattr(http, "build_opener", lambda *a: Mock(open=Mock(side_effect=exception)))
    with pytest.raises(error) as caught:
        http.request_json("http://localhost/api/chat")
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("data", [b"not json", b"[]", b"x"*(8*1024*1024+1)], ids=["malformed-json", "wrong-envelope", "oversized"])
def test_transport_rejects_bad_response(monkeypatch, data):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = data
    monkeypatch.setattr(http, "build_opener", lambda *a: Mock(open=Mock(return_value=response)))
    with pytest.raises(InferenceError):
        http.request_json("http://localhost/api/chat")


def test_redirects_not_followed():
    assert http.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example") is None


@pytest.mark.parametrize("vectors", [[], [[float('nan')]], [[1],[1,2]], [["bad"]]])
def test_bad_embedding_responses(monkeypatch, vectors):
    monkeypatch.setattr(adapters, "request_json", lambda *a, **k: {"embeddings":vectors})
    with pytest.raises(InferenceError):
        OllamaEmbedder().embed(["one"])


@pytest.mark.parametrize("response", [{}, {"choices":[]}, {"choices":[None]}, {"choices":[42]}, {"choices":[{"finish_reason":"stop","message":None}]}])
def test_malformed_remote_envelopes_are_typed_failures(monkeypatch, response):
    monkeypatch.setattr(adapters, "request_json", lambda *a, **k: response)
    provider = RemoteProvider(ProviderConfig(provider="openai-compatible", model="chosen", base_url="https://example.org/v1", api_key="test-only"))
    with pytest.raises(InferenceError):
        provider.complete([], {})


def test_interrupted_http_body_is_a_typed_failure(monkeypatch):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.side_effect = IncompleteRead(b"private text")
    monkeypatch.setattr(http, "build_opener", lambda *a: Mock(open=Mock(return_value=response)))
    with pytest.raises(InferenceError) as caught:
        http.request_json("http://localhost/api/chat")
    assert "private text" not in str(caught.value)


@pytest.mark.parametrize("url", ["http://localhost:abc", "http://[bad", "http://localhost:999999"])
def test_invalid_url_ports_and_hosts_fail_gracefully(url):
    with pytest.raises(InferenceError):
        ProviderConfig(base_url=url)


def test_invalid_model_capabilities_fail_status_check(monkeypatch):
    monkeypatch.setattr(adapters, "request_json", lambda *a, **k: {"models":[{"name":"qwen3:4b","capabilities":None}]})
    assert not OllamaProvider(ProviderConfig()).status().available
