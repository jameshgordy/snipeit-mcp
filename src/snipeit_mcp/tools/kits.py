"""Snipe-IT predefined kit tools (/kits): CRUD and kit content management."""

import logging
from typing import Annotated, Any, Literal

from snipeit.exceptions import (
    SnipeITAuthenticationError,
    SnipeITException,
    SnipeITNotFoundError,
    SnipeITValidationError,
)

from .. import client as _client
from ..mcp_server import mcp
from ..schemas import KitData

logger = logging.getLogger(__name__)

# Kit content endpoints are plural ("models"), but the attach payload uses the
# singular item key ("model"), per PredefinedKitsController in Snipe-IT.
_ITEM_KEYS = {
    "models": "model",
    "licenses": "license",
    "accessories": "accessory",
    "consumables": "consumable",
}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_kits(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete",
                "list_items", "add_item", "update_item", "remove_item"],
        "The action to perform on predefined kits"
    ],
    kit_id: Annotated[int | None, "Kit ID (required for all actions except create and list)"] = None,
    kit_data: Annotated[KitData | None, "Kit data (required for create, optional for update)"] = None,
    item_type: Annotated[
        Literal["models", "licenses", "accessories", "consumables"] | None,
        "Kit content type (required for list_items, add_item, update_item, remove_item)"
    ] = None,
    item_id: Annotated[int | None, "ID of the model/license/accessory/consumable (required for add_item, update_item, remove_item)"] = None,
    quantity: Annotated[int, "Quantity of the item in the kit (for add_item, update_item)"] = 1,
    limit: Annotated[int, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list action)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action): id, name, created_at, updated_at, created_by"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT predefined kits (bundles of models, licenses, accessories, consumables).

    Kit CRUD:
    - create: Create a kit (requires kit_data with name)
    - get / list / update / delete: Standard operations by kit_id

    Kit contents (requires kit_id and item_type):
    - list_items: List the kit's models/licenses/accessories/consumables
    - add_item: Attach an item to the kit (requires item_id; optional quantity)
    - update_item: Change an attached item's quantity (requires item_id)
    - remove_item: Detach an item from the kit (requires item_id)

    Note: checking out a kit to a user is only available in the Snipe-IT web UI;
    there is no kit-checkout API endpoint. To perform a kit checkout via MCP,
    list the kit's items and check each out individually.

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = _client.get_direct_api()

        if action == "create":
            if not kit_data or not kit_data.name:
                return {"success": False, "error": "kit_data with name is required for create action"}
            result = api.create("kits", {"name": kit_data.name})
            return {"success": True, "action": "create", "kit": result}

        elif action == "get":
            if not kit_id:
                return {"success": False, "error": "kit_id is required for get action"}
            kit = api.get("kits", kit_id)
            return {"success": True, "action": "get", "kit": kit}

        elif action == "list":
            kits, _total = api.list_page("kits", limit=limit, offset=offset,
                                         search=search, sort=sort, order=order)
            return {
                "success": True,
                "action": "list",
                **_client.pagination_meta(len(kits), _total, limit, offset),
                "kits": kits,
            }

        elif action == "update":
            if not kit_id:
                return {"success": False, "error": "kit_id is required for update action"}
            if not kit_data or not kit_data.name:
                return {"success": False, "error": "kit_data with name is required for update action"}
            result = api.update("kits", kit_id, {"name": kit_data.name})
            return {"success": True, "action": "update", "kit": result}

        elif action == "delete":
            if not kit_id:
                return {"success": False, "error": "kit_id is required for delete action"}
            api.delete("kits", kit_id)
            return {"success": True, "action": "delete", "kit_id": kit_id,
                    "message": f"Kit {kit_id} deleted successfully"}

        # Content actions below all need kit_id + item_type
        if not kit_id:
            return {"success": False, "error": f"kit_id is required for {action} action"}
        if not item_type:
            return {"success": False, "error": f"item_type is required for {action} action. Valid types: {list(_ITEM_KEYS.keys())}"}

        if action == "list_items":
            result = api._request("GET", f"kits/{kit_id}/{item_type}")
            rows = result.get("rows", []) if isinstance(result, dict) else result
            return {
                "success": True,
                "action": "list_items",
                "kit_id": kit_id,
                "item_type": item_type,
                "count": len(rows),
                "items": rows,
            }

        if not item_id:
            return {"success": False, "error": f"item_id is required for {action} action"}

        if action == "add_item":
            payload = {_ITEM_KEYS[item_type]: item_id, "quantity": quantity}
            result = api._request("POST", f"kits/{kit_id}/{item_type}", json=payload)
            return {"success": True, "action": "add_item", "kit_id": kit_id,
                    "item_type": item_type, "item_id": item_id, "quantity": quantity,
                    "result": result}

        elif action == "update_item":
            result = api._request("PUT", f"kits/{kit_id}/{item_type}/{item_id}",
                                  json={"quantity": quantity})
            return {"success": True, "action": "update_item", "kit_id": kit_id,
                    "item_type": item_type, "item_id": item_id, "quantity": quantity,
                    "result": result}

        elif action == "remove_item":
            result = api._request("DELETE", f"kits/{kit_id}/{item_type}/{item_id}")
            return {"success": True, "action": "remove_item", "kit_id": kit_id,
                    "item_type": item_type, "item_id": item_id, "result": result}

    except SnipeITNotFoundError as e:
        logger.error(f"Kit not found: {e}")
        return {"success": False, "error": f"Not found: {str(e)}"}
    except SnipeITAuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        return {"success": False, "error": f"Authentication failed: {str(e)}"}
    except SnipeITValidationError as e:
        logger.error(f"Validation error: {e}")
        return {"success": False, "error": f"Validation error: {str(e)}"}
    except SnipeITException as e:
        logger.error(f"Snipe-IT error: {e}")
        return {"success": False, "error": f"Snipe-IT error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error in manage_kits: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}
