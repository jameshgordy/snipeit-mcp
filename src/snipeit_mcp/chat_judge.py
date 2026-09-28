"""OpenAI-compatible chat backend: Ollama, vLLM, LM Studio, llama.cpp, OpenRouter, OpenAI.

Turns the same typed questions the System One backend answers natively into a
single ``POST {base}/chat/completions`` request with a JSON-schema structured
output (``response_format`` of type ``json_schema``; the server must support
it — Ollama ≥ 0.5, vLLM, LM Studio, OpenAI do). The reply is validated
against the question definitions and converted into the System One answer
shapes so the tools do not care which backend answered.

What a chat model cannot give us is a *calibrated* probability. With
``JUDGMENT_SAMPLES=1`` (default, ``temperature`` 0) the model's self-reported
confidence is used and the remaining mass is spread evenly over the other
options. With ``JUDGMENT_SAMPLES>1`` the question is asked that many times at
a sampling temperature and vote frequency becomes the probability, with the
confidence derived from how concentrated the votes are. Either way the tools
report ``calibrated: false`` and ``confidence_source`` so callers can weigh
the accept/review thresholds accordingly.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

import requests

from . import judgment
from .judgment import JudgmentConfig, JudgmentError

CHAT_PATH = "/chat/completions"
REQUEST_ID_HEADER = "x-request-id"
SAMPLING_TEMPERATURE = 0.8
SCHEMA_NAME = "judgment"

SYSTEM_PROMPT = (
    "You are a judgment engine, not a chat assistant. You receive STATE (JSON) and "
    "QUESTIONS (JSON). Answer every question independently, using only the state. "
    "For each question return its answer and a confidence between 0 and 1, where 1 "
    "means certain. Reply with exactly one JSON object that matches RESPONSE_SCHEMA. "
    "No prose, no markdown, no keys other than those in the schema."
)

_CONFIDENCE_SCHEMA = {"type": "number", "minimum": 0, "maximum": 1}


# ---------------------------------------------------------------------------
# Prompt and schema construction (pure; unit-tested)
# ---------------------------------------------------------------------------


def build_schema(questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """JSON schema for the reply: one object per question with answer + confidence."""
    properties: dict[str, Any] = {}
    for name, question in questions.items():
        qtype = question.get("type")
        if qtype == "noul":
            answer: dict[str, Any] = {"answer": {"type": "boolean"}}
        elif qtype == "choice":
            keys = list(question["criteria"].keys())
            if not keys:
                raise JudgmentError(f"Choice question {name!r} has no options")
            answer = {"choice": {"type": "string", "enum": keys}}
        elif qtype == "score":
            levels = len(question["criteria"])
            if levels < 1:
                raise JudgmentError(f"Score question {name!r} has no levels")
            answer = {"level": {"type": "integer", "minimum": 0, "maximum": levels - 1}}
        else:
            raise JudgmentError(f"Unsupported question type {qtype!r} for {name!r}")
        properties[name] = {
            "type": "object",
            "properties": {**answer, "confidence": _CONFIDENCE_SCHEMA},
            "required": [*answer.keys(), "confidence"],
            "additionalProperties": False,
        }
    return {
        "type": "object",
        "properties": properties,
        "required": list(questions.keys()),
        "additionalProperties": False,
    }


def render_questions(questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """The questions as the model sees them: instructions plus labelled options/levels."""
    rendered: dict[str, Any] = {}
    for name, question in questions.items():
        entry: dict[str, Any] = {"type": question.get("type"), "instructions": question.get("instructions")}
        criteria = question.get("criteria")
        if question.get("type") == "noul" and isinstance(criteria, dict):
            entry["answer_true_when"] = criteria.get("true")
            entry["answer_false_when"] = criteria.get("false")
        elif question.get("type") == "choice":
            entry["options"] = criteria
        elif question.get("type") == "score":
            entry["levels"] = {str(i): level for i, level in enumerate(criteria or [])}
        rendered[name] = entry
    return rendered


def build_messages(state: Any, questions: dict[str, dict[str, Any]],
                   schema: dict[str, Any]) -> list[dict[str, str]]:
    user = (
        "STATE:\n" + json.dumps(state, ensure_ascii=False, indent=2)
        + "\n\nQUESTIONS:\n" + json.dumps(render_questions(questions), ensure_ascii=False, indent=2)
        + "\n\nRESPONSE_SCHEMA:\n" + json.dumps(schema, ensure_ascii=False)
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


# ---------------------------------------------------------------------------
# Reply parsing, validation, conversion (pure; unit-tested)
# ---------------------------------------------------------------------------

_LEADING_FENCE = re.compile(r"^```[A-Za-z]*\s*")
_TRAILING_FENCE = re.compile(r"\s*```$")


def parse_reply(content: str) -> Any:
    """Parse the model's JSON, tolerating code fences and surrounding prose."""
    text = _TRAILING_FENCE.sub("", _LEADING_FENCE.sub("", content.strip()))
    try:
        return json.loads(text)
    except ValueError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except ValueError:
                pass
    raise JudgmentError("Chat model reply is not valid JSON")


def _confidence(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise JudgmentError(f"Chat model reply has a non-numeric confidence for {name!r}")
    return max(0.0, min(1.0, float(value)))


def validate_reply(reply: Any, questions: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Check the parsed reply against the questions; return normalised per-question items."""
    if not isinstance(reply, dict):
        raise JudgmentError("Chat model reply is not a JSON object")
    items: dict[str, dict[str, Any]] = {}
    for name, question in questions.items():
        item = reply.get(name)
        if not isinstance(item, dict):
            raise JudgmentError(f"Chat model reply is missing question {name!r}")
        confidence = _confidence(item.get("confidence"), name)
        qtype = question.get("type")
        if qtype == "noul":
            answer = item.get("answer")
            if not isinstance(answer, bool):
                raise JudgmentError(f"Chat model reply has a non-boolean answer for {name!r}")
            items[name] = {"answer": answer, "confidence": confidence}
        elif qtype == "choice":
            choice = item.get("choice")
            if choice not in question["criteria"]:
                raise JudgmentError(f"Chat model chose {choice!r}, not one of the options for {name!r}")
            items[name] = {"choice": choice, "confidence": confidence}
        else:  # score
            level = item.get("level")
            levels = len(question["criteria"])
            if isinstance(level, bool) or not isinstance(level, int) or not 0 <= level < levels:
                raise JudgmentError(f"Chat model gave an out-of-range level {level!r} for {name!r}")
            items[name] = {"level": level, "confidence": confidence}
    return items


def _spread(chosen: str, keys: list[str], confidence: float) -> dict[str, float]:
    """Put ``confidence`` on the chosen key and spread the rest evenly."""
    others = [k for k in keys if k != chosen]
    rest = (1.0 - confidence) / len(others) if others else 0.0
    probabilities = {k: round(rest, 4) for k in keys}
    probabilities[chosen] = round(confidence, 4) if others else 1.0
    return probabilities


def _frequencies(votes: list[str], keys: list[str]) -> dict[str, float]:
    return {k: round(votes.count(k) / len(votes), 4) for k in keys}


def convert(questions: dict[str, dict[str, Any]],
            replies: list[dict[str, dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    """Turn one or more validated replies into System One answer shapes."""
    single = len(replies) == 1
    answers: dict[str, dict[str, Any]] = {}
    for name, question in questions.items():
        items = [reply[name] for reply in replies]
        qtype = question.get("type")
        if qtype == "noul":
            if single:
                p = items[0]["confidence"]
                noul = p if items[0]["answer"] else 1.0 - p
            else:
                noul = sum(1 for i in items if i["answer"]) / len(items)
            answers[name] = {"type": "noul", "noul": round(noul, 4)}
        elif qtype == "choice":
            keys = list(question["criteria"].keys())
            if single:
                choice, confidence = items[0]["choice"], items[0]["confidence"]
                probabilities = _spread(choice, keys, confidence)
            else:
                probabilities = _frequencies([i["choice"] for i in items], keys)
                choice = max(keys, key=lambda k: probabilities[k])  # first key wins ties
                confidence = judgment.concentration_confidence(probabilities)
            answers[name] = {"type": "choice", "choice": choice, "confidence": round(confidence, 4),
                             "probabilities": probabilities}
        else:  # score
            criteria = list(question["criteria"])
            keys = [str(i) for i in range(len(criteria))]
            legend = {str(i): level for i, level in enumerate(criteria)}
            if single:
                level, confidence = items[0]["level"], items[0]["confidence"]
                probabilities = _spread(str(level), keys, confidence)
                score = float(level)
            else:
                probabilities = _frequencies([str(i["level"]) for i in items], keys)
                score = sum(i["level"] for i in items) / len(items)
                confidence = judgment.concentration_confidence(probabilities)
            answers[name] = {"type": "score", "score": round(score, 4), "confidence": round(confidence, 4),
                             "legend": legend, "probabilities": probabilities}
    return answers


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


def _error_message(response: requests.Response) -> str:
    status = response.status_code
    if status == 401:
        base = "Chat backend authentication failed (check JUDGMENT_API_KEY)"
    elif status == 404:
        base = ("Chat backend returned 404 (unknown model or wrong JUDGMENT_BASE_URL; Ollama's "
                "OpenAI-compatible base is http://host:11434/v1)")
    elif status == 400:
        base = ("Chat backend rejected the request (the server must support JSON-schema "
                "structured outputs via response_format)")
    elif status == 429:
        base = "Chat backend rate limit exceeded"
    else:
        base = f"Chat backend error {status}"
    detail = judgment.error_detail(response)
    return f"{base}: {detail}" if detail else base


class ChatJudgeClient:
    """Judgment backend over an OpenAI-compatible ``/chat/completions`` endpoint."""

    name = "openai"
    calibrated = False

    def __init__(self, config: JudgmentConfig, *, sleep: Callable[[float], None] = time.sleep):
        self.config = config
        self._sleep = sleep
        self._session = requests.Session()

    @property
    def confidence_source(self) -> str:
        return "vote_frequency" if self.config.samples > 1 else "self_reported"

    @property
    def _url(self) -> str:
        return f"{self.config.base_url}{CHAT_PATH}"

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

    def evaluate(self, state: Any, questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
        if not questions:
            raise JudgmentError("At least one question is required")
        schema = build_schema(questions)
        body = {
            "model": self.config.model,
            "messages": build_messages(state, questions, schema),
            "temperature": 0 if self.config.samples == 1 else SAMPLING_TEMPERATURE,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": SCHEMA_NAME, "strict": True, "schema": schema},
            },
        }
        replies: list[dict[str, dict[str, Any]]] = []
        usage: dict[str, int] = {}
        for _ in range(self.config.samples):
            reply, reply_usage = self._complete(body, questions)
            replies.append(reply)
            judgment.add_usage(usage, reply_usage)
        return {"model": self.config.model, "answers": convert(questions, replies), "usage": usage}

    def _complete(self, body: dict[str, Any],
                  questions: dict[str, dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
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
            raise JudgmentError("Chat backend returned a non-JSON body",
                                status=response.status_code, request_id=request_id) from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise JudgmentError("Chat backend returned a malformed response (no choices[0].message.content)",
                                status=response.status_code, request_id=request_id) from None
        if not isinstance(content, str):
            raise JudgmentError("Chat backend returned a non-text message",
                                status=response.status_code, request_id=request_id)
        try:
            reply = validate_reply(parse_reply(content), questions)
        except JudgmentError as exc:
            raise JudgmentError(str(exc), status=response.status_code, request_id=request_id) from None

        raw_usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        usage = {}
        if isinstance(raw_usage.get("prompt_tokens"), int):
            usage["input_tokens"] = raw_usage["prompt_tokens"]
        if isinstance(raw_usage.get("completion_tokens"), int):
            usage["output_tokens"] = raw_usage["completion_tokens"]
        return reply, usage
