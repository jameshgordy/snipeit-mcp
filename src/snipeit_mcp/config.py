"""Configuration objects driven by environment variables.

Two independent concerns:

* :class:`TransportConfig` — how the MCP server is reached (stdio vs HTTP).
  Modelled after the corresponding object in Zammad-MCP, using the same generic
  ``MCP_TRANSPORT`` / ``MCP_HOST`` / ``MCP_PORT`` variables.
* :class:`SnipeITAuthConfig` — how the server authenticates to Snipe-IT. This
  is the mode-detection logic: OAuth provider config (interactive) takes
  precedence over the static personal-access-token fallback.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Port validation constants
MIN_PORT = 1
MAX_PORT = 65535


class ConfigError(ValueError):
    """Raised when configuration is missing or inconsistent."""


def _env_int(name: str, default: int) -> int:
    """Read an integer env var, falling back to ``default`` when unset/blank."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a valid integer, got: {raw}") from exc


class TransportType(str, Enum):
    """Supported MCP transport types."""

    STDIO = "stdio"
    HTTP = "http"


class AuthMode(str, Enum):
    """How tools authenticate to the upstream Snipe-IT instance."""

    OAUTH = "oauth"
    API_KEY = "api_key"
    MULTI_IDENTITY = "multi_identity"


@dataclass
class TransportConfig:
    """Configuration for the MCP transport layer."""

    transport: TransportType = TransportType.STDIO
    host: str | None = None
    port: int | None = None

    @classmethod
    def from_env(cls) -> TransportConfig:
        """Read transport configuration from MCP_TRANSPORT / MCP_HOST / MCP_PORT."""
        transport_str = os.getenv("MCP_TRANSPORT", "stdio").lower()
        try:
            transport = TransportType(transport_str)
        except ValueError as exc:
            raise ConfigError(
                f"Invalid MCP_TRANSPORT '{transport_str}'. "
                f"Must be one of: {', '.join(t.value for t in TransportType)}"
            ) from exc

        host = os.getenv("MCP_HOST")
        port_str = os.getenv("MCP_PORT")
        port: int | None = None
        if port_str:
            try:
                port = int(port_str)
            except ValueError as exc:
                raise ConfigError(f"MCP_PORT must be a valid integer, got: {port_str}") from exc

        return cls(transport=transport, host=host, port=port)

    def validate(self) -> None:
        """Apply defaults and raise on invalid combinations."""
        if self.transport == TransportType.HTTP:
            if self.port is None:
                raise ConfigError("HTTP transport requires MCP_PORT to be set")
            if not MIN_PORT <= self.port <= MAX_PORT:
                raise ConfigError(
                    f"MCP_PORT must be between {MIN_PORT} and {MAX_PORT}, got: {self.port}"
                )
            if self.host is None:
                self.host = "127.0.0.1"


@dataclass
class SnipeITAuthConfig:
    """How the MCP server authenticates to the upstream Snipe-IT instance.

    Three mutually-exclusive modes:

    * **OAuth** — both ``SNIPEIT_OAUTH_CLIENT_ID`` and ``SNIPEIT_OAUTH_CLIENT_SECRET``
      are set. The MCP server runs an OAuth proxy that hands users off to Snipe-IT's
      Laravel Passport for interactive login; each request to a tool uses the
      authenticated user's own access token. Requires HTTP transport.
    * **Multi-identity** — at least one ``SNIPEIT_IDENTITY_<KEY>_*`` identity is
      configured (or ``SNIPEIT_IDENTITIES_FILE`` is set). One container serves many
      people: each request carries a personal bearer token that selects which
      Snipe-IT personal access token the tool calls use. Requires HTTP transport.
      See :mod:`snipeit_mcp.identity`.
    * **API key** — ``SNIPEIT_TOKEN`` is set (and no OAuth vars / identities). The
      MCP server uses a single static personal-access token for every request.
      Works with both stdio and HTTP transports. Preserves upstream behaviour.
    """

    mode: AuthMode
    url: str
    # API-key mode
    token: str | None = None
    # OAuth mode
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    oauth_base_url: str | None = None
    oauth_redirect_path: str = "/auth/callback"
    # Upstream /users/me validation tuning (OAuth mode only)
    oauth_timeout_seconds: int = 10
    oauth_cache_ttl_seconds: int = 60

    @classmethod
    def from_env(cls) -> SnipeITAuthConfig:
        """Build auth config from SNIPEIT_* environment variables."""
        url = os.getenv("SNIPEIT_URL")
        if not url:
            raise ConfigError("SNIPEIT_URL is required")

        client_id = os.getenv("SNIPEIT_OAUTH_CLIENT_ID")
        client_secret = os.getenv("SNIPEIT_OAUTH_CLIENT_SECRET")
        token = os.getenv("SNIPEIT_TOKEN")

        # Helpful misconfiguration hints
        if client_id and not client_secret:
            raise ConfigError(
                "SNIPEIT_OAUTH_CLIENT_ID is set but SNIPEIT_OAUTH_CLIENT_SECRET is missing"
            )
        if client_secret and not client_id:
            raise ConfigError(
                "SNIPEIT_OAUTH_CLIENT_SECRET is set but SNIPEIT_OAUTH_CLIENT_ID is missing"
            )

        if client_id and client_secret:
            # OAuth and multi-identity are mutually exclusive: both resolve the
            # upstream credential per request, and mixing them would be ambiguous.
            from .identity import load_identity_registry  # noqa: PLC0415 — avoid import cycle

            if load_identity_registry() is not None:
                raise ConfigError(
                    "OAuth mode (SNIPEIT_OAUTH_CLIENT_ID/SECRET) and multi-identity mode "
                    "(SNIPEIT_IDENTITY_* or SNIPEIT_IDENTITIES_FILE) are mutually "
                    "exclusive. Configure one or the other."
                )
            base_url = os.getenv("SNIPEIT_MCP_BASE_URL")
            if not base_url:
                raise ConfigError(
                    "OAuth mode requires SNIPEIT_MCP_BASE_URL — the public URL where "
                    "this MCP server is reachable (used to build the OAuth callback URL)"
                )
            return cls(
                mode=AuthMode.OAUTH,
                url=url,
                oauth_client_id=client_id,
                oauth_client_secret=client_secret,
                oauth_base_url=base_url,
                oauth_redirect_path=os.getenv("SNIPEIT_MCP_REDIRECT_PATH", "/auth/callback"),
                oauth_timeout_seconds=_env_int("SNIPEIT_OAUTH_TIMEOUT", 10),
                oauth_cache_ttl_seconds=_env_int("SNIPEIT_OAUTH_CACHE_TTL", 60),
            )

        # Multi-identity mode: at least one identity configured. Takes
        # precedence over a stray SNIPEIT_TOKEN (which would otherwise be the
        # single shared identity and silently override per-user attribution).
        from .identity import load_identity_registry  # noqa: PLC0415 — avoid import cycle

        registry = load_identity_registry()
        if registry is not None:
            if token:
                logger.warning(
                    "Multi-identity mode active; SNIPEIT_TOKEN is ignored "
                    "(%d identities configured)",
                    len(registry),
                )
            return cls(mode=AuthMode.MULTI_IDENTITY, url=url)

        if token:
            return cls(mode=AuthMode.API_KEY, url=url, token=token)

        raise ConfigError(
            "No Snipe-IT credentials configured. Set one of:\n"
            "  - SNIPEIT_OAUTH_CLIENT_ID + SNIPEIT_OAUTH_CLIENT_SECRET + SNIPEIT_MCP_BASE_URL "
            "(interactive OAuth),\n"
            "  - SNIPEIT_IDENTITY_<KEY>_MCP_TOKEN + SNIPEIT_IDENTITY_<KEY>_SNIPEIT_TOKEN per "
            "person (multi-identity, HTTP transport), or\n"
            "  - SNIPEIT_TOKEN (static personal-access token)"
        )

    def validate_with_transport(self, transport: TransportConfig) -> None:
        """Cross-validate auth config against the chosen transport."""
        if self.mode == AuthMode.OAUTH and transport.transport != TransportType.HTTP:
            raise ConfigError(
                "OAuth mode requires HTTP transport. "
                "Set MCP_TRANSPORT=http and MCP_PORT (the OAuth flow needs HTTP routes "
                "for /authorize and the callback)."
            )
        if self.mode == AuthMode.MULTI_IDENTITY and transport.transport != TransportType.HTTP:
            raise ConfigError(
                "Multi-identity mode requires HTTP transport. "
                "Set MCP_TRANSPORT=http and MCP_PORT — the identity is selected per "
                "request from the Authorization header, which stdio does not have."
            )
