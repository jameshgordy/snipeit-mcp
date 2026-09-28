"""Tests for the TypeSafe (Jev) client: configuration, exact wire format, retries, errors.

Only HTTP is mocked (``responses``); the real client code runs.
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
import requests
import responses

from snipeit_mcp import typesafe
from snipeit_mcp.config import ConfigError
from snipeit_mcp.typesafe import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_TIMEOUT,
    TypeSafeClient,
    TypeSafeConfig,
    TypeSafeError,
    TypeSafeNotConfiguredError,
    add_usage,
    confidence_band,
)

URL = "https://api.typesafe.ai/v1/systemone"
QUESTIONS = {"q": {"type": "noul", "instructions": "Is it?"}}
OK_BODY = {
    "model": "jev-1.13.0",
    "answers": {"q": {"type": "noul", "noul": 0.9}},
    "usage": {"input_tokens": 10, "output_tokens": 1},
}
TYPESAFE_VARS = ("TYPESAFE_API_KEY", "TYPESAFE_BASE_URL", "TYPESAFE_DEFAULT_MODEL", "TYPESAFE_TIMEOUT")


@pytest.fixture
def typesafe_env():
    """A clean TypeSafe environment with only the API key set."""
    with patch.dict(os.environ, {"TYPESAFE_API_KEY": "ts-key-123"}):
        for var in TYPESAFE_VARS[1:]:
            os.environ.pop(var, None)
        yield


@pytest.fixture
def no_typesafe_env():
    with patch.dict(os.environ, {}):
        for var in TYPESAFE_VARS:
            os.environ.pop(var, None)
        yield


class TestConfig:
    def test_missing_key_means_not_configured(self, no_typesafe_env):
        assert TypeSafeConfig.from_env() is None
        assert typesafe.is_configured() is False

    def test_defaults(self, typesafe_env):
        cfg = TypeSafeConfig.from_env()
        assert cfg is not None
        assert cfg.api_key == "ts-key-123"
        assert cfg.base_url == DEFAULT_BASE_URL == "https://api.typesafe.ai"
        assert cfg.model == DEFAULT_MODEL == "jev-latest"
        assert cfg.timeout == DEFAULT_TIMEOUT == 10.0
        assert typesafe.is_configured() is True

    def test_key_never_in_repr(self, typesafe_env):
        assert "ts-key-123" not in repr(TypeSafeConfig.from_env())

    def test_overrides(self, typesafe_env):
        with patch.dict(os.environ, {
            "TYPESAFE_BASE_URL": "https://jev.internal/",
            "TYPESAFE_DEFAULT_MODEL": "jev-1.13.0",
            "TYPESAFE_TIMEOUT": "2.5",
        }):
            cfg = TypeSafeConfig.from_env()
        assert cfg.base_url == "https://jev.internal"  # trailing slash stripped
        assert cfg.model == "jev-1.13.0"
        assert cfg.timeout == 2.5

    @pytest.mark.parametrize("bad", ["abc", "0", "-3"])
    def test_bad_timeout_is_config_error(self, typesafe_env, bad):
        with patch.dict(os.environ, {"TYPESAFE_TIMEOUT": bad}):
            with pytest.raises(ConfigError):
                TypeSafeConfig.from_env()
            # A broken config still counts as "configured" so the error surfaces
            # at call time instead of silently hiding the tools.
            assert typesafe.is_configured() is True

    def test_key_with_whitespace_is_config_error(self, typesafe_env):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "bad key"}):
            with pytest.raises(ConfigError):
                TypeSafeConfig.from_env()

    def test_blank_key_means_not_configured(self, typesafe_env):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "   "}):
            assert TypeSafeConfig.from_env() is None


class TestClient:
    def test_not_configured_raises(self, no_typesafe_env):
        with pytest.raises(TypeSafeNotConfiguredError) as exc:
            TypeSafeClient()
        assert "TYPESAFE_API_KEY" in str(exc.value)

    @responses.activate
    def test_posts_exact_request(self, typesafe_env):
        responses.add(responses.POST, URL, json=OK_BODY, status=200,
                      headers={"x-typesafe-request-id": "req-1"})
        client = TypeSafeClient(sleep=lambda _s: None)

        data = client.system_one({"text": "hi"}, QUESTIONS)

        assert data == OK_BODY
        assert len(responses.calls) == 1
        req = responses.calls[0].request
        assert req.url == URL
        assert json.loads(req.body) == {
            "state": {"text": "hi"},
            "model": "jev-latest",
            "questions": QUESTIONS,
        }
        assert req.headers["Authorization"] == "Bearer ts-key-123"
        assert req.headers["Content-Type"] == "application/json"
        assert req.headers["Accept"] == "application/json"
        assert req.headers["User-Agent"].startswith("snipeit-mcp/")

    @responses.activate
    def test_model_override_and_env_model(self, typesafe_env):
        responses.add(responses.POST, URL, json=OK_BODY)
        responses.add(responses.POST, URL, json=OK_BODY)
        with patch.dict(os.environ, {"TYPESAFE_DEFAULT_MODEL": "jev-1.13.0"}):
            client = TypeSafeClient(sleep=lambda _s: None)
        client.system_one("s", QUESTIONS)
        client.system_one("s", QUESTIONS, model="jev-preview")
        assert json.loads(responses.calls[0].request.body)["model"] == "jev-1.13.0"
        assert json.loads(responses.calls[1].request.body)["model"] == "jev-preview"

    @responses.activate
    def test_custom_base_url(self, typesafe_env):
        responses.add(responses.POST, "https://jev.internal/v1/systemone", json=OK_BODY)
        with patch.dict(os.environ, {"TYPESAFE_BASE_URL": "https://jev.internal/"}):
            client = TypeSafeClient(sleep=lambda _s: None)
        client.system_one("s", QUESTIONS)
        assert responses.calls[0].request.url == "https://jev.internal/v1/systemone"

    @responses.activate
    def test_sends_timeout(self, typesafe_env):
        responses.add(responses.POST, URL, json=OK_BODY)
        with patch.dict(os.environ, {"TYPESAFE_TIMEOUT": "3"}):
            client = TypeSafeClient(sleep=lambda _s: None)
        with patch("snipeit_mcp.typesafe.requests.post", wraps=requests.post) as post:
            client.system_one("s", QUESTIONS)
        assert post.call_args.kwargs["timeout"] == 3.0

    @responses.activate
    def test_retries_429_honouring_retry_after_ms(self, typesafe_env):
        responses.add(responses.POST, URL, json={"detail": "slow down"}, status=429,
                      headers={"retry-after-ms": "10"})
        responses.add(responses.POST, URL, json=OK_BODY)
        sleeps: list[float] = []
        client = TypeSafeClient(sleep=sleeps.append)

        assert client.system_one("s", QUESTIONS) == OK_BODY
        assert len(responses.calls) == 2
        assert sleeps == [0.01]

    @responses.activate
    def test_retries_429_honouring_retry_after_seconds(self, typesafe_env):
        responses.add(responses.POST, URL, status=429, headers={"Retry-After": "2"})
        responses.add(responses.POST, URL, json=OK_BODY)
        sleeps: list[float] = []
        TypeSafeClient(sleep=sleeps.append).system_one("s", QUESTIONS)
        assert sleeps == [2.0]

    @responses.activate
    def test_retries_529_with_backoff(self, typesafe_env):
        responses.add(responses.POST, URL, status=529)
        responses.add(responses.POST, URL, status=529)
        responses.add(responses.POST, URL, json=OK_BODY)
        sleeps: list[float] = []

        assert TypeSafeClient(sleep=sleeps.append).system_one("s", QUESTIONS) == OK_BODY
        assert len(responses.calls) == 3
        assert len(sleeps) == 2
        # Exponential: first retry ≤ 0.5s, second ≤ 1.0s, both > 0 (jitter ≤ 25%).
        assert 0.375 <= sleeps[0] <= 0.5
        assert 0.75 <= sleeps[1] <= 1.0

    @responses.activate
    def test_gives_up_after_max_retries(self, typesafe_env):
        for _ in range(3):
            responses.add(responses.POST, URL, status=500, json={"error": "boom"})
        client = TypeSafeClient(sleep=lambda _s: None)

        with pytest.raises(TypeSafeError) as exc:
            client.system_one("s", QUESTIONS)
        assert exc.value.status == 500
        assert "boom" in str(exc.value)
        assert len(responses.calls) == 3  # initial + MAX_RETRIES

    @responses.activate
    def test_401_not_retried(self, typesafe_env):
        responses.add(responses.POST, URL, status=401, json={"detail": "Invalid API key"})
        client = TypeSafeClient(sleep=lambda _s: None)

        with pytest.raises(TypeSafeError) as exc:
            client.system_one("s", QUESTIONS)
        assert exc.value.status == 401
        assert "TYPESAFE_API_KEY" in str(exc.value)
        assert len(responses.calls) == 1

    @responses.activate
    def test_422_detail_is_readable(self, typesafe_env):
        responses.add(
            responses.POST, URL, status=422,
            headers={"x-typesafe-request-id": "req-422"},
            json={"detail": [{"loc": ["body", "questions", "q", "criteria"],
                              "msg": "Field required", "type": "missing"}]},
        )
        with pytest.raises(TypeSafeError) as exc:
            TypeSafeClient(sleep=lambda _s: None).system_one("s", QUESTIONS)
        assert exc.value.status == 422
        assert exc.value.request_id == "req-422"
        assert "body.questions.q.criteria: Field required" in str(exc.value)

    @responses.activate
    def test_malformed_body_is_error(self, typesafe_env):
        responses.add(responses.POST, URL, json={"foo": 1})
        with pytest.raises(TypeSafeError, match="malformed"):
            TypeSafeClient(sleep=lambda _s: None).system_one("s", QUESTIONS)

    @responses.activate
    def test_non_json_body_is_error(self, typesafe_env):
        responses.add(responses.POST, URL, body="nope", status=200)
        with pytest.raises(TypeSafeError, match="non-JSON"):
            TypeSafeClient(sleep=lambda _s: None).system_one("s", QUESTIONS)

    @responses.activate
    def test_connection_errors_are_retried(self, typesafe_env):
        responses.add(responses.POST, URL, body=requests.ConnectionError("down"))
        responses.add(responses.POST, URL, body=requests.ConnectionError("down"))
        responses.add(responses.POST, URL, json=OK_BODY)
        sleeps: list[float] = []
        assert TypeSafeClient(sleep=sleeps.append).system_one("s", QUESTIONS) == OK_BODY
        assert len(responses.calls) == 3
        assert len(sleeps) == 2

    @responses.activate
    def test_connection_error_gives_up(self, typesafe_env):
        for _ in range(3):
            responses.add(responses.POST, URL, body=requests.ConnectionError("down"))
        with pytest.raises(TypeSafeError, match="down"):
            TypeSafeClient(sleep=lambda _s: None).system_one("s", QUESTIONS)

    def test_empty_questions_rejected(self, typesafe_env):
        with pytest.raises(TypeSafeError):
            TypeSafeClient(sleep=lambda _s: None).system_one("s", {})


class TestHelpers:
    @pytest.mark.parametrize("value,band", [
        (0.99, "high"), (0.9, "high"), (0.89, "medium"), (0.5, "medium"),
        (0.49, "low"), (0.0, "low"), (None, "low"),
    ])
    def test_confidence_band(self, value, band):
        assert confidence_band(value) == band

    def test_add_usage_accumulates_and_ignores_junk(self):
        total: dict[str, int] = {}
        add_usage(total, {"input_tokens": 5, "output_tokens": 1})
        add_usage(total, {"input_tokens": 7, "output_tokens": "x"})
        add_usage(total, None)
        add_usage(total, "garbage")
        assert total == {"input_tokens": 12, "output_tokens": 1}

    def test_parse_retry_after(self):
        parse = typesafe._parse_retry_after
        assert parse({"retry-after-ms": "250"}) == 0.25
        assert parse({"Retry-After": "3"}) == 3.0
        assert parse({"retry-after-ms": "250", "Retry-After": "3"}) == 0.25  # ms wins
        assert parse({"Retry-After": "9999"}) == typesafe.RETRY_AFTER_CAP
        assert parse({"Retry-After": "soon"}) is None
        assert parse({}) is None
