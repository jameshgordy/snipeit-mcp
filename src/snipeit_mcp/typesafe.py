"""TypeSafe AI (Jev) client — the optional judgment backend for the data-quality tools.

Jev is a *System One* model: it answers typed questions (yes/no, pick-one,
score) about a piece of state and returns calibrated probabilities. It never
generates text. The data-quality tools in :mod:`snipeit_mcp.tools.data_quality`
use it for bulk judgments over Snipe-IT reference data — duplicate detection and
matching free text to existing records — that would otherwise cost the calling
LLM many pages of context and tool calls.

The integration is **opt-in**: nothing here runs unless ``TYPESAFE_API_KEY`` is
set, and the tools that depend on it are hidden from ``tools/list`` otherwise
(see :func:`snipeit_mcp.mcp_server.apply_optional_tool_visibility`).

Environment variables (names match the official ``typesafe-sdk``):

* ``TYPESAFE_API_KEY`` — enables the integration.
* ``TYPESAFE_BASE_URL`` — default ``https://api.typesafe.ai``.
* ``TYPESAFE_DEFAULT_MODEL`` — default ``jev-latest``. Pin a version such as
  ``jev-1.13.0`` once you have tuned thresholds against your own data.
* ``TYPESAFE_TIMEOUT`` — per-request timeout in seconds, default ``10``.

Wire contract (verified against ``typesafe-sdk`` 0.7.2 on 2026-09-28):

``POST {base}/v1/systemone`` with ``{"state", "model", "questions"}``.
Every question is ``{"type": "noul"|"choice"|"score", "instructions", "criteria"}``.
The response is ``{"model", "answers": {name: answer}, "usage": {"input_tokens",
"output_tokens"}}`` where a ``choice`` answer carries ``choice``, ``confidence``
and ``probabilities``; a ``score`` answer carries ``score``, ``confidence``,
``legend`` and ``probabilities``; a ``noul`` answer carries ``noul`` (0–1).
Errors: 401 bad key, 422 validation (``detail`` list), 429 rate limit
(``Retry-After`` / ``retry-after-ms``), 529 overloaded.

We deliberately do not depend on ``typesafe-sdk``: the API is a single POST,
the SDK pulls in ``httpx2`` and ``tenacity``, and using :mod:`requests` keeps
the integration testable with the same ``responses`` fixtures as the rest of
the code base.
"""

from __future__ import annotations

import logging
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

from .config import ConfigError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENV_API_KEY = "TYPESAFE_API_KEY"
ENV_BASE_URL = "TYPESAFE_BASE_URL"
ENV_MODEL = "TYPESAFE_DEFAULT_MODEL"
ENV_TIMEOUT = "TYPESAFE_TIMEOUT"

DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"
DEFAULT_TIMEOUT = 10.0
SYSTEM_ONE_PATH = "/v1/systemone"

# Retry behaviour mirrors the official SDK's RetryPolicy defaults.
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

REQUEST_ID_HEADER = "x-typesafe-request-id"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TypeSafeError(Exception):
    """A failed TypeSafe API call (HTTP error, transport error, or malformed body)."""

    def __init__(self, message: str, *, status: int | None = None,
                 request_id: str | None = None):
        super().__init__(message)
        self.status = status
        self.request_id = request_id


class TypeSafeNotConfiguredError(TypeSafeError):
    """Raised when a Jev-backed tool runs without ``TYPESAFE_API_KEY`` set."""


NOT_CONFIGURED_MESSAGE = (
    "TypeSafe Jev is not configured. Set TYPESAFE_API_KEY (and optionally "
    "TYPESAFE_BASE_URL / TYPESAFE_DEFAULT_MODEL) to enable the data-quality tools. "
    "Get a key at https://console.typesafe.ai/keys."
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TypeSafeConfig:
    """Resolved TypeSafe settings. ``api_key`` is never logged or repr'd."""

    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    timeout: float = DEFAULT_TIMEOUT

    def __repr__(self) -> str:  # keep the key out of logs and tracebacks
        return (f"TypeSafeConfig(base_url={self.base_url!r}, model={self.model!r}, "
                f"timeout={self.timeout!r})")

    @classmethod
    def from_env(cls) -> TypeSafeConfig | None:
        """Build the config from ``TYPESAFE_*`` env vars, or ``None`` when no key is set.

        Read fresh on every call (not cached at import) so tests and long-lived
        processes see environment changes, matching the Snipe-IT client.
        """
        api_key = os.getenv(ENV_API_KEY, "").strip()
        if not api_key:
            return None
        if not api_key.isascii() or not api_key.isprintable() or " " in api_key:
            raise ConfigError(f"{ENV_API_KEY} must be printable ASCII without whitespace")

        base_url = (os.getenv(ENV_BASE_URL, "").strip() or DEFAULT_BASE_URL).rstrip("/")
        model = os.getenv(ENV_MODEL, "").strip() or DEFAULT_MODEL

        raw_timeout = os.getenv(ENV_TIMEOUT, "").strip()
        timeout = DEFAULT_TIMEOUT
        if raw_timeout:
            try:
                timeout = float(raw_timeout)
            except ValueError as exc:
                raise ConfigError(f"{ENV_TIMEOUT} must be a number of seconds, got: {raw_timeout}") from exc
            if timeout <= 0:
                raise ConfigError(f"{ENV_TIMEOUT} must be positive, got: {raw_timeout}")

        return cls(api_key=api_key, base_url=base_url, model=model, timeout=timeout)


def is_configured() -> bool:
    """``True`` when ``TYPESAFE_API_KEY`` is set (config errors count as configured
    so they surface loudly at call time rather than silently hiding the tools)."""
    try:
        return TypeSafeConfig.from_env() is not None
    except ConfigError:
        return True


# ---------------------------------------------------------------------------
# Helpers shared by the tools
# ---------------------------------------------------------------------------


def confidence_band(confidence: float | None) -> str:
    """Map a Jev confidence (0–1) to ``high`` / ``medium`` / ``low``."""
    if confidence is None:
        return "low"
    if confidence >= CONFIDENCE_HIGH:
        return "high"
    if confidence >= CONFIDENCE_LOW:
        return "medium"
    return "low"


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


def _error_message(response: requests.Response) -> str:
    status = response.status_code
    detail: Any = None
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        detail = body.get("detail") or body.get("error") or body.get("message")

    if status == 401:
        base = "TypeSafe authentication failed (check TYPESAFE_API_KEY)"
    elif status == 422:
        base = "TypeSafe rejected the request (validation error)"
    elif status == 429:
        base = "TypeSafe rate limit exceeded"
    elif status == 529:
        base = "TypeSafe is overloaded"
    else:
        base = f"TypeSafe API error {status}"

    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                loc = ".".join(str(p) for p in item.get("loc", []))
                parts.append(f"{loc}: {item.get('msg')}" if loc else str(item.get("msg")))
            else:
                parts.append(str(item))
        detail = "; ".join(parts)
    if detail:
        return f"{base}: {detail}"
    return base


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class TypeSafeClient:
    """Minimal synchronous client for ``POST /v1/systemone``.

    ``sleep`` is injectable so tests can assert retry delays without waiting.
    """

    def __init__(self, config: TypeSafeConfig | None = None, *,
                 sleep: Callable[[float], None] = time.sleep):
        cfg = config if config is not None else TypeSafeConfig.from_env()
        if cfg is None:
            raise TypeSafeNotConfiguredError(NOT_CONFIGURED_MESSAGE)
        self.config = cfg
        self._sleep = sleep

    @property
    def _url(self) -> str:
        return f"{self.config.base_url}{SYSTEM_ONE_PATH}"

    def _headers(self) -> dict[str, str]:
        from . import __version__  # noqa: PLC0415 — avoid import cycle at module load

        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"snipeit-mcp/{__version__}",
        }

    def system_one(self, state: Any, questions: dict[str, dict[str, Any]],
                   *, model: str | None = None) -> dict[str, Any]:
        """Evaluate ``questions`` against ``state`` and return the parsed response body.

        Retries 408/429/5xx and transport errors up to :data:`MAX_RETRIES` times,
        honouring ``Retry-After`` / ``retry-after-ms`` when present.
        """
        if not questions:
            raise TypeSafeError("At least one question is required")
        body = {"state": state, "model": model or self.config.model, "questions": questions}

        attempt = 0
        while True:
            try:
                response = requests.post(self._url, headers=self._headers(), json=body,
                                         timeout=self.config.timeout)
            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempt >= MAX_RETRIES:
                    raise TypeSafeError(f"TypeSafe request failed: {exc}") from exc
                self._sleep(_backoff(attempt))
                attempt += 1
                continue

            request_id = response.headers.get(REQUEST_ID_HEADER)
            if response.status_code in RETRY_STATUSES and attempt < MAX_RETRIES:
                delay = _parse_retry_after(response.headers)
                self._sleep(_backoff(attempt) if delay is None else delay)
                attempt += 1
                continue

            if response.status_code >= 400:
                raise TypeSafeError(_error_message(response), status=response.status_code,
                                    request_id=request_id)

            try:
                data = response.json()
            except ValueError as exc:
                raise TypeSafeError("TypeSafe returned a non-JSON body",
                                    status=response.status_code, request_id=request_id) from exc
            if not isinstance(data, dict) or not isinstance(data.get("answers"), dict):
                raise TypeSafeError("TypeSafe returned a malformed response (no 'answers')",
                                    status=response.status_code, request_id=request_id)
            return data
