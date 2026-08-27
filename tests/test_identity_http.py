"""HTTP-layer tests for multi-identity mode: auth middleware, /healthz, policy,
audit log, and the core concurrency acceptance test.

The tests run a real uvicorn server (real TCP, real MCP handshake) with the
production middleware chain: ``MultiIdentityAuthMiddleware`` in front of a
FastMCP app that carries ``IdentityToolMiddleware``. Outgoing Snipe-IT calls
are mocked with ``responses`` and their ``Authorization`` headers are recorded
to prove per-request identity attribution.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from typing import Any

import httpx
import pytest
import responses
from responses import CallbackResponse
import uvicorn
from fastmcp import FastMCP
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from starlette.middleware import Middleware as StarletteMiddleware

from snipeit_mcp import client as _client
from snipeit_mcp.http_auth import (
    AUDIT_LOGGER_NAME,
    IdentityToolMiddleware,
    MultiIdentityAuthMiddleware,
)
from snipeit_mcp.identity import Identity, IdentityRegistry

SNIPEIT_URL = "https://test.snipeit.com"
TOKEN_A = "a" * 40
TOKEN_B = "b" * 40
TOKEN_C = "c" * 40
TOKEN_D = "d" * 40
SNIPEIT_TOKEN_A = "snipeit-pat-alice-00000000000000000000"
SNIPEIT_TOKEN_B = "snipeit-pat-bob-00000000000000000000"
SNIPEIT_TOKEN_C = "snipeit-pat-carol-00000000000000000000"
SNIPEIT_TOKEN_D = "snipeit-pat-dave-00000000000000000000"


def plain_registry() -> IdentityRegistry:
    """Two identities without policy restrictions (for auth + concurrency tests)."""
    return IdentityRegistry(
        identities=(
            Identity(key="ALICE", mcp_token=TOKEN_A, snipeit_token=SNIPEIT_TOKEN_A),
            Identity(key="BOB", mcp_token=TOKEN_B, snipeit_token=SNIPEIT_TOKEN_B),
        )
    )


def build_test_server(middleware_registry: IdentityRegistry) -> FastMCP:
    """A minimal FastMCP server whose tools go through ``client.get_direct_api()``
    — the same code path the production tools use for token resolution."""
    server = FastMCP("identity-test", middleware=[IdentityToolMiddleware(middleware_registry)])

    @server.tool
    def snipeit_list() -> dict:
        """List kits through the (mocked) Snipe-IT API."""
        api = _client.get_direct_api()
        rows, total = api.list_page("kits", limit=5)
        return {"success": True, "count": len(rows), "total": total}

    @server.tool
    def action_tool(action: str, note: str = "") -> dict:
        """Action-parameterized tool; ``list`` hits the API, anything else does not."""
        if action == "list":
            api = _client.get_direct_api()
            rows, _total = api.list_page("kits", limit=5)
            return {"success": True, "action": "list", "count": len(rows), "note": note}
        return {"success": True, "action": action, "note": note}

    return server


def _start_uvicorn(app: Any) -> tuple[uvicorn.Server, int]:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 15
    while not server.started:
        if server.should_exit or time.time() > deadline:
            raise RuntimeError("uvicorn failed to start")
        time.sleep(0.02)
    return server, port


@pytest.fixture
def server():
    """Start uvicorn instances on demand; each request builds its own app."""
    started: list[uvicorn.Server] = []

    def _run(registry: IdentityRegistry, **http_app_kwargs) -> int:
        test_server = build_test_server(registry)
        app = test_server.http_app(
            path="/mcp",
            stateless_http=True,
            middleware=[StarletteMiddleware(MultiIdentityAuthMiddleware, registry=registry)],
            **http_app_kwargs,
        )
        uv_server, port = _start_uvicorn(app)
        started.append(uv_server)
        return port

    yield _run

    for uv_server in started:
        uv_server.should_exit = True


@pytest.fixture(autouse=True)
def multi_identity_env(monkeypatch):
    """Point token resolution at the test Snipe-IT URL (multi-identity mode)."""
    monkeypatch.setenv("SNIPEIT_URL", SNIPEIT_URL)
    monkeypatch.delenv("SNIPEIT_TOKEN", raising=False)


async def _mcp_call(port: int, bearer_token: str, tool: str, arguments: dict) -> Any:
    """One full MCP round-trip (initialize + tools/call) against the test server."""
    url = f"http://127.0.0.1:{port}/mcp"
    headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool, arguments)


async def _mcp_call_expect_error(port: int, bearer_token: str, tool: str,
                                 arguments: dict) -> str:
    """Call a tool expected to be denied; return the error text.

    A denied call surfaces as a normal tool result with ``isError=True``
    (the middleware raises, FastMCP converts it to an error result) — not as a
    JSON-RPC exception — so we assert ``isError`` and return the text content.
    """
    url = f"http://127.0.0.1:{port}/mcp"
    headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else {}
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, arguments)
    assert result.isError is True, f"expected a tool error for {tool}({arguments})"
    return " ".join(block.text for block in result.content if hasattr(block, "text"))


# ----- /healthz and 401 -------------------------------------------------------


@pytest.mark.asyncio
async def test_healthz_without_header_returns_200(server):
    port = server(plain_registry())
    async with httpx.AsyncClient() as http:
        response = await http.get(f"http://127.0.0.1:{port}/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "identities": 2}


@pytest.mark.asyncio
async def test_missing_authorization_header_returns_401(server):
    port = server(plain_registry())
    async with httpx.AsyncClient() as http:
        response = await http.post(f"http://127.0.0.1:{port}/mcp", json={})
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_unknown_token_returns_401(server):
    port = server(plain_registry())
    async with httpx.AsyncClient() as http:
        response = await http.post(
            f"http://127.0.0.1:{port}/mcp",
            json={},
            headers={"Authorization": "Bearer not-a-known-token"},
        )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_wrong_scheme_returns_401(server):
    port = server(plain_registry())
    async with httpx.AsyncClient() as http:
        response = await http.post(
            f"http://127.0.0.1:{port}/mcp",
            json={},
            headers={"Authorization": f"Basic {TOKEN_A}"},
        )
    assert response.status_code == 401


# ----- Token resolution -------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_token_resolves_that_identitys_snipeit_token(server):
    registry = plain_registry()
    port = server(registry)
    seen_auth_headers: list[str] = []

    def _record(request):
        seen_auth_headers.append(request.headers.get("Authorization"))
        return (200, {}, json.dumps({"rows": [], "total": 0}))

    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(CallbackResponse(responses.GET, f"{SNIPEIT_URL}/api/v1/kits", _record))
        result = await _mcp_call(port, TOKEN_B, "snipeit_list", {})

    assert result.isError is False
    assert len(seen_auth_headers) == 1
    # BOB's token -> BOB's Snipe-IT PAT, not ALICE's.
    assert seen_auth_headers[0] == f"Bearer {SNIPEIT_TOKEN_B}"


@pytest.mark.asyncio
async def test_resolve_token_prefers_identity_over_env(monkeypatch):
    """The contextvar beats the SNIPEIT_TOKEN fallback (order: OAuth -> identity -> env)."""
    monkeypatch.setenv("SNIPEIT_TOKEN", "static-fallback-token")
    identity = Identity(key="ALICE", mcp_token=TOKEN_A, snipeit_token=SNIPEIT_TOKEN_A)
    token = _client.current_identity.set(identity)
    try:
        assert _client._resolve_token() == SNIPEIT_TOKEN_A
    finally:
        _client.current_identity.reset(token)


@pytest.mark.asyncio
async def test_env_fallback_still_works_without_identity(monkeypatch):
    monkeypatch.setenv("SNIPEIT_TOKEN", "static-fallback-token")
    assert _client.current_identity.get() is None
    assert _client._resolve_token() == "static-fallback-token"


# ----- Policy: allowlist and read-only ----------------------------------------


@pytest.mark.asyncio
async def test_allowlist_blocks_unlisted_tool(server):
    registry = IdentityRegistry(
        identities=(
            Identity(key="ALICE", mcp_token=TOKEN_A, snipeit_token=SNIPEIT_TOKEN_A,
                     allowed_tools=frozenset({"snipeit_list"})),
        )
    )
    port = server(registry)

    message = await _mcp_call_expect_error(port, TOKEN_A, "action_tool", {"action": "list"})
    assert "not allowed" in message
    assert "snipeit_list" in message

    # The listed tool still works.
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, f"{SNIPEIT_URL}/api/v1/kits",
                 json={"rows": [], "total": 0})
        result = await _mcp_call(port, TOKEN_A, "snipeit_list", {})
    assert result.isError is False


@pytest.mark.asyncio
async def test_allowlist_filters_tools_list(server):
    registry = IdentityRegistry(
        identities=(
            Identity(key="ALICE", mcp_token=TOKEN_A, snipeit_token=SNIPEIT_TOKEN_A,
                     allowed_tools=frozenset({"snipeit_list"})),
            Identity(key="BOB", mcp_token=TOKEN_B, snipeit_token=SNIPEIT_TOKEN_B),
        )
    )
    port = server(registry)

    url = f"http://127.0.0.1:{port}/mcp"

    async def _list_tools(bearer: str) -> list[str]:
        async with streamablehttp_client(url, headers={"Authorization": f"Bearer {bearer}"}) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()
                tools = await session.list_tools()
                return sorted(t.name for t in tools.tools)

    alice_tools = await _list_tools(TOKEN_A)
    bob_tools = await _list_tools(TOKEN_B)
    assert alice_tools == ["snipeit_list"]
    assert bob_tools == ["action_tool", "snipeit_list"]


@pytest.mark.asyncio
async def test_read_only_blocks_write_and_allows_read(server):
    registry = IdentityRegistry(
        identities=(
            Identity(key="BOB", mcp_token=TOKEN_B, snipeit_token=SNIPEIT_TOKEN_B,
                     read_only=True),
        )
    )
    port = server(registry)

    message = await _mcp_call_expect_error(port, TOKEN_B, "action_tool",
                                           {"action": "create", "note": "blocked"})
    assert "read-only" in message
    assert "create" in message

    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(responses.GET, f"{SNIPEIT_URL}/api/v1/kits",
                 json={"rows": [], "total": 0})
        result = await _mcp_call(port, TOKEN_B, "action_tool", {"action": "list"})
    assert result.isError is False


# ----- Concurrency (core acceptance test) --------------------------------------


@pytest.mark.asyncio
async def test_concurrent_requests_never_cross_assign_identities(server):
    """24 concurrent MCP sessions, two identities alternating.

    Every outgoing Snipe-IT request must carry the PAT of the identity that
    triggered it — a single misattribution (leaked contextvar) flips the
    per-PAT counts and fails the assertion.
    """
    registry = IdentityRegistry(
        identities=(
            Identity(key="ALICE", mcp_token=TOKEN_A, snipeit_token=SNIPEIT_TOKEN_A),
            Identity(key="BOB", mcp_token=TOKEN_B, snipeit_token=SNIPEIT_TOKEN_B),
        )
    )
    port = server(registry)

    import asyncio

    num_requests = 24
    seen_auth_headers: list[str] = []

    def _record(request):
        seen_auth_headers.append(request.headers.get("Authorization"))
        return (200, {}, json.dumps({"rows": [], "total": 0}))

    async def _task(index: int) -> bool:
        token = TOKEN_A if index % 2 == 0 else TOKEN_B
        result = await _mcp_call(port, token, "snipeit_list", {})
        return result.isError is False

    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        rsps.add(CallbackResponse(responses.GET, f"{SNIPEIT_URL}/api/v1/kits", _record))
        results = await asyncio.gather(*(_task(i) for i in range(num_requests)))

    assert all(results), "every tool call must succeed"
    assert len(seen_auth_headers) == num_requests

    pat_a = f"Bearer {SNIPEIT_TOKEN_A}"
    pat_b = f"Bearer {SNIPEIT_TOKEN_B}"
    expected_a = sum(1 for i in range(num_requests) if i % 2 == 0)
    expected_b = num_requests - expected_a
    # Exact per-PAT counts prove no request ran under the wrong identity:
    # any cross-assignment would add one PAT where the other is expected.
    assert seen_auth_headers.count(pat_a) == expected_a
    assert seen_auth_headers.count(pat_b) == expected_b
    assert set(seen_auth_headers) == {pat_a, pat_b}


# ----- Audit log ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_log_emits_json_line_per_call(server, caplog):
    registry = IdentityRegistry(
        identities=(
            Identity(key="ALICE", mcp_token=TOKEN_A, snipeit_token=SNIPEIT_TOKEN_A),
        )
    )
    port = server(registry)

    with (
        caplog.at_level("INFO", logger=AUDIT_LOGGER_NAME),
        responses.RequestsMock(assert_all_requests_are_fired=False) as rsps,
    ):
        rsps.add(responses.GET, f"{SNIPEIT_URL}/api/v1/kits",
                 json={"rows": [], "total": 0})
        result = await _mcp_call(port, TOKEN_A, "snipeit_list", {})
        assert result.isError is False

    audit_lines = [r for r in caplog.records if r.name == AUDIT_LOGGER_NAME]
    assert len(audit_lines) == 1
    record = json.loads(audit_lines[0].message)
    assert record["identity"] == "ALICE"
    assert record["tool"] == "snipeit_list"
    assert record["ok"] is True
    assert isinstance(record["duration_ms"], int)
    assert record["args_digest"] == ""  # no arguments passed
    # Structured fields, no secrets or raw tokens anywhere in the line.
    assert SNIPEIT_TOKEN_A not in audit_lines[0].message
    assert TOKEN_A not in audit_lines[0].message


@pytest.mark.asyncio
async def test_audit_log_digests_arguments_without_leaking_them(server, caplog):
    registry = IdentityRegistry(
        identities=(
            Identity(key="ALICE", mcp_token=TOKEN_A, snipeit_token=SNIPEIT_TOKEN_A),
        )
    )
    port = server(registry)

    secret_note = "top-secret-note-value"
    with caplog.at_level("INFO", logger=AUDIT_LOGGER_NAME):
        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(responses.GET, f"{SNIPEIT_URL}/api/v1/kits",
                     json={"rows": [], "total": 0})
            result = await _mcp_call(port, TOKEN_A, "action_tool",
                                     {"action": "list", "note": secret_note})
            assert result.isError is False

        record = json.loads(
            [r for r in caplog.records if r.name == AUDIT_LOGGER_NAME][0].message
        )
        assert record["action"] == "list"
        assert len(record["args_digest"]) == 16
        assert secret_note not in record["args_digest"]
        assert secret_note not in caplog.records[-1].message

        # Same arguments -> same digest (deterministic).
        with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
            rsps.add(responses.GET, f"{SNIPEIT_URL}/api/v1/kits",
                     json={"rows": [], "total": 0})
            await _mcp_call(port, TOKEN_A, "action_tool",
                            {"action": "list", "note": secret_note})
        second = json.loads(
            [r for r in caplog.records if r.name == AUDIT_LOGGER_NAME][1].message
        )
        assert record["args_digest"] == second["args_digest"]
        # The raw argument never appears in any captured audit line.
        assert secret_note not in caplog.records[-1].message