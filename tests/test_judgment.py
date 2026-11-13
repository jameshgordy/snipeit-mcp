"""Tests for the judgment layer: configuration and aliases, backend selection, the
shared HTTP retry helper, and confidence helpers. Only HTTP is mocked."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
import requests
import responses

from snipeit_mcp import judgment
from snipeit_mcp.chat_judge import ChatJudgeClient
from snipeit_mcp.config import ConfigError
from snipeit_mcp.judgment import (
    JUDGMENT_ENV_VARS,
    JudgmentConfig,
    JudgmentError,
    JudgmentNotConfiguredError,
    add_usage,
    concentration_confidence,
    confidence_band,
    get_backend,
    post_json,
)
from snipeit_mcp.systemone import SystemOneClient

URL = "https://judge.example/v1/systemone"
BODY = {"state": "s", "model": "m", "questions": {"q": {"type": "noul"}}}
HEADERS = {"Content-Type": "application/json"}


@pytest.fixture
def clean_env():
    with patch.dict(os.environ, {}):
        for var in JUDGMENT_ENV_VARS:
            os.environ.pop(var, None)
        yield


class TestConfig:
    def test_nothing_set_means_not_configured(self, clean_env):
        assert JudgmentConfig.from_env() is None
        assert judgment.is_configured() is False

    def test_typesafe_key_alias_enables_systemone(self, clean_env):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "ts-key-123"}):
            cfg = JudgmentConfig.from_env()
        assert cfg == JudgmentConfig(backend="systemone", base_url="https://api.typesafe.ai",
                                     model="jev-latest", api_key="ts-key-123", timeout=10.0,
                                     samples=1, time_budget=300.0)

    def test_typesafe_aliases_for_url_model_timeout(self, clean_env):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "k", "TYPESAFE_BASE_URL": "https://jev.internal/",
                                     "TYPESAFE_DEFAULT_MODEL": "jev-1.13.0", "TYPESAFE_TIMEOUT": "2.5"}):
            cfg = JudgmentConfig.from_env()
        assert (cfg.base_url, cfg.model, cfg.timeout) == ("https://jev.internal", "jev-1.13.0", 2.5)

    def test_judgment_vars_win_over_aliases(self, clean_env):
        with patch.dict(os.environ, {"JUDGMENT_API_KEY": "new", "TYPESAFE_API_KEY": "old",
                                     "JUDGMENT_MODEL": "jev-preview", "TYPESAFE_DEFAULT_MODEL": "jev-1.13.0"}):
            cfg = JudgmentConfig.from_env()
        assert (cfg.api_key, cfg.model) == ("new", "jev-preview")

    def test_self_hosted_systemone_without_key(self, clean_env):
        with patch.dict(os.environ, {"JUDGMENT_BACKEND": "systemone", "JUDGMENT_BASE_URL": "http://laya:8080/",
                                     "JUDGMENT_MODEL": "laya"}):
            cfg = JudgmentConfig.from_env()
            assert judgment.is_configured() is True
        assert (cfg.backend, cfg.base_url, cfg.model, cfg.api_key) == ("systemone", "http://laya:8080", "laya", None)

    def test_base_url_alone_configures_systemone(self, clean_env):
        with patch.dict(os.environ, {"JUDGMENT_BASE_URL": "http://laya:8080"}):
            cfg = JudgmentConfig.from_env()
        assert cfg.backend == "systemone" and cfg.model == "jev-latest"

    def test_openai_defaults(self, clean_env):
        with patch.dict(os.environ, {"JUDGMENT_BACKEND": "OpenAI", "JUDGMENT_MODEL": "qwen3:8b"}):
            cfg = JudgmentConfig.from_env()
        assert cfg == JudgmentConfig(backend="openai", base_url="http://localhost:11434/v1", model="qwen3:8b",
                                     api_key=None, timeout=120.0, samples=1, time_budget=300.0)

    def test_openai_requires_model(self, clean_env):
        with patch.dict(os.environ, {"JUDGMENT_BACKEND": "openai"}):
            with pytest.raises(ConfigError, match="JUDGMENT_MODEL"):
                JudgmentConfig.from_env()
            # Broken config still counts as configured so the error surfaces at call time.
            assert judgment.is_configured() is True

    def test_invalid_backend(self, clean_env):
        with patch.dict(os.environ, {"JUDGMENT_BACKEND": "llama"}):
            with pytest.raises(ConfigError, match="JUDGMENT_BACKEND"):
                JudgmentConfig.from_env()

    @pytest.mark.parametrize("bad", ["abc", "0", "-3"])
    def test_bad_timeout(self, clean_env, bad):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "k", "JUDGMENT_TIMEOUT": bad}):
            with pytest.raises(ConfigError, match="JUDGMENT_TIMEOUT"):
                JudgmentConfig.from_env()

    def test_samples(self, clean_env):
        base = {"JUDGMENT_BACKEND": "openai", "JUDGMENT_MODEL": "m"}
        with patch.dict(os.environ, {**base, "JUDGMENT_SAMPLES": "3"}):
            assert JudgmentConfig.from_env().samples == 3
        for bad in ("0", "11", "x"):
            with patch.dict(os.environ, {**base, "JUDGMENT_SAMPLES": bad}):
                with pytest.raises(ConfigError, match="JUDGMENT_SAMPLES"):
                    JudgmentConfig.from_env()
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "k", "JUDGMENT_SAMPLES": "3"}):
            assert JudgmentConfig.from_env().samples == 1  # ignored for systemone

    def test_time_budget(self, clean_env):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "k", "JUDGMENT_TIME_BUDGET": "45"}):
            assert JudgmentConfig.from_env().time_budget == 45.0
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "k", "JUDGMENT_TIME_BUDGET": "-1"}):
            with pytest.raises(ConfigError, match="JUDGMENT_TIME_BUDGET"):
                JudgmentConfig.from_env()

    def test_key_with_whitespace_is_config_error(self, clean_env):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "bad key"}):
            with pytest.raises(ConfigError, match="JUDGMENT_API_KEY"):
                JudgmentConfig.from_env()

    def test_repr_hides_key(self, clean_env):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "ts-key-123"}):
            text = repr(JudgmentConfig.from_env())
        assert "ts-key-123" not in text and "api_key=set" in text


class TestGetBackend:
    def test_not_configured_raises(self, clean_env):
        with pytest.raises(JudgmentNotConfiguredError) as exc:
            get_backend()
        assert "TYPESAFE_API_KEY" in str(exc.value) and "JUDGMENT_BACKEND=openai" in str(exc.value)

    def test_selects_systemone(self, clean_env):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "k"}):
            backend = get_backend()
        assert isinstance(backend, SystemOneClient)
        assert (backend.name, backend.calibrated, backend.confidence_source) == ("systemone", True, "model")

    def test_selects_openai(self, clean_env):
        with patch.dict(os.environ, {"JUDGMENT_BACKEND": "openai", "JUDGMENT_MODEL": "m"}):
            backend = get_backend()
        assert isinstance(backend, ChatJudgeClient)
        assert (backend.name, backend.calibrated, backend.confidence_source) == ("openai", False, "self_reported")
        with patch.dict(os.environ, {"JUDGMENT_BACKEND": "openai", "JUDGMENT_MODEL": "m", "JUDGMENT_SAMPLES": "3"}):
            assert get_backend().confidence_source == "vote_frequency"

    def test_explicit_config_object(self, clean_env):
        cfg = JudgmentConfig(backend="openai", base_url="http://x", model="m", api_key=None, timeout=1.0)
        assert isinstance(get_backend(cfg), ChatJudgeClient)


class TestPostJson:
    @responses.activate
    def test_posts_json_and_returns_response(self):
        responses.add(responses.POST, URL, json={"ok": True})
        response = post_json(URL, headers=HEADERS, body=BODY, timeout=5, sleep=lambda _s: None)
        assert response.status_code == 200 and response.json() == {"ok": True}
        request = responses.calls[0].request
        assert json.loads(request.body) == BODY
        assert request.headers["Content-Type"] == "application/json"

    @responses.activate
    def test_retries_429_honouring_retry_after_ms(self):
        responses.add(responses.POST, URL, status=429, headers={"retry-after-ms": "10"})
        responses.add(responses.POST, URL, json={"ok": True})
        sleeps: list[float] = []
        assert post_json(URL, headers=HEADERS, body=BODY, timeout=5, sleep=sleeps.append).status_code == 200
        assert len(responses.calls) == 2 and sleeps == [0.01]

    @responses.activate
    def test_retries_429_honouring_retry_after_seconds(self):
        responses.add(responses.POST, URL, status=429, headers={"Retry-After": "2"})
        responses.add(responses.POST, URL, json={})
        sleeps: list[float] = []
        post_json(URL, headers=HEADERS, body=BODY, timeout=5, sleep=sleeps.append)
        assert sleeps == [2.0]

    @responses.activate
    def test_retries_5xx_with_exponential_backoff(self):
        responses.add(responses.POST, URL, status=529)
        responses.add(responses.POST, URL, status=529)
        responses.add(responses.POST, URL, json={})
        sleeps: list[float] = []
        assert post_json(URL, headers=HEADERS, body=BODY, timeout=5, sleep=sleeps.append).status_code == 200
        assert len(responses.calls) == 3
        assert 0.375 <= sleeps[0] <= 0.5 and 0.75 <= sleeps[1] <= 1.0

    @responses.activate
    def test_returns_final_error_after_max_retries(self):
        for _ in range(3):
            responses.add(responses.POST, URL, status=500)
        response = post_json(URL, headers=HEADERS, body=BODY, timeout=5, sleep=lambda _s: None)
        assert response.status_code == 500 and len(responses.calls) == 3

    @responses.activate
    def test_4xx_not_retried(self):
        responses.add(responses.POST, URL, status=401)
        assert post_json(URL, headers=HEADERS, body=BODY, timeout=5, sleep=lambda _s: None).status_code == 401
        assert len(responses.calls) == 1

    @responses.activate
    def test_all_transport_errors_are_retried(self):
        # ChunkedEncodingError is a RequestException but not a ConnectionError/Timeout.
        responses.add(responses.POST, URL, body=requests.exceptions.ChunkedEncodingError("cut"))
        responses.add(responses.POST, URL, body=requests.ConnectionError("down"))
        responses.add(responses.POST, URL, json={})
        sleeps: list[float] = []
        assert post_json(URL, headers=HEADERS, body=BODY, timeout=5, sleep=sleeps.append).status_code == 200
        assert len(responses.calls) == 3 and len(sleeps) == 2

    @responses.activate
    def test_transport_error_gives_up(self):
        for _ in range(3):
            responses.add(responses.POST, URL, body=requests.exceptions.ContentDecodingError("bad gzip"))
        with pytest.raises(JudgmentError, match="bad gzip"):
            post_json(URL, headers=HEADERS, body=BODY, timeout=5, sleep=lambda _s: None)

    def test_malformed_url_is_not_retried(self):
        sleeps: list[float] = []
        with pytest.raises(JudgmentError):
            post_json("not-a-url/v1/systemone", headers=HEADERS, body=BODY, timeout=5, sleep=sleeps.append)
        assert sleeps == []

    @responses.activate
    def test_uses_given_session(self):
        responses.add(responses.POST, URL, json={})
        session = requests.Session()
        with patch.object(session, "post", wraps=session.post) as post:
            post_json(URL, headers=HEADERS, body=BODY, timeout=7, session=session)
        assert post.call_args.kwargs["timeout"] == 7


class TestHelpers:
    @pytest.mark.parametrize("value,band", [
        (0.99, "high"), (0.9, "high"), (0.89, "medium"), (0.5, "medium"),
        (0.49, "low"), (0.0, "low"), (None, "low"),
    ])
    def test_confidence_band(self, value, band):
        assert confidence_band(value) == band

    def test_concentration_confidence(self):
        assert concentration_confidence({"a": 1.0, "b": 0.0, "c": 0.0}) == 1.0
        assert concentration_confidence({"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}) == 0.0
        assert concentration_confidence({"a": 0.9, "b": 0.06, "c": 0.04}) == 0.85
        assert concentration_confidence({"a": 0.5, "b": 0.5}) == 0.0
        assert concentration_confidence({"a": 1.0}) == 1.0
        assert concentration_confidence({}) == 1.0

    def test_add_usage_accumulates_and_ignores_junk(self):
        total: dict[str, int] = {}
        add_usage(total, {"input_tokens": 5, "output_tokens": 1})
        add_usage(total, {"input_tokens": 7, "output_tokens": "x"})
        add_usage(total, None)
        add_usage(total, "garbage")
        assert total == {"input_tokens": 12, "output_tokens": 1}

    def test_parse_retry_after(self):
        parse = judgment._parse_retry_after
        assert parse({"retry-after-ms": "250"}) == 0.25
        assert parse({"Retry-After": "3"}) == 3.0
        assert parse({"retry-after-ms": "250", "Retry-After": "3"}) == 0.25
        assert parse({"Retry-After": "9999"}) == judgment.RETRY_AFTER_CAP
        assert parse({"Retry-After": "soon"}) is None
        assert parse({}) is None

    def test_error_detail_shapes(self):
        def resp(payload):
            r = requests.Response()
            r._content = json.dumps(payload).encode()
            r.status_code = 400
            return r
        assert judgment.error_detail(resp({"detail": "plain"})) == "plain"
        assert judgment.error_detail(resp({"error": {"message": "nested"}})) == "nested"
        assert judgment.error_detail(resp({"detail": [{"loc": ["body", "q"], "msg": "required"}]})) == "body.q: required"
        assert judgment.error_detail(resp([1, 2])) is None
