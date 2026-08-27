"""Snipe-IT HTTP clients and shared configuration.

Tool modules access the credentials and clients defined here via
``from snipeit_mcp import client`` and call ``client.get_snipeit_client()`` /
``client.get_direct_api()``. The qualified-access pattern lets tests patch
``snipeit_mcp.client.get_snipeit_client`` / ``...get_direct_api`` once and have
the patch propagate to every tool module.

The bearer credential used for each call is resolved per-request by
:func:`_resolve_token` in this order:

1. The authenticated user's OAuth token from the FastMCP request context
   (OAuth mode).
2. The current identity's ``snipeit_token`` from the ``current_identity``
   contextvar (multi-identity mode — the HTTP auth layer sets it per request).
3. The static ``SNIPEIT_TOKEN`` env var (API-key mode / headless use / tests).

``get_snipeit_client()`` / ``SnipeITDirectAPI.__init__`` create a fresh client
instance for every call, so the per-request resolution is the single source of
truth — there is no shared client state to invalidate.
"""

from __future__ import annotations

import os

import requests
from snipeit import SnipeIT
from snipeit.exceptions import (
    SnipeITAuthenticationError,
    SnipeITException,
    SnipeITNotFoundError,
    SnipeITValidationError,
)

from .identity import current_identity

def _resolve_url() -> str | None:
    """Return the configured Snipe-IT base URL, read fresh from the env each call.

    Reading per-call (rather than capturing at import time) means tests that
    patch ``os.environ`` after the module is imported still take effect.
    """
    return os.getenv("SNIPEIT_URL")


def _resolve_token() -> str | None:
    """Return the bearer credential to use for the current call.

    Resolution order:

    1. OAuth mode — the authenticated user's token from the FastMCP request
       context, when present.
    2. Multi-identity mode — the ``snipeit_token`` of the identity resolved
       from the request's ``Authorization: Bearer`` header. The HTTP auth
       layer stores it in the ``current_identity`` contextvar; FastMCP runs
       sync tool functions in anyio worker threads, and anyio copies the
       current context into those threads, so the value set for the request
       is visible here.
    3. API-key mode / tests — the static ``SNIPEIT_TOKEN`` env var.

    Returns ``None`` when nothing is available; callers raise
    :class:`SnipeITException` in that case.
    """
    try:
        from fastmcp.server.dependencies import get_access_token
    except ImportError:
        access = None
    else:
        # Returns None when there's no authenticated request context (stdio mode
        # without auth, or in tests) — it does not raise.
        access = get_access_token()
    if access is not None:
        return access.token

    identity = current_identity.get()
    if identity is not None:
        return identity.snipeit_token

    return os.getenv("SNIPEIT_TOKEN")


def _require_url_and_token() -> tuple[str, str]:
    url = _resolve_url()
    creds = _resolve_token()
    if not url or not creds:
        raise SnipeITException(
            "Snipe-IT credentials not configured. "
            "Please set SNIPEIT_URL and either SNIPEIT_TOKEN (API key mode) or "
            "the SNIPEIT_OAUTH_CLIENT_* env vars plus SNIPEIT_MCP_BASE_URL "
            "(OAuth mode)."
        )
    return url, creds


def get_snipeit_client() -> SnipeIT:
    """Get or create a Snipe-IT client instance for the current call."""
    url, creds = _require_url_and_token()
    return SnipeIT(url=url, token=creds)


class SnipeITDirectAPI:
    """Direct API client for endpoints not supported by the snipeit-python-api library."""

    def __init__(self):
        url, creds = _require_url_and_token()
        self.base_url = url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {creds}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make an API request and handle errors."""
        url = f"{self.base_url}/api/v1/{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)

        if response.status_code == 404:
            raise SnipeITNotFoundError(f"Resource not found: {endpoint}")
        if response.status_code == 401:
            raise SnipeITAuthenticationError("Authentication failed")
        if response.status_code == 422:
            error_data = response.json()
            raise SnipeITValidationError(str(error_data.get("messages", error_data)))

        response.raise_for_status()
        data = response.json()
        # Snipe-IT returns HTTP 200 with {"status": "error", "messages": ...}
        # for many failures (e.g. unknown sub-resource); surface those as
        # errors instead of letting callers report them as success.
        if isinstance(data, dict) and data.get("status") == "error":
            messages = data.get("messages") or "Unknown API error"
            raise SnipeITException(str(messages))
        return data

    def list(self, endpoint: str, limit: int = 50, offset: int = 0,
             search: str | None = None, sort: str | None = None,
             order: str | None = None) -> list[dict]:
        """List resources, returning only rows (back-compat wrapper)."""
        return self.list_page(endpoint, limit, offset, search, sort, order)[0]

    def list_page(self, endpoint: str, limit: int = 50, offset: int = 0,
                  search: str | None = None, sort: str | None = None,
                  order: str | None = None,
                  extra_params: dict | None = None) -> tuple[list[dict], int]:
        """List resources with pagination, returning ``(rows, total)``.

        ``total`` is the Snipe-IT-reported full count so callers can compute
        ``has_more``. Defaults sort=id, order=asc to ensure deterministic
        ordering across paginated requests.
        """
        params = {"limit": limit, "offset": offset,
                  "sort": sort or "id", "order": order or "asc"}
        if search:
            params["search"] = search
        if extra_params:
            params.update({k: v for k, v in extra_params.items() if v is not None})

        data = self._request("GET", endpoint, params=params)
        rows = data.get("rows", [])
        total = data.get("total", len(rows))
        return rows, total

    def get(self, endpoint: str, resource_id: int) -> dict:
        """Get a single resource by ID."""
        return self._request("GET", f"{endpoint}/{resource_id}")

    def create(self, endpoint: str, data: dict) -> dict:
        """Create a new resource."""
        return self._request("POST", endpoint, json=data)

    def update(self, endpoint: str, resource_id: int, data: dict) -> dict:
        """Update a resource."""
        return self._request("PATCH", f"{endpoint}/{resource_id}", json=data)

    def delete(self, endpoint: str, resource_id: int) -> dict:
        """Delete a resource."""
        return self._request("DELETE", f"{endpoint}/{resource_id}")


def get_direct_api() -> SnipeITDirectAPI:
    """Get a direct API client instance."""
    return SnipeITDirectAPI()


def pagination_meta(count: int, total: int, limit: int, offset: int) -> dict:
    """Build pagination metadata for list responses."""
    return {
        "count": count,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + count) < total,
        "total_pages": -(-total // limit) if limit > 0 else 1,
        "current_page": (offset // limit) + 1 if limit > 0 else 1,
    }


# Standard API fields accepted by Snipe-IT hardware PATCH/POST endpoints.
# Keep in sync with Snipe-IT API: https://snipe-it.readme.io/reference/hardware
HARDWARE_STANDARD_FIELDS = {
    "name", "asset_tag", "serial", "model_id", "status_id",
    "purchase_date", "purchase_cost", "order_number", "notes",
    "warranty_months", "location_id", "rtd_location_id",
    "supplier_id", "company_id", "requestable", "archived",
    "asset_eol_date", "eol_explicit", "byod",
    "assigned_to", "image", "expected_checkin",
    "next_audit_date", "last_audit_date",
}
