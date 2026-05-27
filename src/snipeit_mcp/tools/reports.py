"""Snipe-IT reporting tools: activity reports, status summary, audit tracking."""

import logging
from typing import Annotated, Any, Literal

from pydantic import Field
from snipeit.exceptions import (
    SnipeITAuthenticationError,
    SnipeITException,
    SnipeITNotFoundError,
    SnipeITValidationError,
)

from .. import client as _client
from ..mcp_server import mcp

logger = logging.getLogger(__name__)


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
def activity_reports(
    action: Annotated[
        Literal["list", "item_activity"],
        "The action to perform"
    ],
    limit: Annotated[int, "Number of results to return"] = 50,
    offset: Annotated[int, "Number of results to skip"] = 0,
    search: Annotated[str | None, "Search query"] = None,
    target_type: Annotated[str | None, "Filter by target type (e.g., 'asset', 'license', 'user')"] = None,
    target_id: Annotated[int | None, "Filter by target ID"] = None,
    action_type: Annotated[str | None, "Filter by action type (e.g., 'checkout', 'checkin', 'update')"] = None,
    item_type: Annotated[str | None, "Item type for item_activity (e.g., 'asset', 'license', 'accessory')"] = None,
    item_id: Annotated[int | None, "Item ID for item_activity"] = None,
) -> dict[str, Any]:
    """Query Snipe-IT activity logs and reports.

    Provides access to the activity log which tracks all actions performed
    in Snipe-IT including checkouts, checkins, updates, and more.

    Actions:
    - list: List activity records with optional filtering
    - item_activity: Get activity for a specific item (requires item_type and item_id)

    Returns:
        dict: Activity records matching the query
    """
    try:
        api = _client.get_direct_api()

        if action == "list":
            params = {"limit": limit, "offset": offset}
            if search:
                params["search"] = search
            if target_type:
                params["target_type"] = target_type
            if target_id:
                params["target_id"] = target_id
            if action_type:
                params["action_type"] = action_type

            result = api._request("GET", "reports/activity", params=params)
            activities = result.get("rows", [])
            _total = result.get("total", len(activities))

            activities_list = [
                {
                    "id": act.get("id"),
                    "action_type": act.get("action_type"),
                    "target_type": act.get("target_type"),
                    "target": act.get("target"),
                    "item": act.get("item"),
                    "admin": act.get("admin"),
                    "created_at": act.get("created_at"),
                    "note": act.get("note"),
                }
                for act in activities
            ]

            return {
                "success": True,
                "action": "list",
                **_client.pagination_meta(len(activities_list), _total, limit, offset),
                "activities": activities_list,
            }

        elif action == "item_activity":
            if not item_type or not item_id:
                return {"success": False, "error": "item_type and item_id are required for item_activity action"}

            # Map item types to their API endpoints
            type_map = {
                "asset": "hardware",
                "hardware": "hardware",
                "license": "licenses",
                "accessory": "accessories",
                "consumable": "consumables",
                "component": "components",
                "user": "users",
            }

            endpoint_type = type_map.get(item_type.lower())
            if not endpoint_type:
                return {"success": False, "error": f"Invalid item_type: {item_type}. Valid types: {list(type_map.keys())}"}

            params = {"limit": limit, "offset": offset}
            result = api._request("GET", f"reports/activity", params={
                **params,
                "item_type": endpoint_type,
                "item_id": item_id,
            })
            activities = result.get("rows", [])

            return {
                "success": True,
                "action": "item_activity",
                "item_type": item_type,
                "item_id": item_id,
                "count": len(activities),
                "activities": activities
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Resource not found: {e}")
        return {"success": False, "error": f"Not found: {str(e)}"}
    except SnipeITAuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        return {"success": False, "error": f"Authentication failed: {str(e)}"}
    except SnipeITException as e:
        logger.error(f"Snipe-IT error: {e}")
        return {"success": False, "error": f"Snipe-IT error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error in activity_reports: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}




@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
def status_summary() -> dict[str, Any]:
    """Get asset counts grouped by status label.

    Returns a summary of how many assets are in each status,
    useful for dashboard displays and reporting.

    Returns:
        dict: Asset counts by status label
    """
    try:
        api = _client.get_direct_api()
        result = api._request("GET", "statuslabels/assets")

        return {
            "success": True,
            "summary": result
        }

    except SnipeITNotFoundError as e:
        logger.error(f"Resource not found: {e}")
        return {"success": False, "error": f"Not found: {str(e)}"}
    except SnipeITAuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        return {"success": False, "error": f"Authentication failed: {str(e)}"}
    except SnipeITException as e:
        logger.error(f"Snipe-IT error: {e}")
        return {"success": False, "error": f"Snipe-IT error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error in status_summary: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}




@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
def audit_tracking(
    action: Annotated[
        Literal["due", "overdue", "summary"],
        "The audit tracking action"
    ],
    limit: Annotated[int, "Number of results to return"] = 50,
    offset: Annotated[int, "Number of results to skip"] = 0,
) -> dict[str, Any]:
    """Track asset audit status for compliance.

    Snipe-IT tracks when assets were last audited and calculates
    when they're due for re-audit based on the configured threshold.

    Operations:
    - due: Assets approaching their audit date (within warning threshold)
    - overdue: Assets that have passed their audit date
    - summary: Combined counts of due and overdue assets

    The audit threshold is configured in Admin Settings → Notifications
    and determines the lookahead window for "due" assets.

    Returns:
        dict: Audit status with asset details
    """
    try:
        api = _client.get_direct_api()

        if action == "due":
            params = {"limit": limit, "offset": offset}
            result = api._request("GET", "hardware/audit/due", params=params)
            assets = result.get("rows", [])

            return {
                "success": True,
                "action": "due",
                **_client.pagination_meta(len(assets), result.get("total", len(assets)), limit, offset),
                "assets": assets,
            }

        elif action == "overdue":
            params = {"limit": limit, "offset": offset}
            result = api._request("GET", "hardware/audit/overdue", params=params)
            assets = result.get("rows", [])

            return {
                "success": True,
                "action": "overdue",
                **_client.pagination_meta(len(assets), result.get("total", len(assets)), limit, offset),
                "assets": assets,
            }

        elif action == "summary":
            # Get both due and overdue counts
            due_result = api._request("GET", "hardware/audit/due", params={"limit": 10})
            overdue_result = api._request("GET", "hardware/audit/overdue", params={"limit": 10})

            due_assets = due_result.get("rows", [])
            overdue_assets = overdue_result.get("rows", [])

            return {
                "success": True,
                "action": "summary",
                "due_count": due_result.get("total", len(due_assets)),
                "overdue_count": overdue_result.get("total", len(overdue_assets)),
                "due_assets": due_assets,
                "overdue_assets": overdue_assets
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Resource not found: {e}")
        return {"success": False, "error": f"Not found: {str(e)}"}
    except SnipeITAuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        return {"success": False, "error": f"Authentication failed: {str(e)}"}
    except SnipeITException as e:
        logger.error(f"Snipe-IT error: {e}")
        return {"success": False, "error": f"Snipe-IT error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error in audit_tracking: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


