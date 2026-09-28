"""System One protocol backend: TypeSafe Jev and compatible self-hosted servers.

Wire contract (verified against ``typesafe-sdk`` 0.7.2 on 2026-09-28):

``POST {base}/v1/systemone`` with ``{"state", "model", "questions"}``.
Every question is ``{"type": "noul"|"choice"|"score", "instructions", "criteria"}``.
The response is ``{"model", "answers": {name: answer}, "usage": {"input_tokens",
"output_tokens"}}`` where a ``choice`` answer carries ``choice``, ``confidence``
and ``probabilities``; a ``score`` answer carries ``score``, ``confidence``,
``legend`` and ``probabilities``; a ``noul`` answer carries ``noul`` (0–1).
Errors: 401 bad key, 422 validation (``detail`` list), 429 rate limit
(``Retry-After`` / ``retry-after-ms``), 529 overloaded.

The same protocol is served by open-weight decision models (Laya, CLM, ...)
via their own servers; point ``JUDGMENT_BASE_URL`` at one of those. We do not
depend on ``typesafe-sdk``: the API is a single POST, the SDK pulls in
``httpx2`` and ``tenacity``, and :mod:`requests` keeps the backend testable
with the same ``responses`` fixtures as the rest of the code base.
"""

from __future__ import annotations

import time
from typing import Any, Callable

import requests

from . import judgment
from .judgment import JudgmentConfig, JudgmentError

SYSTEM_ONE_PATH = "/v1/systemone"
REQUEST_ID_HEADER = "x-typesafe-request-id"


def _error_message(response: requests.Response) -> str:
    status = response.status_code
    if status == 401:
        base = "System One authentication failed (check JUDGMENT_API_KEY / TYPESAFE_API_KEY)"
    elif status == 404:
        base = "System One endpoint not found (check JUDGMENT_BASE_URL; the server must serve /v1/systemone)"
    elif status == 422:
        base = "System One server rejected the request (validation error)"
    elif status == 429:
        base = "System One rate limit exceeded"
    elif status == 529:
        base = "System One server is overloaded"
    else:
        base = f"System One API error {status}"
    detail = judgment.error_detail(response)
    return f"{base}: {detail}" if detail else base


class SystemOneClient:
    """Minimal synchronous client for ``POST /v1/systemone``."""

    name = "systemone"
    calibrated = True
    confidence_source = "model"

    def __init__(self, config: JudgmentConfig, *, sleep: Callable[[float], None] = time.sleep):
        self.config = config
        self._sleep = sleep
        self._session = requests.Session()

    @property
    def _url(self) -> str:
        return f"{self.config.base_url}{SYSTEM_ONE_PATH}"

    def _headers(self) -> dict[str, str]:
        from . import __version__  # noqa: PLC0415 — avoid import cycle at module load

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"snipeit-mcp/{__version__}",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def evaluate(self, state: Any, questions: dict[str, dict[str, Any]],
                 *, model: str | None = None) -> dict[str, Any]:
        """Evaluate ``questions`` against ``state`` and return the parsed response body."""
        if not questions:
            raise JudgmentError("At least one question is required")
        body = {"state": state, "model": model or self.config.model, "questions": questions}
        response = judgment.post_json(self._url, headers=self._headers(), body=body,
                                      timeout=self.config.timeout, sleep=self._sleep,
                                      session=self._session)
        request_id = response.headers.get(REQUEST_ID_HEADER)
        if response.status_code >= 400:
            raise JudgmentError(_error_message(response), status=response.status_code,
                                request_id=request_id)
        try:
            data = response.json()
        except ValueError as exc:
            raise JudgmentError("System One server returned a non-JSON body",
                                status=response.status_code, request_id=request_id) from exc
        if not isinstance(data, dict) or not isinstance(data.get("answers"), dict):
            raise JudgmentError("System One server returned a malformed response (no 'answers')",
                                status=response.status_code, request_id=request_id)
        return data
