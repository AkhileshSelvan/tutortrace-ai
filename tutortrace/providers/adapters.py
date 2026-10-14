"""Actual Ollama and credential-configured OpenAI-compatible chat adapters."""

import math
import time

from tutortrace.providers.http import request_json
from tutortrace.providers.llm import Completion, InferenceError, ModelUnavailable, ProviderConfig, ProviderStatus


class OllamaProvider:
    def __init__(self, config: ProviderConfig):
        self.config = config

    def model_info(self, model=None):
        name = model or self.config.model
        data = request_json(self.config.base_url.rstrip("/") + "/api/tags", timeout=5, local=True)
        models = data.get("models")
        if not isinstance(models, list) or not all(isinstance(item, dict) for item in models):
            raise InferenceError("Ollama returned an invalid model inventory.")
        for item in models:
            if item.get("name") in {name, name + ":latest"}:
                if item.get("remote_model") or item.get("remote_host") or ":cloud" in name:
                    raise ModelUnavailable("Cloud Ollama models are not enabled by the local adapter.")
                return item
        raise ModelUnavailable(f"Local model '{name}' is not installed. Choose an installed model; the app never downloads models.")

    def status(self):
        try:
            info = self.model_info()
            if "capabilities" in info and (not isinstance(info["capabilities"], list) or "completion" not in info["capabilities"]):
                raise ModelUnavailable("The selected model does not support text generation.")
            return ProviderStatus(True, "Installed locally; generation readiness is checked when you ask.")
        except InferenceError as exc:
            return ProviderStatus(False, str(exc))

    def complete(self, messages, schema):
        self.model_info()
        start = time.perf_counter()
        data = request_json(self.config.base_url.rstrip("/") + "/api/chat", {
            "model": self.config.model, "messages": messages, "stream": False,
            "think": False, "format": schema, "keep_alive": "2m",
            "options": {"temperature": 0, "seed": 17, "num_ctx": self.config.context_tokens,
                        "num_predict": self.config.output_tokens},
        }, timeout=self.config.timeout, local=True)
        if data.get("done") is not True or data.get("done_reason") == "length":
            raise InferenceError("Model output was incomplete. Increase the output limit or reduce the question scope.")
        message = data.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise InferenceError("Model returned no answer content.")
        return Completion(content, "ollama", self.config.model, time.perf_counter() - start)


class RemoteProvider:
    def __init__(self, config: ProviderConfig):
        self.config = config

    def status(self):
        return ProviderStatus(bool(self.config.api_key), "Remote credentials configured; connectivity is checked on request."
                              if self.config.api_key else "Missing TUTORTRACE_API_KEY. Consumer chat subscriptions do not provide API credentials.")

    def complete(self, messages, schema):
        if not self.config.api_key:
            raise ModelUnavailable("Configure TUTORTRACE_API_KEY to enable remote inference.")
        start = time.perf_counter()
        data = request_json(self.config.base_url.rstrip("/") + "/chat/completions", {
            "model": self.config.model, "messages": messages, "temperature": 0,
            "max_tokens": self.config.output_tokens, "stream": False,
            "response_format": {"type": "json_object"},
        }, timeout=self.config.timeout, api_key=self.config.api_key)
        try:
            choice = data["choices"][0]
            if choice.get("finish_reason") != "stop":
                raise InferenceError("Remote model output was incomplete or refused.")
            content = choice["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
            raise InferenceError("Remote provider returned an invalid completion envelope.") from exc
        return Completion(content, "openai-compatible", self.config.model, time.perf_counter() - start)


def make_provider(config=None):
    config = config or ProviderConfig.from_env()
    return OllamaProvider(config) if config.provider == "ollama" else RemoteProvider(config)


class OllamaEmbedder:
    def __init__(self, model="nomic-embed-text:latest", base_url="http://127.0.0.1:11434", timeout=60):
        self.config = ProviderConfig(model=model, base_url=base_url, timeout=timeout)

    def fingerprint(self):
        info = OllamaProvider(self.config).model_info()
        return self.config.base_url + ":" + self.config.model + ":" + info["digest"]

    def embed(self, texts, *, query=False):
        prefix = ("search_query: " if query else "search_document: ") if self.config.model.startswith("nomic-embed-text") else ""
        data = request_json(self.config.base_url.rstrip("/") + "/api/embed", {
            "model": self.config.model, "input": [prefix + text for text in texts],
            "truncate": False, "keep_alive": "0",
        }, timeout=self.config.timeout, local=True)
        vectors = data.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(texts):
            raise InferenceError("Embedding provider returned the wrong number of vectors.")
        for vector in vectors:
            if not isinstance(vector, list) or not vector or not all(type(x) in (int, float) and math.isfinite(x) for x in vector):
                raise InferenceError("Embedding provider returned an invalid vector.")
        if len({len(vector) for vector in vectors}) != 1:
            raise InferenceError("Embedding dimensions are inconsistent.")
        return vectors
