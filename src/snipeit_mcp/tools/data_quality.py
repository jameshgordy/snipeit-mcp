"""Snipe-IT data-quality tools backed by a judgment model (optional).

These tools answer questions the calling LLM *could* answer itself, but only by
paging hundreds of reference records through its context and comparing them by
hand. Instead, typed questions ("are these two records the same manufacturer?")
go to a *judgment backend* (:mod:`snipeit_mcp.judgment`): TypeSafe Jev or a
self-hosted System One model such as Laya, which return calibrated probabilities
in ~100 ms for a few hundredths of a cent per pair, or an OpenAI-compatible chat
model such as one served by Ollama, which is slower and whose confidence is
self-reported. Either way the comparison runs server-side and the agent
receives just the shortlist plus confidence.

* :func:`find_duplicates` — pairwise duplicate detection over one reference
  table (manufacturers, models, suppliers, locations, categories, companies,
  departments). Lexical blocking in code picks candidate pairs; Jev judges each
  pair on the entity-alignment rubric (different / possibly the same / same).
* :func:`match_records` — resolve free-text names (CSV cells, natural-language
  descriptions) to existing records, with an explicit "none" option so Jev can
  abstain. Useful before creating assets or mapping imports.

Both tools are read-only with respect to Snipe-IT, and are hidden from
``tools/list`` unless a judgment backend is configured (``TYPESAFE_API_KEY`` or
``JUDGMENT_*``; see :func:`snipeit_mcp.mcp_server.apply_optional_tool_visibility`).

Privacy: the projected fields of the scanned records (names, model numbers,
addresses, contact URLs/emails of suppliers and companies) are sent to the
configured backend — a hosted API unless you self-host. Users are deliberately
not supported here because user records are personal data. Restrict who may call these tools with the per-identity
allowlist if that matters for your deployment.

Endpoints used: ``GET /api/v1/{manufacturers,models,suppliers,locations,
categories,companies,departments}`` (verified against Snipe-IT v8.7.2; pages
are capped at ``config('app.max_results')`` = 500 rows).
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import combinations
from typing import Annotated, Any, Callable, Literal

from snipeit.exceptions import (
    SnipeITAuthenticationError,
    SnipeITException,
    SnipeITNotFoundError,
    SnipeITValidationError,
)

from .. import client as _client
from .. import judgment
from ..config import ConfigError
from ..mcp_server import mcp

logger = logging.getLogger(__name__)

EntityType = Literal[
    "manufacturers", "models", "suppliers", "locations", "categories", "companies", "departments"
]

# Snipe-IT caps API pages at config('app.max_results'), 500 by default (v8.7.2).
PAGE_SIZE = 500
MAX_RECORDS = 5000
MAX_PAIRS = 500
MAX_TEXTS = 200
# A choice question allows 255 options; one is reserved for the "none" option.
MAX_CANDIDATES = 254
MAX_WORKERS = 8
# Upper bound on lexical comparisons in the blocked path, so a huge bucket of
# records sharing a common token cannot reintroduce the O(n²) the blocking avoids.
MAX_SCORED_PAIRS = 20000
NONE_OPTION = "none"

VERDICTS = ("different", "review", "same")


def _sub_name(value: Any) -> str | None:
    """Name of a nested ``{"id": .., "name": ..}`` object, or ``None``."""
    return value.get("name") if isinstance(value, dict) else None


def _facts(row: dict, keys: tuple[str, ...]) -> dict[str, Any]:
    """Pick ``keys`` from ``row``, dropping empty values so Jev sees only signal."""
    out: dict[str, Any] = {}
    for key in keys:
        value = row.get(key)
        if isinstance(value, dict):
            value = _sub_name(value)
        if value not in (None, ""):
            out[key] = value
    return out


@dataclass(frozen=True)
class EntitySpec:
    """How one Snipe-IT reference table is fetched, projected, and resolved."""

    endpoint: str
    singular: str
    fields: tuple[str, ...]
    counts: tuple[str, ...]
    resolution_hint: str
    # Extra fields (besides ``name``) that free text may refer to in match_records.
    match_fields: tuple[str, ...] = ()
    # Records sharing this non-empty key are always candidate pairs (e.g. model_number).
    block_key: Callable[[dict], str | None] | None = None
    # Records with different values here can never be duplicates (e.g. category_type).
    partition_key: Callable[[dict], Any] | None = None

    def facts(self, row: dict) -> dict[str, Any]:
        return _facts(row, self.fields)

    def record(self, row: dict) -> dict[str, Any]:
        """The compact record returned to the agent (id + facts + counts)."""
        record: dict[str, Any] = {"id": row.get("id"), **self.facts(row)}
        counts = {k: row.get(k) for k in self.counts if isinstance(row.get(k), int)}
        if counts:
            record["counts"] = counts
        return record


ENTITY_SPECS: dict[str, EntitySpec] = {
    "manufacturers": EntitySpec(
        endpoint="manufacturers",
        singular="manufacturer",
        fields=("name", "url", "support_url", "support_email"),
        counts=("assets_count", "licenses_count", "accessories_count", "consumables_count",
                "components_count"),
        resolution_hint=(
            "Snipe-IT has no merge for manufacturers. Keep the record with the most items, "
            "point the other's models at it (manage_models action=update, model_data.manufacturer_id), "
            "then delete the emptied duplicate (manage_manufacturers action=delete)."
        ),
    ),
    "models": EntitySpec(
        endpoint="models",
        singular="asset model",
        fields=("name", "model_number", "manufacturer", "category"),
        counts=("assets_count",),
        match_fields=("model_number",),
        block_key=lambda row: normalize_name(row.get("model_number")) or None,
        resolution_hint=(
            "Move the duplicate's assets to the model to keep (bulk_asset_operations action=edit, "
            "asset_ids=[...], fields={'model_id': <keep>}), then delete the emptied duplicate "
            "(manage_models action=delete)."
        ),
    ),
    "suppliers": EntitySpec(
        endpoint="suppliers",
        singular="supplier",
        fields=("name", "url", "email", "phone", "city", "country"),
        counts=("assets_count", "accessories_count", "licenses_count", "consumables_count",
                "components_count"),
        resolution_hint=(
            "Re-point supplier_id on the duplicate's assets/licenses/accessories to the record to "
            "keep, then delete the emptied duplicate (manage_suppliers action=delete)."
        ),
    ),
    "locations": EntitySpec(
        endpoint="locations",
        singular="location",
        fields=("name", "address", "city", "state", "country", "zip", "parent"),
        counts=("assets_count", "assigned_assets_count", "users_count", "children_count"),
        resolution_hint=(
            "Re-point location_id / rtd_location_id on assets (bulk_asset_operations action=edit, "
            "fields={'location_id': <keep>}) "
            "and location_id on users to the record to keep, move child locations, then delete "
            "the emptied duplicate (manage_locations action=delete)."
        ),
    ),
    "categories": EntitySpec(
        endpoint="categories",
        singular="category",
        fields=("name", "category_type"),
        counts=("assets_count", "accessories_count", "consumables_count", "components_count",
                "licenses_count"),
        partition_key=lambda row: row.get("category_type"),
        resolution_hint=(
            "Categories of different types are never duplicates and were not compared. Re-point "
            "category_id on the duplicate's models/items to the record to keep, then delete the "
            "emptied duplicate (manage_categories action=delete)."
        ),
    ),
    "companies": EntitySpec(
        endpoint="companies",
        singular="company",
        fields=("name", "email", "phone", "parent"),
        counts=("assets_count", "users_count", "licenses_count", "accessories_count",
                "consumables_count", "components_count"),
        resolution_hint=(
            "Re-point company_id on the duplicate's assets, users and licenses to the record to "
            "keep, then delete the emptied duplicate (manage_companies action=delete)."
        ),
    ),
    "departments": EntitySpec(
        endpoint="departments",
        singular="department",
        fields=("name", "company", "location"),
        counts=("users_count",),
        resolution_hint=(
            "Re-point department_id on the duplicate's users (manage_users action=update) to the "
            "record to keep, then delete the emptied duplicate (manage_departments action=delete)."
        ),
    ),
}


# ---------------------------------------------------------------------------
# Lexical blocking (pure functions; unit-tested)
# ---------------------------------------------------------------------------

_NON_ALNUM = re.compile(r"[^0-9a-z]+")


def normalize_name(value: Any) -> str:
    """Lower-case, strip accents and punctuation, collapse whitespace."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = _NON_ALNUM.sub(" ", text.lower())
    return " ".join(text.split())


def lexical_similarity(a: Any, b: Any) -> float:
    """Cheap 0–1 similarity used only to pick which pairs Jev gets to see.

    Max of character ratio, token Jaccard, and a containment bonus. This is a
    recall knob, not a verdict: abbreviations ("HP" vs "Hewlett-Packard") score
    low here and are only caught when the table is small enough to compare
    exhaustively.
    """
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ratio = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jaccard = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    containment = 0.8 if min(len(na), len(nb)) >= 3 and (na in nb or nb in na) else 0.0
    return round(max(ratio, jaccard, containment), 4)


def _index_keys(normalized: str) -> set[str]:
    keys = {tok for tok in normalized.split() if len(tok) >= 2}
    if len(normalized) >= 3:
        keys.add("^" + normalized[:3])
    return keys


def candidate_pairs(
    records: list[dict],
    *,
    min_similarity: float,
    max_pairs: int,
    block_key: Callable[[dict], str | None] | None = None,
    partition_key: Callable[[dict], Any] | None = None,
) -> tuple[list[tuple[int, int, float]], bool]:
    """Return ``([(i, j, similarity), ...], blocked, saturated)`` for records worth judging.

    When every compatible pair fits in ``max_pairs`` (small tables), all pairs are
    returned and ``blocked`` is ``False`` — the model then also sees abbreviation
    cases that lexical similarity would miss. Otherwise only pairs sharing a
    token, a 3-character prefix, or ``block_key`` are scored; those at or above
    ``min_similarity`` are kept, best first, capped at ``max_pairs``. Buckets
    are visited smallest (most specific) first and scoring stops after
    :data:`MAX_SCORED_PAIRS` comparisons, in which case ``saturated`` is ``True``
    and the caller should narrow the scan with ``search``.
    Pairs whose ``partition_key`` differs are never candidates.
    """
    n = len(records)

    def compatible(i: int, j: int) -> bool:
        if partition_key is None:
            return True
        return partition_key(records[i]) == partition_key(records[j])

    def similarity(i: int, j: int) -> float:
        sim = lexical_similarity(records[i].get("name"), records[j].get("name"))
        if block_key is not None:
            ki, kj = block_key(records[i]), block_key(records[j])
            if ki and kj and ki == kj:
                sim = 1.0
        return sim

    if compatible_pair_count(records, partition_key) <= max_pairs:
        pairs = [(i, j, similarity(i, j)) for i, j in combinations(range(n), 2) if compatible(i, j)]
        return pairs, False, False

    index: dict[str, list[int]] = {}
    for i, row in enumerate(records):
        keys = _index_keys(normalize_name(row.get("name")))
        if block_key is not None:
            bk = block_key(row)
            if bk:
                keys.add("#" + bk)
        for key in keys:
            index.setdefault(key, []).append(i)

    seen: set[tuple[int, int]] = set()
    saturated = False
    for members in sorted(index.values(), key=len):
        if len(members) < 2:
            continue
        for i, j in combinations(members, 2):
            if len(seen) >= MAX_SCORED_PAIRS:
                saturated = True
                break
            if compatible(i, j):
                seen.add((i, j) if i < j else (j, i))
        if saturated:
            break

    scored = [(i, j, similarity(i, j)) for i, j in seen]
    kept = [p for p in scored if p[2] >= min_similarity]
    kept.sort(key=lambda p: (-p[2], p[0], p[1]))
    return kept[:max_pairs], True, saturated


def compatible_pair_count(records: list[dict], partition_key: Callable[[dict], Any] | None) -> int:
    """Number of unordered pairs that could be duplicates (same partition)."""
    if partition_key is None:
        n = len(records)
        return n * (n - 1) // 2
    sizes: dict[Any, int] = {}
    for row in records:
        key = partition_key(row)
        sizes[key] = sizes.get(key, 0) + 1
    return sum(k * (k - 1) // 2 for k in sizes.values())


def rank_candidates(text: str, records: list[dict], fields: tuple[str, ...], top: int) -> list[int]:
    """Indexes of the ``top`` records most lexically similar to ``text``."""
    scored = []
    for i, row in enumerate(records):
        sim = max(lexical_similarity(text, row.get(f)) for f in fields)
        scored.append((-sim, i))
    scored.sort()
    return [i for _, i in scored[:top]]


# ---------------------------------------------------------------------------
# Jev questions
# ---------------------------------------------------------------------------

_SAME_ENTITY_CRITERIA = (
    "Different {s}s. The names refer to distinct things; the differences are not "
    "just spelling, casing, punctuation, abbreviation or formatting.",
    "Possibly the same {s}. The names are clearly related (shared brand or base name, "
    "abbreviation, partial overlap) but the records may still be distinct — for example "
    "a parent and a variant, or two sites of one organisation. A person should decide.",
    "The same {s}. The names are spelling, casing, punctuation, whitespace, accent, "
    "abbreviation, legal-suffix (Inc, Ltd, GmbH, Co) or word-order variants of one name, "
    "and no other field contradicts that.",
)


def pair_questions(spec: EntitySpec) -> dict[str, dict[str, Any]]:
    """The questions asked about every candidate pair (entity-alignment rubric)."""
    return {
        "same_entity": {
            "type": "score",
            "instructions": (
                f"Do record_a and record_b describe the same {spec.singular}? Judge from the "
                "names first; use the other fields only to confirm or contradict."
            ),
            "criteria": [c.format(s=spec.singular) for c in _SAME_ENTITY_CRITERIA],
        },
        "name_variant": {
            "type": "noul",
            "instructions": "record_a.name and record_b.name are variants of the same name.",
            "criteria": {
                "true": (
                    "The same name written differently: spelling, casing, punctuation, "
                    "whitespace, accents, abbreviation, legal suffix, or word order."
                ),
                "false": "Different names, even if they share a word or a brand.",
            },
        },
    }


def pair_state(spec: EntitySpec, row_a: dict, row_b: dict) -> dict[str, Any]:
    return {"entity_type": spec.singular, "record_a": spec.facts(row_a), "record_b": spec.facts(row_b)}


def match_question(spec: EntitySpec, criteria: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        "match": {
            "type": "choice",
            "instructions": (
                f"Which of the listed {spec.singular} records does `text` refer to? Compare "
                f"`text` against each option's fields. Choose `{NONE_OPTION}` if no option is "
                f"the same {spec.singular}."
            ),
            "criteria": criteria,
        }
    }


def verdict_from_score(score: Any) -> str:
    """Round a 3-level score to ``different`` / ``review`` / ``same``."""
    try:
        level = int(round(float(score)))
    except (TypeError, ValueError):
        return "review"
    return VERDICTS[max(0, min(level, 2))]


# ---------------------------------------------------------------------------
# Snipe-IT fetch
# ---------------------------------------------------------------------------


def _fetch_all(api: Any, endpoint: str, limit: int, search: str | None) -> tuple[list[dict], int]:
    """Fetch up to ``limit`` rows in stable (id asc) pages of ``PAGE_SIZE``.

    Terminates on the server-reported ``total`` (or an empty page), not on a
    short page: Snipe-IT clamps every response to its own ``max_results``,
    which an admin may set below ``PAGE_SIZE``.
    """
    rows_all: list[dict] = []
    total = 0
    offset = 0
    while len(rows_all) < limit:
        page = min(PAGE_SIZE, limit - len(rows_all))
        rows, total = api.list_page(endpoint, limit=page, offset=offset, search=search)
        rows_all.extend(rows)
        if not rows or len(rows_all) >= total:
            break
        offset += len(rows)
    return rows_all[:limit], max(total, len(rows_all))


def _run_parallel(jobs: list[Any], fn: Callable[[Any], dict],
                  time_budget: float) -> list[dict | None]:
    """Run ``fn`` over ``jobs`` on a thread pool, in order, within ``time_budget`` seconds.

    Jobs not finished by the deadline are cancelled and come back as ``None``;
    a job already running when the deadline passes is allowed to finish (each
    is bounded by the backend's request timeout and retry policy).
    """
    if not jobs:
        return []
    results: list[dict | None] = [None] * len(jobs)
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(jobs))) as pool:
        futures = {pool.submit(fn, job): index for index, job in enumerate(jobs)}
        try:
            for future in as_completed(futures, timeout=time_budget):
                results[futures[future]] = future.result()
        except TimeoutError:
            logger.warning("Judgment time budget of %ss exhausted; skipping pending work", time_budget)
            pool.shutdown(wait=True, cancel_futures=True)
            for future, index in futures.items():
                if future.done() and not future.cancelled():
                    results[index] = future.result()
    return results


def _error_dict(tool: str, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, judgment.JudgmentNotConfiguredError):
        return {"success": False, "error": str(exc)}
    if isinstance(exc, ConfigError):
        return {"success": False, "error": f"Configuration error: {exc}"}
    if isinstance(exc, judgment.JudgmentError):
        return {"success": False, "error": f"Judgment backend error: {exc}"}
    if isinstance(exc, SnipeITNotFoundError):
        return {"success": False, "error": f"Not found: {exc}"}
    if isinstance(exc, SnipeITAuthenticationError):
        return {"success": False, "error": f"Authentication failed: {exc}"}
    if isinstance(exc, SnipeITValidationError):
        return {"success": False, "error": f"Validation error: {exc}"}
    if isinstance(exc, SnipeITException):
        return {"success": False, "error": f"Snipe-IT error: {exc}"}
    logger.error(f"Unexpected error in {tool}: {exc}", exc_info=True)
    return {"success": False, "error": f"Unexpected error: {exc}"}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
def find_duplicates(
    entity_type: Annotated[EntityType, "Which reference table to scan for duplicates"],
    limit: Annotated[int, f"Maximum records to fetch from Snipe-IT (1–{MAX_RECORDS})"] = 2000,
    search: Annotated[str | None, "Optional Snipe-IT search filter to narrow the scan"] = None,
    max_pairs: Annotated[int, f"Maximum candidate pairs to send to Jev (1–{MAX_PAIRS}); caps cost"] = 100,
    min_similarity: Annotated[float, "Lexical similarity (0–1) a pair needs to become a candidate when blocking applies"] = 0.6,
    include_different: Annotated[bool, "Also return pairs Jev judged different (default: counts only)"] = False,
) -> dict[str, Any]:
    """Find likely duplicate records in a Snipe-IT reference table using a judgment model.

    Requires a configured judgment backend (TypeSafe Jev via TYPESAFE_API_KEY, a
    self-hosted System One model, or an OpenAI-compatible chat model such as
    Ollama via JUDGMENT_*). Fetches the table, picks candidate pairs in code
    (all pairs for small tables; lexically similar pairs otherwise), and asks
    the backend for each pair whether the two records are the same entity.

    Returns:
        duplicates: pairs judged the same (verdict "same"), best first.
        review: pairs Jev found related but not certainly identical.
        different_count / different: pairs judged distinct.
        Each pair carries score (0 different, 1 possibly, 2 same), confidence,
        confidence_band (high ≥0.9, medium ≥0.5, low), per-level probabilities,
        the name_variant probability, both records with item counts (keep the
        one with more items), and a resolution_hint on how to merge in Snipe-IT.
        pairs_considered vs pairs_evaluated shows how much blocking cut.
        backend / calibrated / confidence_source say who judged: the bands are
        meaningful for calibrated System One models; for chat models the
        confidence is self-reported (or vote frequency) and only a hint.

    Nothing is modified. Verify before deleting: treat "review" and low
    confidence as a to-check list, not a to-merge list.
    """
    try:
        spec = ENTITY_SPECS[entity_type]
        limit = max(1, min(int(limit), MAX_RECORDS))
        max_pairs = max(1, min(int(max_pairs), MAX_PAIRS))
        min_similarity = max(0.0, min(float(min_similarity), 1.0))

        backend = judgment.get_backend()
        api = _client.get_direct_api()
        rows, total = _fetch_all(api, spec.endpoint, limit, search)

        pairs, blocked, saturated = candidate_pairs(
            rows, min_similarity=min_similarity, max_pairs=max_pairs,
            block_key=spec.block_key, partition_key=spec.partition_key,
        )
        questions = pair_questions(spec)
        usage: dict[str, int] = {}
        model: str | None = None

        def evaluate(pair: tuple[int, int, float]) -> dict[str, Any]:
            i, j, sim = pair
            row_a, row_b = rows[i], rows[j]
            base = {"record_a": spec.record(row_a), "record_b": spec.record(row_b), "similarity": sim}
            try:
                data = backend.evaluate(pair_state(spec, row_a, row_b), questions)
            except judgment.JudgmentError as exc:
                return {**base, "error": str(exc)}
            answers = data.get("answers", {})
            same = answers.get("same_entity") or {}
            variant = answers.get("name_variant") or {}
            return {
                **base,
                "verdict": verdict_from_score(same.get("score")),
                "score": same.get("score"),
                "confidence": same.get("confidence"),
                "confidence_band": judgment.confidence_band(same.get("confidence")),
                "probabilities": same.get("probabilities"),
                "name_variant": variant.get("noul"),
                "_usage": data.get("usage"),
                "_model": data.get("model"),
            }

        started = time.monotonic()
        evaluated = _run_parallel(pairs, evaluate, backend.config.time_budget)

        duplicates: list[dict] = []
        review: list[dict] = []
        different: list[dict] = []
        errors: list[dict] = []
        skipped = 0
        for pair, item in zip(pairs, evaluated):
            if item is None:
                skipped += 1
                errors.append({"record_a_id": rows[pair[0]].get("id"), "record_b_id": rows[pair[1]].get("id"),
                               "error": f"skipped: time budget of {backend.config.time_budget:g}s exhausted"})
                continue
            judgment.add_usage(usage, item.pop("_usage", None))
            model = item.pop("_model", None) or model
            if "error" in item:
                errors.append({"record_a_id": item["record_a"].get("id"),
                               "record_b_id": item["record_b"].get("id"), "error": item["error"]})
            elif item["verdict"] == "same":
                duplicates.append(item)
            elif item["verdict"] == "review":
                review.append(item)
            else:
                different.append(item)

        def rank(item: dict) -> tuple:
            return (-(item.get("confidence") or 0.0), -(item.get("similarity") or 0.0))

        duplicates.sort(key=rank)
        review.sort(key=rank)

        n = len(rows)
        result: dict[str, Any] = {
            "success": True,
            "entity_type": entity_type,
            "records_scanned": n,
            "records_total": total,
            "truncated": total > n,
            "pairs_considered": compatible_pair_count(rows, spec.partition_key),
            "pairs_evaluated": len(evaluated) - len(errors),
            "blocking": {"applied": blocked, "saturated": saturated,
                         "min_similarity": min_similarity, "max_pairs": max_pairs},
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "time_budget_exhausted": skipped > 0,
            "duplicates": duplicates,
            "review": review,
            "different_count": len(different),
            "errors": errors,
            "backend": backend.name,
            "model": model or backend.config.model,
            "calibrated": backend.calibrated,
            "confidence_source": backend.confidence_source,
            "usage": usage,
            "resolution_hint": spec.resolution_hint,
        }
        if include_different:
            result["different"] = different
        notes = []
        if total > n:
            notes.append(f"Only the first {n} of {total} records were scanned (ordered by id). "
                         "Raise limit or use search to cover the rest.")
        if saturated:
            notes.append(f"Lexical blocking stopped after {MAX_SCORED_PAIRS} comparisons; many records "
                         "share common name tokens. Use search to scan a narrower slice.")
        if skipped:
            notes.append(f"{skipped} pair(s) were not judged within the time budget "
                         f"({backend.config.time_budget:g}s, JUDGMENT_TIME_BUDGET); rerun with a "
                         "smaller max_pairs or a narrower search.")
        if notes:
            result["note"] = " ".join(notes)
        return result

    except Exception as exc:  # noqa: BLE001 — tools always return a dict
        return _error_dict("find_duplicates", exc)


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
def match_records(
    entity_type: Annotated[EntityType, "Which reference table the texts should be matched against"],
    texts: Annotated[list[str], f"Free-text names to resolve, e.g. CSV cells or spoken names (1–{MAX_TEXTS})"],
    context: Annotated[str | None, "Optional context shared by all texts (e.g. 'column from a laptop purchase order')"] = None,
    candidates_per_text: Annotated[int, f"How many lexically closest records Jev sees per text (1–{MAX_CANDIDATES})"] = 50,
    top_k: Annotated[int, "How many alternatives to return per text (1–20)"] = 5,
    limit: Annotated[int, f"Maximum records to fetch from Snipe-IT (1–{MAX_RECORDS})"] = 2000,
    search: Annotated[str | None, "Optional Snipe-IT search filter to narrow the candidate table"] = None,
) -> dict[str, Any]:
    """Resolve free-text names to existing Snipe-IT records using a judgment model.

    Requires a configured judgment backend (TYPESAFE_API_KEY or JUDGMENT_*). For
    each text, the lexically closest records are offered to the backend as
    options together with an explicit "none" option, and it picks one with a
    probability per option.

    Returns, per text: verdict ("accept" when confidence ≥ 0.9, "review" for a
    weaker match, "none" when nothing fits), the matched record (id + fields),
    confidence, and the top alternatives with probabilities. Use the ids
    directly in create/update/import payloads for "accept"; confirm "review".
    backend / calibrated / confidence_source say who judged; the 0.9 threshold
    is meaningful for calibrated System One models and only a hint for chat
    models, whose confidence is self-reported (or vote frequency).

    Nothing is modified.
    """
    try:
        spec = ENTITY_SPECS[entity_type]
        if not isinstance(texts, list) or not texts:
            return {"success": False, "error": "texts must be a non-empty list of strings"}
        if len(texts) > MAX_TEXTS:
            return {"success": False, "error": f"texts may contain at most {MAX_TEXTS} entries"}
        cleaned = [str(t).strip() for t in texts]
        if any(not t for t in cleaned):
            return {"success": False, "error": "texts must not contain empty strings"}
        candidates_per_text = max(1, min(int(candidates_per_text), MAX_CANDIDATES))
        top_k = max(1, min(int(top_k), 20))
        limit = max(1, min(int(limit), MAX_RECORDS))

        backend = judgment.get_backend()
        api = _client.get_direct_api()
        rows, total = _fetch_all(api, spec.endpoint, limit, search)
        if not rows:
            return {"success": False, "error": f"No {entity_type} found in Snipe-IT to match against"}

        match_fields = ("name", *spec.match_fields)

        def resolve(text: str) -> dict[str, Any]:
            idxs = rank_candidates(text, rows, match_fields, candidates_per_text)
            offered = {str(rows[i].get("id")): rows[i] for i in idxs}
            criteria: dict[str, Any] = {key: spec.facts(row) for key, row in offered.items()}
            criteria[NONE_OPTION] = f"None of the listed {spec.singular} records is the one `text` describes."
            state: dict[str, Any] = {"entity_type": spec.singular, "text": text}
            if context:
                state["context"] = context
            try:
                data = backend.evaluate(state, match_question(spec, criteria))
            except judgment.JudgmentError as exc:
                return {"text": text, "verdict": "error", "error": str(exc)}

            answer = (data.get("answers") or {}).get("match") or {}
            choice = answer.get("choice")
            confidence = answer.get("confidence")
            probabilities = answer.get("probabilities") or {}
            if choice != NONE_OPTION and choice not in offered:
                # The backend must pick from the options it was given; anything
                # else is a protocol violation, never a match.
                return {"text": text, "verdict": "error",
                        "error": f"backend chose {choice!r}, which was not among the offered options",
                        "_usage": data.get("usage"), "_model": data.get("model")}
            ranked = sorted(((k, p) for k, p in probabilities.items() if k == NONE_OPTION or k in offered),
                            key=lambda kv: -kv[1])
            alternatives = []
            for key, prob in ranked[:top_k]:
                row = offered.get(key)
                alternatives.append({
                    "id": row.get("id") if row else None,
                    "name": row.get("name") if row else NONE_OPTION,
                    "probability": prob,
                })

            if choice == NONE_OPTION:
                verdict, match = "none", None
            else:
                match = spec.record(offered[choice])
                verdict = "accept" if judgment.confidence_band(confidence) == "high" else "review"
            return {
                "text": text,
                "verdict": verdict,
                "match": match,
                "confidence": confidence,
                "confidence_band": judgment.confidence_band(confidence),
                "alternatives": alternatives,
                "_usage": data.get("usage"),
                "_model": data.get("model"),
            }

        started = time.monotonic()
        raw_results = _run_parallel(cleaned, resolve, backend.config.time_budget)
        usage: dict[str, int] = {}
        model: str | None = None
        summary = {"accept": 0, "review": 0, "none": 0, "error": 0}
        results: list[dict[str, Any]] = []
        skipped = 0
        for text, item in zip(cleaned, raw_results):
            if item is None:
                skipped += 1
                item = {"text": text, "verdict": "error",
                        "error": f"skipped: time budget of {backend.config.time_budget:g}s exhausted"}
            judgment.add_usage(usage, item.pop("_usage", None))
            model = item.pop("_model", None) or model
            summary[item["verdict"]] = summary.get(item["verdict"], 0) + 1
            results.append(item)

        n = len(rows)
        result: dict[str, Any] = {
            "success": True,
            "entity_type": entity_type,
            "records_scanned": n,
            "records_total": total,
            "truncated": total > n,
            "candidates_per_text": min(candidates_per_text, n),
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "time_budget_exhausted": skipped > 0,
            "results": results,
            "summary": summary,
            "backend": backend.name,
            "model": model or backend.config.model,
            "calibrated": backend.calibrated,
            "confidence_source": backend.confidence_source,
            "usage": usage,
        }
        notes = []
        if total > n:
            notes.append(f"Only the first {n} of {total} records were candidates (ordered by id). "
                         "Raise limit or use search to cover the rest.")
        if skipped:
            notes.append(f"{skipped} text(s) were not judged within the time budget "
                         f"({backend.config.time_budget:g}s, JUDGMENT_TIME_BUDGET); rerun with fewer texts.")
        if notes:
            result["note"] = " ".join(notes)
        return result

    except Exception as exc:  # noqa: BLE001 — tools always return a dict
        return _error_dict("match_records", exc)
