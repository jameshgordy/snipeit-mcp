"""Tests for the OpenAI-compatible chat backend (Ollama and friends): schema and
prompt construction, reply parsing/validation/conversion, and the exact wire
format. Only HTTP is mocked."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
import responses

from snipeit_mcp.chat_judge import (
    SAMPLING_TEMPERATURE,
    SYSTEM_PROMPT,
    ChatJudgeClient,
    build_messages,
    build_schema,
    convert,
    parse_reply,
    render_questions,
    validate_reply,
)
from snipeit_mcp.judgment import JUDGMENT_ENV_VARS, JudgmentConfig, JudgmentError, get_backend

CHAT_URL = "http://localhost:11434/v1/chat/completions"
QUESTIONS = {
    "same_entity": {"type": "score", "instructions": "Same?", "criteria": ["different", "possibly", "same"]},
    "name_variant": {"type": "noul", "instructions": "Variants?", "criteria": {"true": "yes", "false": "no"}},
    "match": {"type": "choice", "instructions": "Which?",
              "criteria": {"12": {"name": "A"}, "13": {"name": "B"}, "none": "None of them"}},
}
GOOD_REPLY = {
    "same_entity": {"level": 2, "confidence": 0.9},
    "name_variant": {"answer": True, "confidence": 0.95},
    "match": {"choice": "12", "confidence": 0.8},
}
CONF = {"type": "number", "minimum": 0, "maximum": 1}
EXPECTED_SCHEMA = {
    "type": "object",
    "properties": {
        "same_entity": {"type": "object",
                        "properties": {"level": {"type": "integer", "minimum": 0, "maximum": 2}, "confidence": CONF},
                        "required": ["level", "confidence"], "additionalProperties": False},
        "name_variant": {"type": "object",
                         "properties": {"answer": {"type": "boolean"}, "confidence": CONF},
                         "required": ["answer", "confidence"], "additionalProperties": False},
        "match": {"type": "object",
                  "properties": {"choice": {"type": "string", "enum": ["12", "13", "none"]}, "confidence": CONF},
                  "required": ["choice", "confidence"], "additionalProperties": False},
    },
    "required": ["same_entity", "name_variant", "match"],
    "additionalProperties": False,
}


def chat_response(content, usage=(50, 20)) -> dict:
    if not isinstance(content, str):
        content = json.dumps(content)
    return {
        "id": "chatcmpl-1", "object": "chat.completion", "model": "qwen3:8b",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": usage[0], "completion_tokens": usage[1], "total_tokens": sum(usage)},
    }


@pytest.fixture
def ollama_env():
    with patch.dict(os.environ, {}):
        for var in JUDGMENT_ENV_VARS:
            os.environ.pop(var, None)
        os.environ["JUDGMENT_BACKEND"] = "openai"
        os.environ["JUDGMENT_MODEL"] = "qwen3:8b"
        yield


def client(**env) -> ChatJudgeClient:
    with patch.dict(os.environ, env):
        backend = get_backend(sleep=lambda _s: None)
    assert isinstance(backend, ChatJudgeClient)
    return backend


class TestSchemaAndPrompt:
    def test_schema(self):
        assert build_schema(QUESTIONS) == EXPECTED_SCHEMA

    def test_schema_rejects_bad_questions(self):
        with pytest.raises(JudgmentError, match="Unsupported"):
            build_schema({"q": {"type": "rank", "criteria": []}})
        with pytest.raises(JudgmentError, match="no options"):
            build_schema({"q": {"type": "choice", "criteria": {}}})
        with pytest.raises(JudgmentError, match="no levels"):
            build_schema({"q": {"type": "score", "criteria": []}})

    def test_render_questions(self):
        assert render_questions(QUESTIONS) == {
            "same_entity": {"type": "score", "instructions": "Same?",
                            "levels": {"0": "different", "1": "possibly", "2": "same"}},
            "name_variant": {"type": "noul", "instructions": "Variants?",
                             "answer_true_when": "yes", "answer_false_when": "no"},
            "match": {"type": "choice", "instructions": "Which?",
                      "options": {"12": {"name": "A"}, "13": {"name": "B"}, "none": "None of them"}},
        }

    def test_build_messages(self):
        state = {"record_a": {"name": "Apple"}, "record_b": {"name": "Apple Inc."}}
        messages = build_messages(state, QUESTIONS, EXPECTED_SCHEMA)
        assert [m["role"] for m in messages] == ["system", "user"]
        assert messages[0]["content"] == SYSTEM_PROMPT
        user = messages[1]["content"]
        assert user.startswith("STATE:\n" + json.dumps(state, ensure_ascii=False, indent=2))
        assert "\n\nQUESTIONS:\n" in user and "\n\nRESPONSE_SCHEMA:\n" + json.dumps(EXPECTED_SCHEMA) in user
        assert '"levels"' in user and '"answer_true_when"' in user


class TestParseAndValidate:
    def test_parse_tolerates_fences_and_prose(self):
        assert parse_reply('{"a": 1}') == {"a": 1}
        assert parse_reply('```json\n{"a": 1}\n```') == {"a": 1}
        assert parse_reply('Sure! Here it is: {"a": {"b": 2}} hope that helps') == {"a": {"b": 2}}
        with pytest.raises(JudgmentError, match="not valid JSON"):
            parse_reply("no json here")

    def test_validate_ok_and_clamps_confidence(self):
        reply = {**GOOD_REPLY, "match": {"choice": "13", "confidence": 1.7},
                 "name_variant": {"answer": False, "confidence": -0.2}}
        items = validate_reply(reply, QUESTIONS)
        assert items["same_entity"] == {"level": 2, "confidence": 0.9}
        assert items["name_variant"] == {"answer": False, "confidence": 0.0}
        assert items["match"] == {"choice": "13", "confidence": 1.0}

    @pytest.mark.parametrize("reply,message", [
        ([], "not a JSON object"),
        ({k: v for k, v in GOOD_REPLY.items() if k != "match"}, "missing question 'match'"),
        ({**GOOD_REPLY, "match": {"choice": "99", "confidence": 0.9}}, "not one of the options"),
        ({**GOOD_REPLY, "same_entity": {"level": 3, "confidence": 0.9}}, "out-of-range level"),
        ({**GOOD_REPLY, "same_entity": {"level": True, "confidence": 0.9}}, "out-of-range level"),
        ({**GOOD_REPLY, "name_variant": {"answer": "yes", "confidence": 0.9}}, "non-boolean"),
        ({**GOOD_REPLY, "name_variant": {"answer": True, "confidence": "high"}}, "non-numeric confidence"),
    ])
    def test_validate_rejects(self, reply, message):
        with pytest.raises(JudgmentError, match=message):
            validate_reply(reply, QUESTIONS)


class TestConvert:
    def test_single_sample(self):
        answers = convert(QUESTIONS, [validate_reply(GOOD_REPLY, QUESTIONS)])
        assert answers["same_entity"] == {
            "type": "score", "score": 2.0, "confidence": 0.9,
            "legend": {"0": "different", "1": "possibly", "2": "same"},
            "probabilities": {"0": 0.05, "1": 0.05, "2": 0.9},
        }
        assert answers["name_variant"] == {"type": "noul", "noul": 0.95}
        assert answers["match"] == {"type": "choice", "choice": "12", "confidence": 0.8,
                                    "probabilities": {"12": 0.8, "13": 0.1, "none": 0.1}}

    def test_single_sample_false_noul_and_single_option(self):
        questions = {"q": {"type": "noul"}, "c": {"type": "choice", "criteria": {"only": None}}}
        answers = convert(questions, [{"q": {"answer": False, "confidence": 0.8}, "c": {"choice": "only", "confidence": 0.3}}])
        assert answers["q"]["noul"] == pytest.approx(0.2)
        assert answers["c"]["probabilities"] == {"only": 1.0}

    def test_multi_sample_votes(self):
        replies = [
            {"same_entity": {"level": 2, "confidence": 1}, "name_variant": {"answer": True, "confidence": 1},
             "match": {"choice": "12", "confidence": 1}},
            {"same_entity": {"level": 2, "confidence": 1}, "name_variant": {"answer": True, "confidence": 1},
             "match": {"choice": "12", "confidence": 1}},
            {"same_entity": {"level": 1, "confidence": 1}, "name_variant": {"answer": False, "confidence": 1},
             "match": {"choice": "13", "confidence": 1}},
        ]
        answers = convert(QUESTIONS, replies)
        assert answers["same_entity"]["probabilities"] == {"0": 0.0, "1": 0.3333, "2": 0.6667}
        assert answers["same_entity"]["score"] == pytest.approx(1.6667, abs=1e-4)
        assert answers["same_entity"]["confidence"] == pytest.approx(0.5, abs=1e-3)  # (3*0.6667-1)/2
        assert answers["name_variant"]["noul"] == pytest.approx(0.6667, abs=1e-4)
        assert answers["match"]["choice"] == "12"
        assert answers["match"]["probabilities"] == {"12": 0.6667, "13": 0.3333, "none": 0.0}

    def test_multi_sample_tie_goes_to_first_option(self):
        questions = {"c": {"type": "choice", "criteria": {"a": None, "b": None}}}
        answers = convert(questions, [{"c": {"choice": "b", "confidence": 1}}, {"c": {"choice": "a", "confidence": 1}}])
        assert answers["c"]["choice"] == "a" and answers["c"]["confidence"] == 0.0


class TestClient:
    @responses.activate
    def test_posts_exact_request(self, ollama_env):
        responses.add(responses.POST, CHAT_URL, json=chat_response(GOOD_REPLY))
        state = {"record_a": {"name": "Apple"}, "record_b": {"name": "Apple Inc."}}

        data = client().evaluate(state, QUESTIONS)

        request = responses.calls[0].request
        assert request.url == CHAT_URL
        assert "Authorization" not in request.headers
        assert request.headers["Content-Type"] == "application/json"
        assert request.headers["User-Agent"].startswith("snipeit-mcp/")
        assert json.loads(request.body) == {
            "model": "qwen3:8b",
            "messages": build_messages(state, QUESTIONS, EXPECTED_SCHEMA),
            "temperature": 0,
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "judgment", "strict": True, "schema": EXPECTED_SCHEMA}},
        }
        assert data == {
            "model": "qwen3:8b",
            "answers": convert(QUESTIONS, [validate_reply(GOOD_REPLY, QUESTIONS)]),
            "usage": {"input_tokens": 50, "output_tokens": 20},
        }

    @responses.activate
    def test_hosted_service_with_key(self, ollama_env):
        responses.add(responses.POST, "https://api.openai.com/v1/chat/completions", json=chat_response(GOOD_REPLY))
        c = client(JUDGMENT_BASE_URL="https://api.openai.com/v1/", JUDGMENT_API_KEY="sk-test", JUDGMENT_MODEL="gpt-x")
        c.evaluate("s", QUESTIONS)
        request = responses.calls[0].request
        assert request.headers["Authorization"] == "Bearer sk-test"
        assert json.loads(request.body)["model"] == "gpt-x"

    @responses.activate
    def test_samples_vote_across_requests(self, ollama_env):
        for level, choice in ((2, "12"), (2, "12"), (1, "13")):
            responses.add(responses.POST, CHAT_URL, json=chat_response({
                "same_entity": {"level": level, "confidence": 0.9},
                "name_variant": {"answer": True, "confidence": 0.9},
                "match": {"choice": choice, "confidence": 0.9},
            }))
        data = client(JUDGMENT_SAMPLES="3").evaluate("s", QUESTIONS)
        assert len(responses.calls) == 3
        assert all(json.loads(c.request.body)["temperature"] == SAMPLING_TEMPERATURE for c in responses.calls)
        assert data["usage"] == {"input_tokens": 150, "output_tokens": 60}
        assert data["answers"]["match"]["probabilities"] == {"12": 0.6667, "13": 0.3333, "none": 0.0}
        assert data["answers"]["same_entity"]["score"] == pytest.approx(1.6667, abs=1e-4)

    @responses.activate
    def test_fenced_reply_is_accepted(self, ollama_env):
        responses.add(responses.POST, CHAT_URL, json=chat_response("```json\n" + json.dumps(GOOD_REPLY) + "\n```"))
        assert client().evaluate("s", QUESTIONS)["answers"]["match"]["choice"] == "12"

    @responses.activate
    def test_invalid_option_from_model_is_error(self, ollama_env):
        responses.add(responses.POST, CHAT_URL, json=chat_response({**GOOD_REPLY, "match": {"choice": "99", "confidence": 1}}))
        with pytest.raises(JudgmentError, match="not one of the options") as exc:
            client().evaluate("s", QUESTIONS)
        assert exc.value.status == 200

    @responses.activate
    def test_404_hints_at_model_and_base_url(self, ollama_env):
        responses.add(responses.POST, CHAT_URL, status=404, json={"error": {"message": "model 'qwen3:8b' not found"}})
        with pytest.raises(JudgmentError) as exc:
            client().evaluate("s", QUESTIONS)
        assert "JUDGMENT_BASE_URL" in str(exc.value) and "model 'qwen3:8b' not found" in str(exc.value)
        assert len(responses.calls) == 1

    @responses.activate
    def test_400_hints_at_structured_outputs(self, ollama_env):
        responses.add(responses.POST, CHAT_URL, status=400, json={"error": {"message": "response_format unsupported"}})
        with pytest.raises(JudgmentError, match="structured outputs"):
            client().evaluate("s", QUESTIONS)

    @responses.activate
    def test_401_mentions_key(self, ollama_env):
        responses.add(responses.POST, CHAT_URL, status=401)
        with pytest.raises(JudgmentError, match="JUDGMENT_API_KEY"):
            client().evaluate("s", QUESTIONS)

    @responses.activate
    def test_malformed_responses(self, ollama_env):
        responses.add(responses.POST, CHAT_URL, json={"choices": []})
        responses.add(responses.POST, CHAT_URL, json={"choices": [{"message": {"content": None}}]})
        responses.add(responses.POST, CHAT_URL, body="nope")
        c = client()
        with pytest.raises(JudgmentError, match="malformed"):
            c.evaluate("s", QUESTIONS)
        with pytest.raises(JudgmentError, match="non-text"):
            c.evaluate("s", QUESTIONS)
        with pytest.raises(JudgmentError, match="non-JSON"):
            c.evaluate("s", QUESTIONS)

    def test_empty_questions_rejected(self, ollama_env):
        with pytest.raises(JudgmentError):
            client().evaluate("s", {})

    def test_direct_construction(self):
        cfg = JudgmentConfig(backend="openai", base_url="http://h/v1", model="m", api_key=None, timeout=1.0, samples=2)
        c = ChatJudgeClient(cfg)
        assert c._url == "http://h/v1/chat/completions" and c.confidence_source == "vote_frequency"
