"""Snipe-IT HTTP clients and shared configuration.

Tool modules access the credentials and clients defined here via
``from snipeit_mcp import client`` and call ``client.get_snipeit_client()`` /
``client.get_direct_api()``. The qualified-access pattern lets tests patch
``snipeit_mcp.client.get_snipeit_client`` / ``...get_direct_api`` once and have
the patch propagate to every tool module.
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

# Get Snipe-IT configuration from environment variables
SNIPEIT_URL = os.getenv("SNIPEIT_URL")
SNIPEIT_TOKEN = os.getenv("SNIPEIT_TOKEN")


def get_snipeit_client() -> SnipeIT:
    """Get or create a Snipe-IT client instance."""
    if not SNIPEIT_URL or not SNIPEIT_TOKEN:
        raise SnipeITException(
            "Snipe-IT credentials not configured. "
            "Please set SNIPEIT_URL and SNIPEIT_TOKEN environment variables."
        )
    return SnipeIT(url=SNIPEIT_URL, token=SNIPEIT_TOKEN)


class SnipeITDirectAPI:
    """Direct API client for endpoints not supported by the snipeit-python-api library."""

    def __init__(self):
        if not SNIPEIT_URL or not SNIPEIT_TOKEN:
            raise SnipeITException(
                "Snipe-IT credentials not configured. "
                "Please set SNIPEIT_URL and SNIPEIT_TOKEN environment variables."
            )
        self.base_url = SNIPEIT_URL.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {SNIPEIT_TOKEN}",
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
        return response.json()

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
