"""Judgment backends for the data-quality tools: configuration, selection, shared plumbing.

The data-quality tools (:mod:`snipeit_mcp.tools.data_quality`) ask *typed
questions* about a piece of state — yes/no (``noul``), pick-one (``choice``),
rubric level (``score``) — and expect an answer with a probability per option.
Two kinds of backend can answer them:

* **System One protocol** (:mod:`snipeit_mcp.systemone`) — ``POST /v1/systemone``
  as served by TypeSafe's hosted Jev and by self-hosted open-weight decision
  models that speak the same protocol (Laya, CLM, Rapid-MLX's system-one
  server, openjev). These models are trained to output *calibrated*
  probabilities, which is what the tools' confidence thresholds assume.
* **OpenAI-compatible chat** (:mod:`snipeit_mcp.chat_judge`) — any
  ``/v1/chat/completions`` server with JSON-schema structured outputs: Ollama,
  vLLM, LM Studio, llama.cpp, OpenRouter, OpenAI. The questions are rendered
  into a prompt and the model's self-reported confidence is used, which is
  **not** calibrated; optionally several samples are taken and vote frequency
  becomes the probability. Slower (seconds per call) but fully local.

Configuration (``JUDGMENT_*``; the ``TYPESAFE_*`` names of the official
``typesafe-sdk`` are accepted as aliases so a plain ``TYPESAFE_API_KEY``
enables Jev):

* ``JUDGMENT_BACKEND`` — ``systemone`` (default) or ``openai``.
* ``JUDGMENT_BASE_URL`` — default ``https://api.typesafe.ai`` for systemone,
  ``http://localhost:11434/v1`` (Ollama) for openai.
* ``JUDGMENT_MODEL`` — default ``jev-latest`` for systemone; required for openai.
* ``JUDGMENT_API_KEY`` — required by hosted services, usually absent for local servers.
* ``JUDGMENT_TIMEOUT`` — seconds per request; default 10 (systemone) / 120 (openai).
* ``JUDGMENT_SAMPLES`` — openai only, 1–10; >1 votes across samples.
* ``JUDGMENT_TIME_BUDGET`` — seconds one tool call may spend on backend calls in
  total (default 300); work still pending at the deadline is skipped and reported.

The integration is opt-in: with none of these set, :func:`is_configured` is
``False`` and the tools are hidden from ``tools/list``.
"""

from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Literal, Protocol

import requests

from .config import ConfigError

logger = logging.getLogger(__name__)

BackendName = Literal["systemone", "openai"]
BACKENDS: tuple[str, ...] = ("systemone", "openai")

ENV_BACKEND = "JUDGMENT_BACKEND"
ENV_BASE_URL = "JUDGMENT_BASE_URL"
ENV_MODEL = "JUDGMENT_MODEL"
ENV_API_KEY = "JUDGMENT_API_KEY"
ENV_TIMEOUT = "JUDGMENT_TIMEOUT"
ENV_SAMPLES = "JUDGMENT_SAMPLES"
ENV_TIME_BUDGET = "JUDGMENT_TIME_BUDGET"
# Aliases matching the official typesafe-sdk's environment variables.
ALIASES: dict[str, str] = {
    ENV_API_KEY: "TYPESAFE_API_KEY",
    ENV_BASE_URL: "TYPESAFE_BASE_URL",
    ENV_MODEL: "TYPESAFE_DEFAULT_MODEL",
    ENV_TIMEOUT: "TYPESAFE_TIMEOUT",
}
JUDGMENT_ENV_VARS: tuple[str, ...] = (
    ENV_BACKEND, ENV_BASE_URL, ENV_MODEL, ENV_API_KEY, ENV_TIMEOUT, ENV_SAMPLES,
    ENV_TIME_BUDGET, *ALIASES.values(),
)

SYSTEMONE_DEFAULT_BASE_URL = "https://api.typesafe.ai"
SYSTEMONE_DEFAULT_MODEL = "jev-latest"
SYSTEMONE_DEFAULT_TIMEOUT = 10.0
OPENAI_DEFAULT_BASE_URL = "http://localhost:11434/v1"  # Ollama's OpenAI-compatible endpoint
OPENAI_DEFAULT_TIMEOUT = 120.0
MAX_SAMPLES = 10
DEFAULT_TIME_BUDGET = 300.0

# Retry policy shared by both backends; mirrors the official typesafe-sdk defaults.
RETRY_STATUSES: frozenset[int] = frozenset({408, 429, *range(500, 600)})
MAX_RETRIES = 2
BACKOFF_INITIAL = 0.5
BACKOFF_MAX = 5.0
BACKOFF_JITTER = 0.25
RETRY_AFTER_CAP = 30.0

# Confidence bands from https://docs.typesafe.ai/confidence: above 0.9 act
# automatically, 0.5–0.9 proceed with confirmation/review, below 0.5 do not act.
CONFIDENCE_HIGH = 0.9
CONFIDENCE_LOW = 0.5

NOT_CONFIGURED_MESSAGE = (
    "No judgment backend configured. Set TYPESAFE_API_KEY for TypeSafe Jev; or "
    "JUDGMENT_BACKEND=systemone with JUDGMENT_BASE_URL for a self-hosted System One "
    "server (Laya, CLM, ...); or JUDGMENT_BACKEND=openai with JUDGMENT_BASE_URL and "
    "JUDGMENT_MODEL for an OpenAI-compatible chat server such as Ollama."
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class JudgmentError(Exception):
    """A failed backend call (HTTP error, transport error, or unusable reply)."""

    def __init__(self, message: str, *, status: int | None = None,
                 request_id: str | None = None):
        super().__init__(message)
        self.status = status
        self.request_id = request_id


class JudgmentNotConfiguredError(JudgmentError):
    """Raised when a judgment-backed tool runs with no backend configured."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def _env(name: str) -> str:
    """Env var value (stripped), falling back to its typesafe-sdk alias."""
    value = os.getenv(name, "").strip()
    if not value and name in ALIASES:
        value = os.getenv(ALIASES[name], "").strip()
    return value


def _positive_float(name: str, raw: str, default: float) -> float:
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number of seconds, got: {raw}") from exc
    if value <= 0:
        raise ConfigError(f"{name} must be positive, got: {raw}")
    return value


@dataclass(frozen=True)
class JudgmentConfig:
    """Resolved backend settings. ``api_key`` is never logged or repr'd."""

    backend: BackendName
    base_url: str
    model: str
    api_key: str | None
    timeout: float
    samples: int = 1
    time_budget: float = DEFAULT_TIME_BUDGET

    def __repr__(self) -> str:  # keep the key out of logs and tracebacks
        return (f"JudgmentConfig(backend={self.backend!r}, base_url={self.base_url!r}, "
                f"model={self.model!r}, timeout={self.timeout!r}, samples={self.samples!r}, "
                f"time_budget={self.time_budget!r}, api_key={'set' if self.api_key else 'unset'})")

    @classmethod
    def from_env(cls) -> JudgmentConfig | None:
        """Build the config from ``JUDGMENT_*`` / ``TYPESAFE_*`` env vars.

        Returns ``None`` when nothing at all is set. Read fresh on every call
        (not cached at import) so tests and long-lived processes see changes.
        """
        raw_backend = _env(ENV_BACKEND).lower()
        api_key = _env(ENV_API_KEY) or None
        base_url = _env(ENV_BASE_URL)
        model = _env(ENV_MODEL)
        if not (raw_backend or api_key or base_url or model):
            return None

        backend = raw_backend or "systemone"
        if backend not in BACKENDS:
            raise ConfigError(f"{ENV_BACKEND} must be one of {', '.join(BACKENDS)}, got: {raw_backend}")
        if api_key is not None and (not api_key.isascii() or not api_key.isprintable() or " " in api_key):
            raise ConfigError(f"{ENV_API_KEY} must be printable ASCII without whitespace")

        if backend == "systemone":
            base_url = (base_url or SYSTEMONE_DEFAULT_BASE_URL).rstrip("/")
            model = model or SYSTEMONE_DEFAULT_MODEL
            timeout = _positive_float(ENV_TIMEOUT, _env(ENV_TIMEOUT), SYSTEMONE_DEFAULT_TIMEOUT)
        else:
            base_url = (base_url or OPENAI_DEFAULT_BASE_URL).rstrip("/")
            if not model:
                raise ConfigError(
                    f"{ENV_MODEL} is required for the openai backend "
                    "(e.g. JUDGMENT_MODEL=qwen3:8b for Ollama)"
                )
            timeout = _positive_float(ENV_TIMEOUT, _env(ENV_TIMEOUT), OPENAI_DEFAULT_TIMEOUT)

        raw_samples = _env(ENV_SAMPLES)
        samples = 1
        if raw_samples:
            try:
                samples = int(raw_samples)
            except ValueError as exc:
                raise ConfigError(f"{ENV_SAMPLES} must be an integer, got: {raw_samples}") from exc
            if not 1 <= samples <= MAX_SAMPLES:
                raise ConfigError(f"{ENV_SAMPLES} must be between 1 and {MAX_SAMPLES}, got: {raw_samples}")
            if backend == "systemone" and samples != 1:
                logger.warning("%s is ignored by the systemone backend", ENV_SAMPLES)
                samples = 1

        time_budget = _positive_float(ENV_TIME_BUDGET, _env(ENV_TIME_BUDGET), DEFAULT_TIME_BUDGET)

        return cls(backend=backend, base_url=base_url, model=model, api_key=api_key,
                   timeout=timeout, samples=samples, time_budget=time_budget)


def is_configured() -> bool:
    """``True`` when any judgment backend setting is present.

    A broken configuration still counts as configured so the error surfaces at
    call time instead of silently hiding the tools.
    """
    try:
        return JudgmentConfig.from_env() is not None
    except ConfigError:
        return True


# ---------------------------------------------------------------------------
# Backend protocol and selection
# ---------------------------------------------------------------------------


class JudgmentBackend(Protocol):
    """What the tools need from a backend."""

    name: str
    calibrated: bool
    confidence_source: str
    config: JudgmentConfig

    def evaluate(self, state: Any, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Answer ``questions`` about ``state``.

        Returns ``{"model": str, "answers": {name: answer}, "usage": {...}}`` where
        answers use the System One shapes: ``{"type": "noul", "noul": p}``,
        ``{"type": "choice", "choice", "confidence", "probabilities"}``,
        ``{"type": "score", "score", "confidence", "legend", "probabilities"}``.
        """


def get_backend(config: JudgmentConfig | None = None, *,
                sleep: Callable[[float], None] = time.sleep) -> JudgmentBackend:
    """Resolve the configured backend, raising :class:`JudgmentNotConfiguredError` if none."""
    cfg = config if config is not None else JudgmentConfig.from_env()
    if cfg is None:
        raise JudgmentNotConfiguredError(NOT_CONFIGURED_MESSAGE)
    if cfg.backend == "openai":
        from .chat_judge import ChatJudgeClient  # noqa: PLC0415 — avoid import cycle

        return ChatJudgeClient(cfg, sleep=sleep)
    from .systemone import SystemOneClient  # noqa: PLC0415 — avoid import cycle

    return SystemOneClient(cfg, sleep=sleep)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def confidence_band(confidence: float | None) -> str:
    """Map a confidence (0–1) to ``high`` / ``medium`` / ``low``."""
    if confidence is None:
        return "low"
    if confidence >= CONFIDENCE_HIGH:
        return "high"
    if confidence >= CONFIDENCE_LOW:
        return "medium"
    return "low"


def concentration_confidence(probabilities: dict[str, float]) -> float:
    """TypeSafe's confidence statistic: how concentrated a distribution is.

    ``(n * p_max - 1) / (n - 1)`` — 1.0 when all mass is on one option, 0.0 when
    spread evenly. Used to derive a confidence for chat backends that only
    yield a distribution (vote frequencies).
    """
    n = len(probabilities)
    if n <= 1:
        return 1.0
    p_max = max(probabilities.values(), default=0.0)
    return round(max(0.0, min(1.0, (n * p_max - 1) / (n - 1))), 4)


def add_usage(total: dict[str, int], usage: Any) -> None:
    """Accumulate a response's ``usage`` block into ``total`` (in place)."""
    if not isinstance(usage, dict):
        return
    for key in ("input_tokens", "output_tokens"):
        value = usage.get(key)
        if isinstance(value, int):
            total[key] = total.get(key, 0) + value


def _parse_retry_after(headers: Any) -> float | None:
    """Delay in seconds from ``retry-after-ms`` or ``Retry-After``, else ``None``."""
    ms = headers.get("retry-after-ms")
    if ms:
        try:
            return min(max(float(ms) / 1000.0, 0.0), RETRY_AFTER_CAP)
        except ValueError:
            pass
    secs = headers.get("Retry-After")
    if secs:
        try:
            return min(max(float(secs), 0.0), RETRY_AFTER_CAP)
        except ValueError:
            return None
    return None


def _backoff(attempt: int) -> float:
    """Exponential backoff for the *n*-th retry (0-based) with jitter subtracted."""
    exponential = min(BACKOFF_INITIAL * (2 ** attempt), BACKOFF_MAX)
    return round(exponential * (1 - random.random() * BACKOFF_JITTER), 3)


# Malformed-configuration errors that no retry can fix.
_NON_RETRYABLE = (requests.exceptions.InvalidURL, requests.exceptions.MissingSchema,
                  requests.exceptions.InvalidSchema, requests.exceptions.InvalidHeader)


def post_json(url: str, *, headers: dict[str, str], body: dict[str, Any], timeout: float,
              sleep: Callable[[float], None] = time.sleep,
              session: requests.Session | None = None) -> requests.Response:
    """POST ``body`` as JSON with the shared retry policy.

    Retries 408/429/5xx and transport errors (any :class:`requests.RequestException`
    except malformed-URL/header errors) up to :data:`MAX_RETRIES` times, honouring
    ``Retry-After`` / ``retry-after-ms``. Returns the final response — the caller
    maps any remaining error status to a :class:`JudgmentError`. ``session``
    enables connection pooling across the many calls one tool invocation makes.
    """
    poster = session if session is not None else requests
    attempt = 0
    while True:
        try:
            response = poster.post(url, headers=headers, json=body, timeout=timeout)
        except _NON_RETRYABLE as exc:
            raise JudgmentError(f"Request to {url} failed: {exc}") from exc
        except requests.RequestException as exc:
            if attempt >= MAX_RETRIES:
                raise JudgmentError(f"Request to {url} failed: {exc}") from exc
            sleep(_backoff(attempt))
            attempt += 1
            continue

        if response.status_code in RETRY_STATUSES and attempt < MAX_RETRIES:
            delay = _parse_retry_after(response.headers)
            sleep(_backoff(attempt) if delay is None else delay)
            attempt += 1
            continue
        return response


def error_detail(response: requests.Response) -> str | None:
    """Best-effort human-readable error text from a JSON error body."""
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    detail: Any = body.get("detail") or body.get("error") or body.get("message")
    if isinstance(detail, dict):  # OpenAI-style {"error": {"message": ...}}
        detail = detail.get("message") or detail
    if isinstance(detail, list):  # FastAPI-style validation detail
        parts = []
        for item in detail:
            if isinstance(item, dict):
                loc = ".".join(str(p) for p in item.get("loc", []))
                parts.append(f"{loc}: {item.get('msg')}" if loc else str(item.get("msg")))
            else:
                parts.append(str(item))
        detail = "; ".join(parts)
    return str(detail) if detail else None
