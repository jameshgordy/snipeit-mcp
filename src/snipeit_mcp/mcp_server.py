"""FastMCP server instance and tool registration for the Snipe-IT MCP server.

This module owns the singleton :class:`fastmcp.FastMCP` instance. Tool modules
under :mod:`snipeit_mcp.tools` import ``mcp`` from here and attach themselves
via ``@mcp.tool(...)`` decorators. Importing this module triggers registration
of every tool by importing :mod:`snipeit_mcp.tools` at the bottom.

The FastMCP instance is constructed per auth mode:

* **OAuth** — with a :class:`SnipeITOAuthProvider` (interactive web mode).
* **Multi-identity** — with the :class:`IdentityToolMiddleware`, which
  enforces each identity's tool allowlist / read-only flag, filters
  ``tools/list`` per identity, and writes the JSON audit line per tool call.
* **API key** — without any auth provider; tools authenticate via the static
  ``SNIPEIT_TOKEN`` env var.

The HTTP bearer-token layer (:class:`MultiIdentityAuthMiddleware`, which also
serves ``/healthz``) is registered at run time in :mod:`snipeit_mcp.__main__`,
not here.

Logging is *not* configured here — that lives in :mod:`snipeit_mcp.logging_config`
and must be called from the entry point before this module is imported, so
stdio JSON-RPC traffic on stdout stays uncorrupted.
"""

import logging
import os

from fastmcp import FastMCP

from .auth import SnipeITOAuthProvider
from .config import AuthMode, ConfigError, SnipeITAuthConfig
from .identity import load_identity_registry

logger = logging.getLogger(__name__)


def _load_auth_config():
    """Read the auth config at import time, tolerating a missing/partial setup.

    ``ConfigError`` is swallowed so the module stays importable in degraded
    modes (e.g. tests that set env vars per test); the real validation runs in
    ``__main__.main``. Any *other* exception must propagate loudly.
    """
    try:
        return SnipeITAuthConfig.from_env()
    except ConfigError:
        return None


def _build_auth_provider(cfg):
    """Construct the OAuth provider when OAuth mode is configured, else ``None``."""
    if cfg is None or cfg.mode != AuthMode.OAUTH:
        return None
    assert cfg.oauth_client_id and cfg.oauth_client_secret and cfg.oauth_base_url
    return SnipeITOAuthProvider(
        snipeit_url=cfg.url,
        client_id=cfg.oauth_client_id,
        client_secret=cfg.oauth_client_secret,
        base_url=cfg.oauth_base_url,
        redirect_path=cfg.oauth_redirect_path,
        timeout_seconds=cfg.oauth_timeout_seconds,
        cache_ttl_seconds=cfg.oauth_cache_ttl_seconds,
    )


def _build_identity_middleware(cfg):
    """Construct the per-identity tool middleware in multi-identity mode, else ``None``.

    The middleware enforces each identity's tool allowlist and read-only flag,
    filters ``tools/list`` per identity, and writes the JSON audit line for
    every tool call.
    """
    if cfg is None or cfg.mode != AuthMode.MULTI_IDENTITY:
        return None
    registry = load_identity_registry()
    assert registry is not None, "MULTI_IDENTITY mode implies a loaded registry"
    from .http_auth import IdentityToolMiddleware  # noqa: PLC0415 — keep import local

    return IdentityToolMiddleware(registry)


_auth_config = _load_auth_config()
_auth_provider = _build_auth_provider(_auth_config)
_identity_middleware = _build_identity_middleware(_auth_config)

if _auth_provider is not None:
    logger.info("Snipe-IT OAuth provider configured (interactive login enabled)")
    mcp = FastMCP(name="Snipe-IT MCP Server", auth=_auth_provider)
elif _identity_middleware is not None:
    logger.info(
        "Multi-identity mode: %d identities, per-identity policy + audit logging active",
        len(_identity_middleware.registry),
    )
    mcp = FastMCP(name="Snipe-IT MCP Server", middleware=[_identity_middleware])
else:
    mcp = FastMCP(name="Snipe-IT MCP Server")

# Import tool modules so their @mcp.tool decorators run and register tools on `mcp`.
# Placed after `mcp` is defined so submodules can import it from this module.
from . import tools  # noqa: E402, F401

# ============================================================================
# Tool Whitelist Configuration
# ============================================================================
# FastMCP 3.x exposes no public synchronous tool registry, so the whitelist is
# implemented with the server's enable/disable visibility controls. Disabled
# tools stay registered but are hidden from clients — they no longer appear in
# ``list_tools`` and cannot be called — which matches the previous behavior of
# dropping them from the tool set, and is freely re-applicable (e.g. from tests).


def apply_tool_whitelist(allowed_csv: str | None = None) -> None:
    """Apply the ``SNIPEIT_ALLOWED_TOOLS`` whitelist to ``mcp``.

    Pass ``None`` (the default) to read the value from the environment; pass an
    empty string to clear any active whitelist and restore the full tool set.
    """
    if allowed_csv is None:
        allowed_csv = os.getenv("SNIPEIT_ALLOWED_TOOLS", "").strip()

    if allowed_csv:
        allowed = {t.strip() for t in allowed_csv.split(",") if t.strip()}
        # Enable only the whitelisted tools, disabling every other tool.
        mcp.enable(names=allowed, components={"tool"}, only=True)
        logger.info(
            f"Tool whitelist active: only {sorted(allowed)} enabled; "
            "all other tools disabled."
        )
    else:
        # Re-enable the full tool set.
        mcp.enable(components={"tool"})
        logger.info("All tools enabled (no whitelist configured)")


apply_tool_whitelist()
