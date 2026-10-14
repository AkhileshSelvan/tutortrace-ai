"""Provider-neutral inference contract; source validation belongs to the tutor."""

from dataclasses import dataclass, field
import os
from typing import Protocol
from urllib.parse import urlsplit

from tutortrace.errors import TutorTraceError


class InferenceError(TutorTraceError):
    code = "inference_error"


class ModelUnavailable(InferenceError):
    code = "model_unavailable"


class InferenceTimeout(InferenceError):
    code = "inference_timeout"


class InvalidAnswer(InferenceError):
    code = "invalid_answer"


@dataclass(frozen=True)
class ProviderConfig:
    provider: str = "ollama"
    model: str = "qwen3:4b"
    base_url: str = "http://127.0.0.1:11434"
    api_key: str = field(default="", repr=False, compare=False)
    timeout: float = 120
    context_tokens: int = 4096
    output_tokens: int = 900

    def __post_init__(self):
        try:
            parsed = urlsplit(self.base_url)
            parsed.port  # Validate a supplied port before making any request.
        except ValueError as exc:
            raise InferenceError("Provider URL has an invalid host or port.") from exc
        if self.provider not in {"ollama", "openai-compatible"}:
            raise InferenceError("Choose ollama or openai-compatible as the provider.")
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise InferenceError("Provider URL must not contain credentials, query parameters or fragments.")
        local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
            raise InferenceError("Remote inference requires HTTPS; HTTP is allowed only on loopback.")
        if self.provider == "ollama" and not local:
            raise InferenceError("The Ollama adapter is local-only. Use the remote adapter for remote inference.")
        if not self.model.strip() or len(self.model) > 200:
            raise ModelUnavailable("Configure a model name before using the AI tutor.")
        if not 1 <= self.timeout <= 600 or not 2048 <= self.context_tokens <= 32768 or not 128 <= self.output_tokens <= 4096:
            raise InferenceError("Invalid inference timeout or token limits.")

    @classmethod
    def from_env(cls):
        provider = os.getenv("TUTORTRACE_LLM_PROVIDER", "ollama")
        try:
            return cls(provider=provider,
                       model=os.getenv("TUTORTRACE_LLM_MODEL", "qwen3:4b" if provider == "ollama" else ""),
                       base_url=os.getenv("TUTORTRACE_LLM_URL", "http://127.0.0.1:11434" if provider == "ollama" else ""),
                       api_key=os.getenv("TUTORTRACE_API_KEY", ""),
                       timeout=float(os.getenv("TUTORTRACE_TIMEOUT", "120")),
                       context_tokens=int(os.getenv("TUTORTRACE_CONTEXT_TOKENS", "4096")),
                       output_tokens=int(os.getenv("TUTORTRACE_OUTPUT_TOKENS", "900")))
        except ValueError as exc:
            raise InferenceError("Inference limits must be numeric.") from exc


@dataclass(frozen=True)
class Completion:
    content: str
    provider: str
    model: str
    elapsed_seconds: float


@dataclass(frozen=True)
class ProviderStatus:
    available: bool
    message: str


class AnswerProvider(Protocol):
    config: ProviderConfig
    def status(self) -> ProviderStatus: ...
    def complete(self, messages: list[dict], schema: dict) -> Completion: ...
