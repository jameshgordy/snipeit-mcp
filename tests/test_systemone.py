"""Tests for the System One protocol backend (TypeSafe Jev and compatible servers):
exact wire format and error mapping. Only HTTP is mocked."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
import responses

from snipeit_mcp.judgment import JUDGMENT_ENV_VARS, JudgmentConfig, JudgmentError, get_backend
from snipeit_mcp.systemone import SystemOneClient

URL = "https://api.typesafe.ai/v1/systemone"
QUESTIONS = {"q": {"type": "noul", "instructions": "Is it?"}}
OK_BODY = {
    "model": "jev-1.13.0",
    "answers": {"q": {"type": "noul", "noul": 0.9}},
    "usage": {"input_tokens": 10, "output_tokens": 1},
}


@pytest.fixture
def jev_env():
    with patch.dict(os.environ, {}):
        for var in JUDGMENT_ENV_VARS:
            os.environ.pop(var, None)
        os.environ["TYPESAFE_API_KEY"] = "ts-key-123"
        yield


def client(**env) -> SystemOneClient:
    with patch.dict(os.environ, env):
        backend = get_backend(sleep=lambda _s: None)
    assert isinstance(backend, SystemOneClient)
    return backend


class TestSystemOneClient:
    @responses.activate
    def test_posts_exact_request(self, jev_env):
        responses.add(responses.POST, URL, json=OK_BODY, headers={"x-typesafe-request-id": "req-1"})

        data = client().evaluate({"text": "hi"}, QUESTIONS)

        assert data == OK_BODY
        request = responses.calls[0].request
        assert request.url == URL
        assert json.loads(request.body) == {"state": {"text": "hi"}, "model": "jev-latest", "questions": QUESTIONS}
        assert request.headers["Authorization"] == "Bearer ts-key-123"
        assert request.headers["Content-Type"] == "application/json"
        assert request.headers["Accept"] == "application/json"
        assert request.headers["User-Agent"].startswith("snipeit-mcp/")

    @responses.activate
    def test_self_hosted_server_without_key(self, jev_env):
        os.environ.pop("TYPESAFE_API_KEY")
        responses.add(responses.POST, "http://laya:8080/v1/systemone", json=OK_BODY)
        c = client(JUDGMENT_BACKEND="systemone", JUDGMENT_BASE_URL="http://laya:8080/", JUDGMENT_MODEL="laya")
        c.evaluate("s", QUESTIONS)
        request = responses.calls[0].request
        assert request.url == "http://laya:8080/v1/systemone"
        assert "Authorization" not in request.headers
        assert json.loads(request.body)["model"] == "laya"

    @responses.activate
    def test_model_override_and_env_model(self, jev_env):
        responses.add(responses.POST, URL, json=OK_BODY)
        responses.add(responses.POST, URL, json=OK_BODY)
        c = client(TYPESAFE_DEFAULT_MODEL="jev-1.13.0")
        c.evaluate("s", QUESTIONS)
        c.evaluate("s", QUESTIONS, model="jev-preview")
        assert json.loads(responses.calls[0].request.body)["model"] == "jev-1.13.0"
        assert json.loads(responses.calls[1].request.body)["model"] == "jev-preview"

    @responses.activate
    def test_timeout_is_passed_and_session_reused(self, jev_env):
        responses.add(responses.POST, URL, json=OK_BODY)
        responses.add(responses.POST, URL, json=OK_BODY)
        c = client(TYPESAFE_TIMEOUT="3")
        with patch.object(c._session, "post", wraps=c._session.post) as post:
            c.evaluate("s", QUESTIONS)
            c.evaluate("s", QUESTIONS)
        assert post.call_count == 2
        assert all(call.kwargs["timeout"] == 3.0 for call in post.call_args_list)

    @responses.activate
    def test_401_mentions_key(self, jev_env):
        responses.add(responses.POST, URL, status=401, json={"detail": "Invalid API key"})
        with pytest.raises(JudgmentError) as exc:
            client().evaluate("s", QUESTIONS)
        assert exc.value.status == 401
        assert "TYPESAFE_API_KEY" in str(exc.value) and "Invalid API key" in str(exc.value)
        assert len(responses.calls) == 1

    @responses.activate
    def test_404_mentions_base_url(self, jev_env):
        responses.add(responses.POST, URL, status=404)
        with pytest.raises(JudgmentError, match="JUDGMENT_BASE_URL"):
            client().evaluate("s", QUESTIONS)

    @responses.activate
    def test_422_detail_is_readable(self, jev_env):
        responses.add(responses.POST, URL, status=422, headers={"x-typesafe-request-id": "req-422"},
                      json={"detail": [{"loc": ["body", "questions", "q", "criteria"],
                                        "msg": "Field required", "type": "missing"}]})
        with pytest.raises(JudgmentError) as exc:
            client().evaluate("s", QUESTIONS)
        assert exc.value.status == 422 and exc.value.request_id == "req-422"
        assert "body.questions.q.criteria: Field required" in str(exc.value)

    @responses.activate
    def test_429_exhausted_is_an_error(self, jev_env):
        for _ in range(3):
            responses.add(responses.POST, URL, status=429, headers={"retry-after-ms": "1"})
        with pytest.raises(JudgmentError, match="rate limit") as exc:
            client().evaluate("s", QUESTIONS)
        assert exc.value.status == 429 and len(responses.calls) == 3

    @responses.activate
    def test_malformed_and_non_json_bodies(self, jev_env):
        responses.add(responses.POST, URL, json={"foo": 1})
        responses.add(responses.POST, URL, body="nope")
        c = client()
        with pytest.raises(JudgmentError, match="malformed"):
            c.evaluate("s", QUESTIONS)
        with pytest.raises(JudgmentError, match="non-JSON"):
            c.evaluate("s", QUESTIONS)

    def test_empty_questions_rejected(self, jev_env):
        with pytest.raises(JudgmentError):
            client().evaluate("s", {})

    def test_direct_construction(self):
        cfg = JudgmentConfig(backend="systemone", base_url="http://h", model="m", api_key=None, timeout=1.0)
        c = SystemOneClient(cfg)
        assert c._url == "http://h/v1/systemone" and "Authorization" not in c._headers()
