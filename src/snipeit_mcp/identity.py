"""Multi-identity registry: per-user bearer tokens mapped to Snipe-IT PATs.

In multi-identity mode a single container serves many people. Each caller
authenticates to the MCP server with a personal bearer token (``mcp_token``);
this module maps that token to the caller's Snipe-IT personal access token
(``snipeit_token``) so every outgoing API call runs under the right identity.

Identities are configured in one of two ways:

* ``SNIPEIT_IDENTITY_<KEY>_*`` environment variables, discovered by scanning
  :data:`os.environ`:

  - ``SNIPEIT_IDENTITY_<KEY>_MCP_TOKEN`` (required, min 32 chars, unique)
  - ``SNIPEIT_IDENTITY_<KEY>_SNIPEIT_TOKEN`` (required)
  - ``SNIPEIT_IDENTITY_<KEY>_DISPLAY_NAME`` (optional)
  - ``SNIPEIT_IDENTITY_<KEY>_ALLOWED_TOOLS`` (optional CSV; restricts tools)
  - ``SNIPEIT_IDENTITY_<KEY>_READ_ONLY`` (optional bool; blocks write actions)

  ``<KEY>`` matches ``[A-Z0-9_]+`` and is the identity ID (``STAAT``,
  ``BAUDER``, ...). This is the default path for Portainer, where stack
  variables are the only configuration knob.

* ``SNIPEIT_IDENTITIES_FILE`` pointing at a JSON file containing a list of
  identity objects with the same fields (plus an explicit ``key``). When this
  variable is set, the file wins and the ``SNIPEIT_IDENTITY_*`` environment
  variables are ignored — intended for secret-mount based environments.

The identity resolved for the current request is carried in the
:data:`current_identity` contextvar, set by the HTTP auth layer before tool
execution. FastMCP runs sync tool functions in anyio worker threads, and anyio
copies the current context into those threads — which is why a ContextVar
(rather than ``threading.local``) is the correct carrier, and why concurrent
requests cannot leak identities into each other.

Security: tokens are compared with :func:`hmac.compare_digest`, and log output
contains identity keys — never token values or parts of them.
"""

from __future__ import annotations

import contextvars
import hmac
import json
import logging
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .config import ConfigError

logger = logging.getLogger(__name__)

ENV_PREFIX = "SNIPEIT_IDENTITY_"
ENV_VAR_FILE = "SNIPEIT_IDENTITIES_FILE"
MIN_MCP_TOKEN_LENGTH = 32

# SNIPEIT_IDENTITY_<KEY>_<FIELD> with KEY in [A-Z0-9_]+ and a fixed field name.
_ENV_VAR_RE = re.compile(
    r"^SNIPEIT_IDENTITY_(?P<key>[A-Z0-9_]+)_"
    r"(?P<field>MCP_TOKEN|SNIPEIT_TOKEN|DISPLAY_NAME|ALLOWED_TOOLS|READ_ONLY)$"
)
_FILE_KEY_RE = re.compile(r"^[A-Z0-9_]+$")

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class Identity:
    """One person: an MCP bearer token mapped to a Snipe-IT personal access token."""

    key: str
    mcp_token: str
    snipeit_token: str
    display_name: str | None = None
    allowed_tools: frozenset[str] | None = None  # None = no restriction
    read_only: bool = False

    @property
    def log_name(self) -> str:
        """Human-readable name for log lines (never a token)."""
        return self.display_name or self.key


# The identity resolved for the current request (set by the HTTP auth layer).
# ContextVar — not threading.local — because FastMCP runs sync tools in anyio
# worker threads and anyio copies the current context into those threads.
current_identity: contextvars.ContextVar[Identity | None] = contextvars.ContextVar(
    "snipeit_current_identity", default=None
)


@dataclass(frozen=True)
class IdentityRegistry:
    """Immutable set of identities with constant-time token lookup."""

    identities: tuple[Identity, ...]

    def __len__(self) -> int:
        return len(self.identities)

    @property
    def keys(self) -> list[str]:
        return [ident.key for ident in self.identities]

    def lookup(self, token: str | None) -> Identity | None:
        """Return the identity whose ``mcp_token`` matches ``token``, else ``None``.

        Uses :func:`hmac.compare_digest` so the comparison time does not depend
        on how much of the candidate token matches (no early exit on the first
        differing character).
        """
        if not token:
            return None
        candidate = token.encode("utf-8")
        for identity in self.identities:
            if hmac.compare_digest(candidate, identity.mcp_token.encode("utf-8")):
                return identity
        return None


def _parse_bool(raw: str | None, key: str, field: str) -> bool:
    if raw is None:
        return False
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ConfigError(
        f"Identity {key}: {field} must be a boolean (true/false, 1/0, yes/no, on/off), got: {raw!r}"
    )


def _parse_allowed_tools(raw: str | Sequence[str] | None, key: str) -> frozenset[str] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        items = raw.split(",")
    else:
        items = list(raw)
    names = {item.strip() for item in items if isinstance(item, str) and item.strip()}
    if not names:
        return None
    return frozenset(names)


def _build_identity(
    key: str,
    *,
    mcp_token: str | None,
    snipeit_token: str | None,
    display_name: str | None = None,
    allowed_tools: str | Sequence[str] | None = None,
    read_only: str | bool | None = None,
) -> Identity:
    if not mcp_token or not mcp_token.strip():
        raise ConfigError(f"Identity {key}: mcp_token is required")
    if not snipeit_token or not snipeit_token.strip():
        raise ConfigError(f"Identity {key}: snipeit_token is required")
    if isinstance(read_only, str):
        read_only = _parse_bool(read_only, key, "READ_ONLY")
    elif read_only is None:
        read_only = False
    return Identity(
        key=key,
        mcp_token=mcp_token.strip(),
        snipeit_token=snipeit_token.strip(),
        display_name=(display_name or None),
        allowed_tools=_parse_allowed_tools(allowed_tools, key),
        read_only=bool(read_only),
    )


def _parse_env(env: Mapping[str, str]) -> list[Identity]:
    """Parse ``SNIPEIT_IDENTITY_<KEY>_*`` variables from ``env``."""
    per_key: dict[str, dict[str, str]] = {}
    for name, value in env.items():
        match = _ENV_VAR_RE.match(name)
        if not match:
            continue
        per_key.setdefault(match.group("key"), {})[match.group("field")] = value

    identities = [
        _build_identity(
            key,
            mcp_token=fields.get("MCP_TOKEN"),
            snipeit_token=fields.get("SNIPEIT_TOKEN"),
            display_name=fields.get("DISPLAY_NAME"),
            allowed_tools=fields.get("ALLOWED_TOOLS"),
            read_only=fields.get("READ_ONLY"),
        )
        for key, fields in sorted(per_key.items())
    ]
    return identities


def _parse_file(path: str) -> list[Identity]:
    """Parse the JSON identities file referenced by ``SNIPEIT_IDENTITIES_FILE``."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError as exc:
        raise ConfigError(f"{ENV_VAR_FILE} points to an unreadable file ({path}): {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{ENV_VAR_FILE} is not valid JSON ({path}): {exc}") from exc

    if not isinstance(data, list):
        raise ConfigError(f"{ENV_VAR_FILE} must contain a JSON list of identity objects")

    identities = []
    for index, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise ConfigError(f"{ENV_VAR_FILE}: entry {index} must be an object")
        key = entry.get("key")
        if not isinstance(key, str) or not _FILE_KEY_RE.match(key):
            raise ConfigError(
                f"{ENV_VAR_FILE}: entry {index} has a missing or invalid 'key' "
                "(must match [A-Z0-9_]+)"
            )
        read_only = entry.get("read_only")
        if read_only is not None and not isinstance(read_only, bool):
            raise ConfigError(f"{ENV_VAR_FILE}: entry {key}: 'read_only' must be a boolean")
        identities.append(
            _build_identity(
                key,
                mcp_token=entry.get("mcp_token"),
                snipeit_token=entry.get("snipeit_token"),
                display_name=entry.get("display_name"),
                allowed_tools=entry.get("allowed_tools"),
                read_only=read_only,
            )
        )
    return identities


def _validate(identities: Sequence[Identity]) -> None:
    """Reject configurations that would break attribution or be an obvious error."""
    seen_tokens: dict[str, str] = {}
    for identity in identities:
        if len(identity.mcp_token) < MIN_MCP_TOKEN_LENGTH:
            raise ConfigError(
                f"Identity {identity.key}: mcp_token must be at least "
                f"{MIN_MCP_TOKEN_LENGTH} characters (got {len(identity.mcp_token)}). "
                "Suggested generation: openssl rand -hex 32"
            )
        if identity.mcp_token == identity.snipeit_token:
            raise ConfigError(
                f"Identity {identity.key}: mcp_token and snipeit_token must differ "
                "(the MCP token authenticates to this server, the Snipe-IT token "
                "authenticates to Snipe-IT)"
            )
        holder = seen_tokens.get(identity.mcp_token)
        if holder is not None:
            raise ConfigError(
                f"mcp_token is shared by identities '{holder}' and '{identity.key}' — "
                "each identity needs a unique mcp_token"
            )
        seen_tokens[identity.mcp_token] = identity.key


def load_identity_registry(env: Mapping[str, str] | None = None) -> IdentityRegistry | None:
    """Load and validate the identity registry, or return ``None`` if unconfigured.

    When ``SNIPEIT_IDENTITIES_FILE`` is set the file wins and any
    ``SNIPEIT_IDENTITY_*`` environment variables are ignored (logged once).
    Raises :class:`~snipeit_mcp.config.ConfigError` on malformed configuration —
    callers in the startup path translate that into a process exit.
    """
    env = os.environ if env is None else env
    file_path = (env.get(ENV_VAR_FILE) or "").strip()
    env_identities = _parse_env(env)

    if file_path:
        identities = _parse_file(file_path)
        if env_identities:
            logger.info(
                "%s is set — ignoring %d SNIPEIT_IDENTITY_* environment identities",
                ENV_VAR_FILE,
                len(env_identities),
            )
    else:
        identities = env_identities

    if not identities:
        return None

    _validate(identities)
    registry = IdentityRegistry(identities=tuple(identities))
    logger.info(
        "Loaded %d identity(ies) from %s: %s",
        len(registry),
        f"file {file_path}" if file_path else "environment",
        ", ".join(registry.keys),
    )
    return registry