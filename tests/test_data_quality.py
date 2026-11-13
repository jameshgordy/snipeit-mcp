"""Tests for the judgment-backed data-quality tools.

End-to-end through the real ``SnipeITDirectAPI`` and the real backend clients with
only HTTP mocked (``responses``) — the Snipe-IT list endpoints, the System One
``/v1/systemone`` endpoint and the OpenAI-compatible ``/chat/completions`` endpoint.
Backend answers are produced by callbacks that inspect the request body, so the
tests also pin the exact state/questions we send.
"""

from __future__ import annotations

import json
import os
import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
import responses

from snipeit_mcp import find_duplicates, match_records
from snipeit_mcp.judgment import JUDGMENT_ENV_VARS, JudgmentConfig
from snipeit_mcp.tools import data_quality as dq
from snipeit_mcp.tools.data_quality import (
    ENTITY_SPECS,
    NONE_OPTION,
    candidate_pairs,
    compatible_pair_count,
    lexical_similarity,
    normalize_name,
    pair_questions,
    rank_candidates,
    verdict_from_score,
)

SNIPEIT = "https://test.snipeit.com/api/v1"
JEV = "https://api.typesafe.ai/v1/systemone"
CHAT = "http://localhost:11434/v1/chat/completions"


def get_tool_fn(tool):
    return tool.fn if hasattr(tool, "fn") else tool


@pytest.fixture
def systemone_env():
    """TypeSafe Jev via the typesafe-sdk alias variable (proves the alias works)."""
    with patch.dict(os.environ, {}):
        for var in JUDGMENT_ENV_VARS:
            os.environ.pop(var, None)
        os.environ["TYPESAFE_API_KEY"] = "ts-key-123"
        yield


@pytest.fixture
def ollama_env():
    with patch.dict(os.environ, {}):
        for var in JUDGMENT_ENV_VARS:
            os.environ.pop(var, None)
        os.environ["JUDGMENT_BACKEND"] = "openai"
        os.environ["JUDGMENT_MODEL"] = "qwen3:8b"
        yield


@pytest.fixture
def no_judgment_env():
    with patch.dict(os.environ, {}):
        for var in JUDGMENT_ENV_VARS:
            os.environ.pop(var, None)
        yield


def add_snipeit(endpoint: str, rows: list[dict], total: int | None = None) -> None:
    responses.add(responses.GET, f"{SNIPEIT}/{endpoint}",
                  json={"total": len(rows) if total is None else total, "rows": rows})


def add_jev(decide, *, status: int = 200):
    """Mock Jev with ``decide(body) -> answers``; records every request body."""
    bodies: list[dict] = []

    def callback(request):
        body = json.loads(request.body)
        bodies.append(body)
        if status != 200:
            return status, {"content-type": "application/json"}, json.dumps({"detail": "nope"})
        payload = {"model": "jev-1.13.0", "answers": decide(body),
                   "usage": {"input_tokens": 100, "output_tokens": 2}}
        return 200, {"content-type": "application/json"}, json.dumps(payload)

    responses.add_callback(responses.POST, JEV, callback=callback, content_type="application/json")
    return bodies


def query(call) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(call.request.url).query).items()}


def score_answer(level: int, confidence: float) -> dict:
    probs = {"0": 0.0, "1": 0.0, "2": 0.0}
    probs[str(level)] = confidence
    return {"type": "score", "score": float(level), "confidence": confidence,
            "legend": {"0": "different", "1": "possibly", "2": "same"}, "probabilities": probs}


def pair_names(body: dict) -> tuple[str, str]:
    return body["state"]["record_a"]["name"], body["state"]["record_b"]["name"]


MANUFACTURERS = [
    {"id": 1, "name": "Apple", "url": "https://apple.com", "support_url": None,
     "support_email": "", "assets_count": 120, "licenses_count": 3},
    {"id": 2, "name": "Apple Inc.", "url": None, "assets_count": 4, "licenses_count": 0},
    {"id": 3, "name": "Dell", "url": "https://dell.com", "assets_count": 80},
]


def decide_apple(body: dict) -> dict:
    a, b = pair_names(body)
    same = normalize_name(a).split()[0] == normalize_name(b).split()[0]
    return {
        "same_entity": score_answer(2, 0.93) if same else score_answer(0, 0.97),
        "name_variant": {"type": "noul", "noul": 0.96 if same else 0.02},
    }


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestBlockingHelpers:
    @pytest.mark.parametrize("raw,expected", [
        ("Apple, Inc.", "apple inc"),
        ("  Zürich   HQ ", "zurich hq"),
        ("HEWLETT-PACKARD", "hewlett packard"),
        (None, ""),
        (42, "42"),
    ])
    def test_normalize_name(self, raw, expected):
        assert normalize_name(raw) == expected

    def test_lexical_similarity(self):
        assert lexical_similarity("Apple", "apple ") == 1.0
        assert lexical_similarity("Dell", "Dell Inc") >= 0.6
        assert lexical_similarity("MacBook Pro 14", "Macbook Pro 14-inch") >= 0.6
        assert lexical_similarity("HP", "Hewlett-Packard") < 0.6
        assert lexical_similarity("", "Dell") == 0.0
        assert lexical_similarity(None, None) == 0.0

    def test_small_table_compares_every_pair(self):
        records = [{"name": "HP"}, {"name": "Hewlett-Packard"}, {"name": "Dell"}]
        pairs, blocked, _ = candidate_pairs(records, min_similarity=0.6, max_pairs=100)
        assert blocked is False
        assert {(i, j) for i, j, _ in pairs} == {(0, 1), (0, 2), (1, 2)}

    def test_large_table_blocks_by_similarity_and_caps(self):
        words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
                 "india", "juliet", "kilo", "lima", "mike", "november", "oscar", "papa"]
        records = [{"name": w.title()} for w in words] + [{"name": "Acme"}, {"name": "ACME Corp"}]
        pairs, blocked, _ = candidate_pairs(records, min_similarity=0.6, max_pairs=5)
        assert blocked is True
        assert len(pairs) <= 5
        assert (16, 17) in {(i, j) for i, j, _ in pairs}
        assert all(sim >= 0.6 for _, _, sim in pairs)

    def test_block_key_forces_candidates(self):
        records = [
            {"name": "MacBook Pro 14", "model_number": "A2779"},
            {"name": "MBP 14-inch", "model_number": "A2779"},
            {"name": "ThinkPad X1", "model_number": "20XW"},
            {"name": "Latitude 5420", "model_number": None},
        ]
        spec = ENTITY_SPECS["models"]
        pairs, blocked, _ = candidate_pairs(records, min_similarity=0.6, max_pairs=2,
                                         block_key=spec.block_key)
        assert blocked is True
        assert (0, 1, 1.0) in pairs

    def test_partition_key_excludes_incompatible_pairs(self):
        records = [
            {"name": "Laptops", "category_type": "asset"},
            {"name": "Laptops", "category_type": "accessory"},
            {"name": "Laptop", "category_type": "asset"},
        ]
        spec = ENTITY_SPECS["categories"]
        pairs, _, _ = candidate_pairs(records, min_similarity=0.6, max_pairs=100,
                                   partition_key=spec.partition_key)
        assert {(i, j) for i, j, _ in pairs} == {(0, 2)}

    def test_rank_candidates_uses_match_fields(self):
        records = [
            {"id": 12, "name": "MacBook Pro 14-inch (2023)", "model_number": "A2779"},
            {"id": 13, "name": "ThinkPad X1 Carbon Gen 11", "model_number": "21HM"},
        ]
        assert rank_candidates("A2779", records, ("name", "model_number"), 1) == [0]
        assert rank_candidates("thinkpad x1", records, ("name",), 1) == [1]

    def test_compatible_pair_count(self):
        rows = [{"t": "a"}, {"t": "a"}, {"t": "a"}, {"t": "b"}, {"t": "b"}]
        assert compatible_pair_count(rows, None) == 10
        assert compatible_pair_count(rows, lambda r: r["t"]) == 3 + 1

    @pytest.mark.parametrize("score,verdict", [
        (0, "different"), (0.4, "different"), (0.6, "review"), (1.0, "review"),
        (1.4, "review"), (1.6, "same"), (2.0, "same"), (5, "same"), (None, "review"), ("x", "review"),
    ])
    def test_verdict_from_score(self, score, verdict):
        assert verdict_from_score(score) == verdict

    def test_every_spec_is_complete(self):
        for name, spec in ENTITY_SPECS.items():
            assert spec.endpoint == name
            assert "name" in spec.fields
            assert spec.resolution_hint
            questions = pair_questions(spec)
            assert questions["same_entity"]["type"] == "score"
            assert len(questions["same_entity"]["criteria"]) == 3
            assert questions["name_variant"]["type"] == "noul"
            assert set(questions["name_variant"]["criteria"]) == {"true", "false"}


# ---------------------------------------------------------------------------
# find_duplicates
# ---------------------------------------------------------------------------


class TestFindDuplicates:
    @responses.activate
    def test_end_to_end_manufacturers(self, systemone_env):
        add_snipeit("manufacturers", MANUFACTURERS)
        bodies = add_jev(decide_apple)

        result = get_tool_fn(find_duplicates)(entity_type="manufacturers")

        # Snipe-IT fetch: one stable, full page.
        assert query(responses.calls[0]) == {"limit": "500", "offset": "0", "sort": "id", "order": "asc"}
        assert responses.calls[0].request.headers["Authorization"] == "Bearer test-token-12345"

        # Jev: every pair once; exact state + question shape for the Apple pair.
        assert len(bodies) == 3
        apple = next(b for b in bodies if pair_names(b) == ("Apple", "Apple Inc."))
        assert apple["model"] == "jev-latest"
        assert apple["state"] == {
            "entity_type": "manufacturer",
            "record_a": {"name": "Apple", "url": "https://apple.com"},  # empty fields dropped
            "record_b": {"name": "Apple Inc."},
        }
        assert apple["questions"] == pair_questions(ENTITY_SPECS["manufacturers"])
        same_entity = apple["questions"]["same_entity"]
        assert same_entity["type"] == "score" and len(same_entity["criteria"]) == 3
        assert apple["questions"]["name_variant"]["type"] == "noul"

        assert result["success"] is True
        assert result["entity_type"] == "manufacturers"
        assert result["records_scanned"] == 3 and result["records_total"] == 3
        assert result["truncated"] is False
        assert result["pairs_considered"] == 3 and result["pairs_evaluated"] == 3
        assert result["blocking"] == {"applied": False, "saturated": False, "min_similarity": 0.6, "max_pairs": 100}
        assert result["different_count"] == 2 and "different" not in result
        assert result["review"] == [] and result["errors"] == []
        assert result["model"] == "jev-1.13.0"
        assert (result["backend"], result["calibrated"], result["confidence_source"]) == ("systemone", True, "model")
        assert result["time_budget_exhausted"] is False and result["elapsed_seconds"] >= 0
        assert "note" not in result
        assert result["usage"] == {"input_tokens": 300, "output_tokens": 6}
        assert "manage_manufacturers" in result["resolution_hint"]

        [dup] = result["duplicates"]
        assert dup["verdict"] == "same"
        assert dup["score"] == 2.0 and dup["confidence"] == 0.93 and dup["confidence_band"] == "high"
        assert dup["probabilities"] == {"0": 0.0, "1": 0.0, "2": 0.93}
        assert dup["name_variant"] == 0.96
        assert dup["record_a"] == {"id": 1, "name": "Apple", "url": "https://apple.com",
                                   "counts": {"assets_count": 120, "licenses_count": 3}}
        assert dup["record_b"] == {"id": 2, "name": "Apple Inc.",
                                   "counts": {"assets_count": 4, "licenses_count": 0}}
        assert dup["similarity"] >= 0.6

    @responses.activate
    def test_include_different_returns_all_pairs(self, systemone_env):
        add_snipeit("manufacturers", MANUFACTURERS)
        add_jev(decide_apple)
        result = get_tool_fn(find_duplicates)(entity_type="manufacturers", include_different=True)
        assert len(result["different"]) == 2
        assert all(p["verdict"] == "different" for p in result["different"])

    @responses.activate
    def test_review_verdict_and_ordering(self, systemone_env):
        def decide(body):
            a, b = pair_names(body)
            if {a, b} == {"Apple", "Apple Inc."}:
                return {"same_entity": score_answer(1, 0.55), "name_variant": {"type": "noul", "noul": 0.5}}
            return {"same_entity": score_answer(0, 0.99), "name_variant": {"type": "noul", "noul": 0.0}}

        add_snipeit("manufacturers", MANUFACTURERS)
        add_jev(decide)
        result = get_tool_fn(find_duplicates)(entity_type="manufacturers")
        assert result["duplicates"] == []
        [rev] = result["review"]
        assert rev["verdict"] == "review" and rev["confidence_band"] == "medium"

    @responses.activate
    def test_paginates_in_stable_pages(self, systemone_env, monkeypatch):
        monkeypatch.setattr(dq, "PAGE_SIZE", 2)
        responses.add(responses.GET, f"{SNIPEIT}/suppliers",
                      json={"total": 3, "rows": [{"id": 1, "name": "Alpha"}, {"id": 2, "name": "Bravo"}]})
        responses.add(responses.GET, f"{SNIPEIT}/suppliers",
                      json={"total": 3, "rows": [{"id": 3, "name": "Charlie"}]})
        add_jev(lambda body: {"same_entity": score_answer(0, 0.99), "name_variant": {"type": "noul", "noul": 0.0}})

        result = get_tool_fn(find_duplicates)(entity_type="suppliers")

        # Each page asks for a full PAGE_SIZE; the short second page ends the loop.
        gets = [c for c in responses.calls if c.request.method == "GET"]
        assert [query(c) for c in gets] == [
            {"limit": "2", "offset": "0", "sort": "id", "order": "asc"},
            {"limit": "2", "offset": "2", "sort": "id", "order": "asc"},
        ]
        assert result["records_scanned"] == 3 and result["pairs_evaluated"] == 3

    @responses.activate
    def test_limit_truncates_and_notes(self, systemone_env):
        add_snipeit("locations", [{"id": 1, "name": "HQ"}, {"id": 2, "name": "HQ Berlin"}], total=50)
        add_jev(lambda body: {"same_entity": score_answer(0, 0.9), "name_variant": {"type": "noul", "noul": 0.1}})

        result = get_tool_fn(find_duplicates)(entity_type="locations", limit=2, search="HQ")

        assert query(responses.calls[0]) == {"limit": "2", "offset": "0", "sort": "id",
                                             "order": "asc", "search": "HQ"}
        assert result["truncated"] is True and result["records_total"] == 50
        assert "first 2 of 50" in result["note"]

    @responses.activate
    def test_blocking_only_sends_similar_pairs(self, systemone_env):
        words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
                 "india", "juliet", "kilo", "lima", "mike", "november", "oscar", "papa"]
        rows = [{"id": i + 1, "name": w.title()} for i, w in enumerate(words)]
        rows += [{"id": 90, "name": "Acme"}, {"id": 91, "name": "ACME Corp"}]
        add_snipeit("companies", rows)
        bodies = add_jev(lambda body: {"same_entity": score_answer(2, 0.9),
                                       "name_variant": {"type": "noul", "noul": 0.9}})

        result = get_tool_fn(find_duplicates)(entity_type="companies", max_pairs=5)

        assert result["pairs_considered"] == 18 * 17 // 2
        assert result["blocking"]["applied"] is True
        assert len(bodies) == 1 and pair_names(bodies[0]) == ("Acme", "ACME Corp")
        assert result["duplicates"][0]["record_a"]["id"] == 90

    @responses.activate
    def test_categories_of_different_type_are_not_compared(self, systemone_env):
        add_snipeit("categories", [
            {"id": 1, "name": "Laptops", "category_type": "asset", "assets_count": 10},
            {"id": 2, "name": "Laptops", "category_type": "accessory", "accessories_count": 2},
            {"id": 3, "name": "Laptop", "category_type": "asset", "assets_count": 1},
        ])
        bodies = add_jev(lambda body: {"same_entity": score_answer(2, 0.95),
                                       "name_variant": {"type": "noul", "noul": 0.99}})

        result = get_tool_fn(find_duplicates)(entity_type="categories")

        assert len(bodies) == 1
        assert bodies[0]["state"] == {
            "entity_type": "category",
            "record_a": {"name": "Laptops", "category_type": "asset"},
            "record_b": {"name": "Laptop", "category_type": "asset"},
        }
        assert [(d["record_a"]["id"], d["record_b"]["id"]) for d in result["duplicates"]] == [(1, 3)]
        assert result["pairs_considered"] == 1  # cross-type pairs are not candidates at all

    @responses.activate
    def test_models_send_manufacturer_and_category_names(self, systemone_env):
        add_snipeit("models", [
            {"id": 12, "name": "MacBook Pro 14", "model_number": "A2779",
             "manufacturer": {"id": 1, "name": "Apple"}, "category": {"id": 5, "name": "Laptop"},
             "assets_count": 30},
            {"id": 13, "name": "Macbook Pro 14-inch", "model_number": "A2779",
             "manufacturer": {"id": 1, "name": "Apple"}, "category": None, "assets_count": 2},
        ])
        bodies = add_jev(lambda body: {"same_entity": score_answer(2, 0.9),
                                       "name_variant": {"type": "noul", "noul": 0.9}})
        result = get_tool_fn(find_duplicates)(entity_type="models")
        assert bodies[0]["state"]["entity_type"] == "asset model"
        assert bodies[0]["state"]["record_a"] == {"name": "MacBook Pro 14", "model_number": "A2779",
                                                  "manufacturer": "Apple", "category": "Laptop"}
        assert bodies[0]["state"]["record_b"] == {"name": "Macbook Pro 14-inch", "model_number": "A2779",
                                                  "manufacturer": "Apple"}
        assert result["duplicates"][0]["similarity"] == 1.0  # shared model_number
        assert "bulk_asset_operations" in result["resolution_hint"]

    @responses.activate
    def test_jev_failure_on_one_pair_is_reported_not_fatal(self, systemone_env):
        add_snipeit("manufacturers", MANUFACTURERS)

        def callback(request):
            body = json.loads(request.body)
            if "Dell" in pair_names(body) and "Apple" == pair_names(body)[0]:
                return 401, {}, json.dumps({"detail": "bad key"})
            payload = {"model": "jev-1.13.0", "answers": decide_apple(body),
                       "usage": {"input_tokens": 100, "output_tokens": 2}}
            return 200, {"content-type": "application/json"}, json.dumps(payload)

        responses.add_callback(responses.POST, JEV, callback=callback, content_type="application/json")

        result = get_tool_fn(find_duplicates)(entity_type="manufacturers")
        assert result["success"] is True
        assert result["pairs_evaluated"] == 2
        [err] = result["errors"]
        assert (err["record_a_id"], err["record_b_id"]) == (1, 3)
        assert "authentication" in err["error"].lower()
        assert len(result["duplicates"]) == 1

    @responses.activate
    def test_not_configured_makes_no_requests(self, no_judgment_env):
        add_snipeit("manufacturers", MANUFACTURERS)
        result = get_tool_fn(find_duplicates)(entity_type="manufacturers")
        assert result["success"] is False
        assert "TYPESAFE_API_KEY" in result["error"]
        assert len(responses.calls) == 0

    @responses.activate
    def test_bad_typesafe_config_is_reported(self, systemone_env):
        with patch.dict(os.environ, {"TYPESAFE_TIMEOUT": "abc"}):
            result = get_tool_fn(find_duplicates)(entity_type="manufacturers")
        assert result["success"] is False
        assert "TIMEOUT" in result["error"]
        assert len(responses.calls) == 0

    @responses.activate
    def test_snipeit_auth_error(self, systemone_env):
        responses.add(responses.GET, f"{SNIPEIT}/manufacturers", status=401)
        result = get_tool_fn(find_duplicates)(entity_type="manufacturers")
        assert result["success"] is False
        assert "authentication" in result["error"].lower()

    @responses.activate
    def test_snipeit_soft_error_is_surfaced(self, systemone_env):
        responses.add(responses.GET, f"{SNIPEIT}/manufacturers",
                      json={"status": "error", "messages": "Nope"})
        result = get_tool_fn(find_duplicates)(entity_type="manufacturers")
        assert result["success"] is False
        assert "Nope" in result["error"]

    @responses.activate
    def test_single_record_has_nothing_to_compare(self, systemone_env):
        add_snipeit("departments", [{"id": 1, "name": "IT"}])
        result = get_tool_fn(find_duplicates)(entity_type="departments")
        assert result["success"] is True
        assert result["pairs_considered"] == 0 and result["pairs_evaluated"] == 0
        assert result["duplicates"] == [] and result["usage"] == {}

    @responses.activate
    def test_parameters_are_clamped(self, systemone_env):
        add_snipeit("manufacturers", MANUFACTURERS)
        add_jev(decide_apple)
        result = get_tool_fn(find_duplicates)(entity_type="manufacturers", limit=999999,
                                              max_pairs=99999, min_similarity=7)
        assert query(responses.calls[0])["limit"] == "500"
        assert result["blocking"]["max_pairs"] == dq.MAX_PAIRS
        assert result["blocking"]["min_similarity"] == 1.0

    @responses.activate
    def test_paginates_past_a_server_side_cap(self, systemone_env):
        # The server clamps every page to 1 row (its own max_results) although we ask for 500.
        for row in ({"id": 1, "name": "Alpha"}, {"id": 2, "name": "Bravo"}, {"id": 3, "name": "Charlie"}):
            responses.add(responses.GET, f"{SNIPEIT}/suppliers", json={"total": 3, "rows": [row]})
        add_jev(lambda body: {"same_entity": score_answer(0, 0.99), "name_variant": {"type": "noul", "noul": 0.0}})

        result = get_tool_fn(find_duplicates)(entity_type="suppliers")

        gets = [c for c in responses.calls if c.request.method == "GET"]
        assert [query(c)["offset"] for c in gets] == ["0", "1", "2"]
        assert all(query(c)["limit"] == "500" for c in gets)
        assert result["records_scanned"] == 3 and result["pairs_evaluated"] == 3

    @responses.activate
    def test_saturated_blocking_is_reported(self, systemone_env, monkeypatch):
        monkeypatch.setattr(dq, "MAX_SCORED_PAIRS", 1)
        names = ["Main Office", "Main Warehouse", "Main Lab", "Main Depot", "Main Hub"]
        add_snipeit("locations", [{"id": i + 1, "name": n} for i, n in enumerate(names)])
        bodies = add_jev(lambda body: {"same_entity": score_answer(0, 0.9), "name_variant": {"type": "noul", "noul": 0.1}})

        result = get_tool_fn(find_duplicates)(entity_type="locations", max_pairs=2)

        assert result["blocking"]["applied"] is True and result["blocking"]["saturated"] is True
        assert len(bodies) <= 1
        assert "search" in result["note"]

    @responses.activate
    def test_time_budget_skips_pending_pairs(self, systemone_env, monkeypatch):
        add_snipeit("manufacturers", MANUFACTURERS)

        class SlowBackend:
            name, calibrated, confidence_source = "systemone", True, "model"
            config = JudgmentConfig(backend="systemone", base_url="http://x", model="m", api_key=None,
                                    timeout=1.0, time_budget=0.05)

            def evaluate(self, state, questions):
                time.sleep(0.2)
                return {"model": "m", "answers": {"same_entity": score_answer(0, 0.9),
                                                  "name_variant": {"type": "noul", "noul": 0.0}},
                        "usage": {"input_tokens": 1, "output_tokens": 1}}

        monkeypatch.setattr(dq.judgment, "get_backend", lambda: SlowBackend())
        monkeypatch.setattr(dq, "MAX_WORKERS", 1)

        result = get_tool_fn(find_duplicates)(entity_type="manufacturers")

        assert result["success"] is True
        assert result["time_budget_exhausted"] is True
        assert result["pairs_evaluated"] == 1
        skipped = [e for e in result["errors"] if "time budget" in e["error"]]
        assert len(skipped) == 2 and all(e["record_a_id"] and e["record_b_id"] for e in skipped)
        assert "JUDGMENT_TIME_BUDGET" in result["note"]

    @responses.activate
    def test_openai_backend_end_to_end(self, ollama_env):
        add_snipeit("manufacturers", MANUFACTURERS)
        bodies: list[dict] = []

        def callback(request):
            body = json.loads(request.body)
            bodies.append(body)
            user = body["messages"][1]["content"]
            state = json.loads(user[len("STATE:\n"):user.index("\n\nQUESTIONS:")])
            same = normalize_name(state["record_a"]["name"]).split()[0] == normalize_name(state["record_b"]["name"]).split()[0]
            reply = {"same_entity": {"level": 2 if same else 0, "confidence": 0.9},
                     "name_variant": {"answer": same, "confidence": 0.95}}
            payload = {"choices": [{"message": {"role": "assistant", "content": json.dumps(reply)}}],
                       "usage": {"prompt_tokens": 400, "completion_tokens": 30}}
            return 200, {"content-type": "application/json"}, json.dumps(payload)

        responses.add_callback(responses.POST, CHAT, callback=callback, content_type="application/json")

        result = get_tool_fn(find_duplicates)(entity_type="manufacturers")

        assert len(bodies) == 3
        assert bodies[0]["model"] == "qwen3:8b" and bodies[0]["temperature"] == 0
        schema = bodies[0]["response_format"]["json_schema"]["schema"]
        assert bodies[0]["response_format"]["type"] == "json_schema"
        assert schema["required"] == ["same_entity", "name_variant"]
        assert schema["properties"]["same_entity"]["properties"]["level"] == {"type": "integer", "minimum": 0, "maximum": 2}

        assert (result["backend"], result["calibrated"], result["confidence_source"]) == ("openai", False, "self_reported")
        assert result["model"] == "qwen3:8b"
        assert result["usage"] == {"input_tokens": 1200, "output_tokens": 90}
        [dup] = result["duplicates"]
        assert (dup["record_a"]["id"], dup["record_b"]["id"]) == (1, 2)
        assert dup["score"] == 2.0 and dup["confidence"] == 0.9 and dup["confidence_band"] == "high"
        assert dup["probabilities"] == {"0": 0.05, "1": 0.05, "2": 0.9}
        assert dup["name_variant"] == 0.95
        assert result["different_count"] == 2


# ---------------------------------------------------------------------------
# match_records
# ---------------------------------------------------------------------------

MODELS = [
    {"id": 12, "name": "MacBook Pro 14-inch (2023)", "model_number": "A2779",
     "manufacturer": {"id": 1, "name": "Apple"}, "category": {"id": 5, "name": "Laptop"},
     "assets_count": 30},
    {"id": 13, "name": "ThinkPad X1 Carbon Gen 11", "model_number": "21HM",
     "manufacturer": {"id": 2, "name": "Lenovo"}, "category": {"id": 5, "name": "Laptop"},
     "assets_count": 12},
    {"id": 14, "name": "Latitude 5420", "model_number": None,
     "manufacturer": {"id": 3, "name": "Dell"}, "category": {"id": 5, "name": "Laptop"},
     "assets_count": 7},
]


def decide_models(body: dict) -> dict:
    text = body["state"]["text"].lower()
    if "macbook" in text:
        return {"match": {"type": "choice", "choice": "12", "confidence": 0.95,
                          "probabilities": {"12": 0.96, "13": 0.02, "14": 0.01, NONE_OPTION: 0.01}}}
    if "thinkpad" in text:
        return {"match": {"type": "choice", "choice": "13", "confidence": 0.7,
                          "probabilities": {"13": 0.8, "12": 0.1, "14": 0.05, NONE_OPTION: 0.05}}}
    return {"match": {"type": "choice", "choice": NONE_OPTION, "confidence": 0.8,
                      "probabilities": {NONE_OPTION: 0.85, "12": 0.05, "13": 0.05, "14": 0.05}}}


class TestMatchRecords:
    @responses.activate
    def test_end_to_end_models(self, systemone_env):
        add_snipeit("models", MODELS)
        bodies = add_jev(decide_models)

        result = get_tool_fn(match_records)(
            entity_type="models",
            texts=["macbook pro 14 m3", "thinkpad x1", "some random widget"],
            context="Model column of a laptop purchase order",
        )

        assert query(responses.calls[0]) == {"limit": "500", "offset": "0", "sort": "id", "order": "asc"}
        assert len(bodies) == 3
        mac = next(b for b in bodies if b["state"]["text"] == "macbook pro 14 m3")
        assert mac["model"] == "jev-latest"
        assert mac["state"] == {"entity_type": "asset model", "text": "macbook pro 14 m3",
                                "context": "Model column of a laptop purchase order"}
        question = mac["questions"]["match"]
        assert question["type"] == "choice"
        assert NONE_OPTION in question["instructions"]
        assert set(question["criteria"]) == {"12", "13", "14", NONE_OPTION}
        assert question["criteria"]["12"] == {"name": "MacBook Pro 14-inch (2023)", "model_number": "A2779",
                                              "manufacturer": "Apple", "category": "Laptop"}
        assert question["criteria"]["14"] == {"name": "Latitude 5420", "manufacturer": "Dell",
                                              "category": "Laptop"}
        assert "asset model" in question["criteria"][NONE_OPTION]

        assert result["success"] is True
        assert result["records_scanned"] == 3 and result["truncated"] is False
        assert result["candidates_per_text"] == 3
        assert result["summary"] == {"accept": 1, "review": 1, "none": 1, "error": 0}
        assert result["usage"] == {"input_tokens": 300, "output_tokens": 6}
        assert result["model"] == "jev-1.13.0"
        assert (result["backend"], result["calibrated"], result["confidence_source"]) == ("systemone", True, "model")
        assert result["time_budget_exhausted"] is False

        mac_r, think_r, none_r = result["results"]
        assert mac_r["text"] == "macbook pro 14 m3"
        assert mac_r["verdict"] == "accept" and mac_r["confidence"] == 0.95
        assert mac_r["confidence_band"] == "high"
        assert mac_r["match"] == {"id": 12, "name": "MacBook Pro 14-inch (2023)", "model_number": "A2779",
                                  "manufacturer": "Apple", "category": "Laptop",
                                  "counts": {"assets_count": 30}}
        assert mac_r["alternatives"][0] == {"id": 12, "name": "MacBook Pro 14-inch (2023)", "probability": 0.96}
        assert mac_r["alternatives"][1] == {"id": 13, "name": "ThinkPad X1 Carbon Gen 11", "probability": 0.02}

        assert think_r["verdict"] == "review" and think_r["match"]["id"] == 13
        assert think_r["confidence_band"] == "medium"

        assert none_r["verdict"] == "none" and none_r["match"] is None
        assert none_r["alternatives"][0] == {"id": None, "name": NONE_OPTION, "probability": 0.85}

    @responses.activate
    def test_candidates_per_text_shortlists_lexically(self, systemone_env):
        add_snipeit("models", MODELS)
        bodies = add_jev(decide_models)
        get_tool_fn(match_records)(entity_type="models", texts=["A2779"], candidates_per_text=1, top_k=2)
        criteria = bodies[0]["questions"]["match"]["criteria"]
        assert set(criteria) == {"12", NONE_OPTION}  # model_number match wins the shortlist
        assert "context" not in bodies[0]["state"]

    @responses.activate
    def test_top_k_limits_alternatives(self, systemone_env):
        add_snipeit("models", MODELS)
        add_jev(decide_models)
        result = get_tool_fn(match_records)(entity_type="models", texts=["macbook"], top_k=2)
        assert len(result["results"][0]["alternatives"]) == 2

    @responses.activate
    def test_choice_outside_offered_options_is_error(self, systemone_env):
        add_snipeit("models", MODELS)
        add_jev(lambda body: {"match": {"type": "choice", "choice": "999", "confidence": 0.9,
                                        "probabilities": {"999": 0.9}}})
        result = get_tool_fn(match_records)(entity_type="models", texts=["x"])
        item = result["results"][0]
        assert item["verdict"] == "error" and "not among the offered options" in item["error"]
        assert result["summary"]["error"] == 1

    @responses.activate
    def test_choice_in_table_but_not_offered_is_error(self, systemone_env):
        add_snipeit("models", MODELS)
        bodies = add_jev(lambda body: {"match": {"type": "choice", "choice": "13", "confidence": 0.95,
                                                 "probabilities": {"13": 0.95, "12": 0.05}}})
        result = get_tool_fn(match_records)(entity_type="models", texts=["A2779"], candidates_per_text=1)
        assert set(bodies[0]["questions"]["match"]["criteria"]) == {"12", NONE_OPTION}
        item = result["results"][0]
        assert item["verdict"] == "error" and "'13'" in item["error"]

    @responses.activate
    def test_alternatives_only_from_offered_options(self, systemone_env):
        add_snipeit("models", MODELS)
        add_jev(lambda body: {"match": {"type": "choice", "choice": "12", "confidence": 0.95,
                                        "probabilities": {"12": 0.9, "13": 0.05, NONE_OPTION: 0.05}}})
        result = get_tool_fn(match_records)(entity_type="models", texts=["A2779"], candidates_per_text=1)
        item = result["results"][0]
        assert item["verdict"] == "accept" and item["match"]["id"] == 12
        assert [a["id"] for a in item["alternatives"]] == [12, None]  # "13" was never offered

    @responses.activate
    def test_jev_error_per_text(self, systemone_env):
        add_snipeit("models", MODELS)
        add_jev(lambda body: {}, status=401)
        result = get_tool_fn(match_records)(entity_type="models", texts=["a", "b"])
        assert result["success"] is True
        assert result["summary"] == {"accept": 0, "review": 0, "none": 0, "error": 2}
        assert all(r["verdict"] == "error" and "error" in r for r in result["results"])

    @responses.activate
    def test_input_validation(self, systemone_env):
        fn = get_tool_fn(match_records)
        assert fn(entity_type="models", texts=[])["success"] is False
        assert fn(entity_type="models", texts=["ok", "  "])["success"] is False
        too_many = fn(entity_type="models", texts=["x"] * (dq.MAX_TEXTS + 1))
        assert too_many["success"] is False and str(dq.MAX_TEXTS) in too_many["error"]
        assert len(responses.calls) == 0

    @responses.activate
    def test_no_records_to_match_against(self, systemone_env):
        add_snipeit("suppliers", [])
        result = get_tool_fn(match_records)(entity_type="suppliers", texts=["Acme"])
        assert result["success"] is False and "No suppliers" in result["error"]

    @responses.activate
    def test_not_configured(self, no_judgment_env):
        result = get_tool_fn(match_records)(entity_type="models", texts=["x"])
        assert result["success"] is False and "TYPESAFE_API_KEY" in result["error"]
        assert len(responses.calls) == 0

    @responses.activate
    def test_time_budget_skips_pending_texts(self, systemone_env, monkeypatch):
        add_snipeit("models", MODELS)

        class SlowBackend:
            name, calibrated, confidence_source = "systemone", True, "model"
            config = JudgmentConfig(backend="systemone", base_url="http://x", model="m", api_key=None,
                                    timeout=1.0, time_budget=0.05)

            def evaluate(self, state, questions):
                time.sleep(0.2)
                return {"model": "m", "answers": decide_models({"state": state}), "usage": {}}

        monkeypatch.setattr(dq.judgment, "get_backend", lambda: SlowBackend())
        monkeypatch.setattr(dq, "MAX_WORKERS", 1)

        result = get_tool_fn(match_records)(entity_type="models", texts=["macbook", "thinkpad", "other"])

        assert result["time_budget_exhausted"] is True
        assert result["summary"] == {"accept": 1, "review": 0, "none": 0, "error": 2}
        assert [r["text"] for r in result["results"]] == ["macbook", "thinkpad", "other"]
        assert all("time budget" in r["error"] for r in result["results"][1:])
        assert "JUDGMENT_TIME_BUDGET" in result["note"]

    @responses.activate
    def test_truncation_note(self, systemone_env):
        add_snipeit("locations", [{"id": 1, "name": "HQ"}], total=900)
        add_jev(lambda body: {"match": {"type": "choice", "choice": "1", "confidence": 0.99,
                                        "probabilities": {"1": 0.99, NONE_OPTION: 0.01}}})
        result = get_tool_fn(match_records)(entity_type="locations", texts=["hq"], limit=1)
        assert result["truncated"] is True and "first 1 of 900" in result["note"]
        assert result["results"][0]["verdict"] == "accept"


# ---------------------------------------------------------------------------
# Visibility
# ---------------------------------------------------------------------------


class TestVisibility:
    async def test_hidden_without_backend_visible_with_one(self, no_judgment_env):
        from snipeit_mcp.mcp_server import JUDGMENT_TOOLS, apply_tool_whitelist, mcp

        try:
            apply_tool_whitelist("")
            names = {t.name for t in await mcp.list_tools()}
            assert not (names & JUDGMENT_TOOLS)
            assert len(names) >= 40

            with patch.dict(os.environ, {"TYPESAFE_API_KEY": "k"}):
                apply_tool_whitelist("")
                names = {t.name for t in await mcp.list_tools()}
                assert JUDGMENT_TOOLS <= names

                apply_tool_whitelist("find_duplicates,system_info")
                names = {t.name for t in await mcp.list_tools()}
                assert names == {"find_duplicates", "system_info"}

            with patch.dict(os.environ, {"JUDGMENT_BACKEND": "openai", "JUDGMENT_MODEL": "qwen3:8b"}):
                apply_tool_whitelist("")
                names = {t.name for t in await mcp.list_tools()}
                assert JUDGMENT_TOOLS <= names

            apply_tool_whitelist("find_duplicates,system_info")
            names = {t.name for t in await mcp.list_tools()}
            assert names == {"system_info"}
        finally:
            apply_tool_whitelist("")

    async def test_tools_are_read_only(self, no_judgment_env):
        from snipeit_mcp.mcp_server import JUDGMENT_TOOLS, apply_tool_whitelist, mcp

        # get_tool() only resolves visible tools, so make them visible first.
        try:
            with patch.dict(os.environ, {"TYPESAFE_API_KEY": "k"}):
                apply_tool_whitelist("")
                for name in JUDGMENT_TOOLS:
                    tool = await mcp.get_tool(name)
                    assert tool is not None, name
                    assert tool.annotations.readOnlyHint is True
                    assert tool.annotations.destructiveHint is False
        finally:
            apply_tool_whitelist("")
