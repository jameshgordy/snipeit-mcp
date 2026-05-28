"""Snipe-IT inventory tools: consumables, components, accessories."""

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
from ..schemas import ConsumableData, ComponentData, ComponentCheckout, AccessoryData, AccessoryCheckout

logger = logging.getLogger(__name__)


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_consumables(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete"],
        "The action to perform on consumables"
    ],
    consumable_id: Annotated[int | None, "Consumable ID (required for get, update, delete)"] = None,
    consumable_data: Annotated[ConsumableData | None, "Consumable data (required for create, optional for update)"] = None,
    limit: Annotated[int, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list action)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action)"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT consumables with CRUD operations.
    
    This tool handles all basic consumable operations:
    - create: Create a new consumable (requires consumable_data with name, qty, and category_id)
    - get: Retrieve a single consumable by ID
    - list: List consumables with optional pagination and filtering
    - update: Update an existing consumable (requires consumable_id and consumable_data)
    - delete: Delete a consumable (requires consumable_id)
    
    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        client = _client.get_snipeit_client()
        
        with client:
            if action == "create":
                if not consumable_data:
                    return {"success": False, "error": "consumable_data is required for create action"}
                
                if not consumable_data.name or consumable_data.qty is None or not consumable_data.category_id:
                    return {
                        "success": False,
                        "error": "name, qty, and category_id are required to create a consumable"
                    }
                
                # Build creation payload
                create_kwargs = {k: v for k, v in consumable_data.model_dump().items() if v is not None}
                consumable = client.consumables.create(**create_kwargs)
                
                return {
                    "success": True,
                    "action": "create",
                    "consumable": {
                        "id": consumable.id,
                        "name": getattr(consumable, "name", None),
                        "qty": getattr(consumable, "qty", None),
                    }
                }
            
            elif action == "get":
                if not consumable_id:
                    return {"success": False, "error": "consumable_id is required for get action"}
                
                consumable = client.consumables.get(consumable_id)
                
                # Extract consumable data
                consumable_dict = {
                    "id": consumable.id,
                    "name": getattr(consumable, "name", None),
                    "qty": getattr(consumable, "qty", None),
                    "category": getattr(consumable, "category", None),
                    "company": getattr(consumable, "company", None),
                    "location": getattr(consumable, "location", None),
                    "manufacturer": getattr(consumable, "manufacturer", None),
                    "model_number": getattr(consumable, "model_number", None),
                    "item_no": getattr(consumable, "item_no", None),
                    "order_number": getattr(consumable, "order_number", None),
                    "purchase_date": getattr(consumable, "purchase_date", None),
                    "purchase_cost": getattr(consumable, "purchase_cost", None),
                    "min_amt": getattr(consumable, "min_amt", None),
                    "remaining": getattr(consumable, "remaining", None),
                }
                
                return {
                    "success": True,
                    "action": "get",
                    "consumable": consumable_dict
                }
            
            elif action == "list":
                params = {"limit": limit, "offset": offset}
                if search:
                    params["search"] = search
                # Default sort=id, order=asc for stable offset-based pagination
                params["sort"] = sort or "id"
                params["order"] = order or "asc"
                
                api = _client.get_direct_api()
                consumables, _total = api.list_page("consumables", **params)

                consumables_list = [
                    {
                        "id": c.get("id"),
                        "name": c.get("name"),
                        "qty": c.get("qty"),
                        "remaining": c.get("remaining"),
                    }
                    for c in consumables
                ]

                return {
                    "success": True,
                    "action": "list",
                    **_client.pagination_meta(len(consumables_list), _total, limit, offset),
                    "consumables": consumables_list,
                }
            
            elif action == "update":
                if not consumable_id:
                    return {"success": False, "error": "consumable_id is required for update action"}
                if not consumable_data:
                    return {"success": False, "error": "consumable_data is required for update action"}
                
                # Build update payload (only include non-None values)
                update_kwargs = {k: v for k, v in consumable_data.model_dump().items() if v is not None}
                
                consumable = client.consumables.patch(consumable_id, **update_kwargs)
                
                return {
                    "success": True,
                    "action": "update",
                    "consumable": {
                        "id": consumable.id,
                        "name": getattr(consumable, "name", None),
                        "qty": getattr(consumable, "qty", None),
                    }
                }
            
            elif action == "delete":
                if not consumable_id:
                    return {"success": False, "error": "consumable_id is required for delete action"}
                
                client.consumables.delete(consumable_id)
                
                return {
                    "success": True,
                    "action": "delete",
                    "consumable_id": consumable_id,
                    "message": "Consumable deleted successfully"
                }
    
    except SnipeITNotFoundError as e:
        logger.error(f"Consumable not found: {e}")
        return {"success": False, "error": f"Consumable not found: {str(e)}"}
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
        logger.error(f"Unexpected error in manage_consumables: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}




@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_accessories(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete"],
        "The action to perform on accessories"
    ],
    accessory_id: Annotated[int | None, "Accessory ID (required for get, update, delete)"] = None,
    accessory_data: Annotated[AccessoryData | None, "Accessory data (required for create, optional for update)"] = None,
    limit: Annotated[int, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list action)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action)"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT accessories with CRUD operations.

    Accessories are quantity-based items (cables, adapters, peripherals) that can be
    checked out to users. Unlike assets, accessories are tracked by quantity rather
    than individually.

    Operations:
    - create: Create a new accessory (requires accessory_data with name, qty, and category_id)
    - get: Retrieve a single accessory by ID
    - list: List accessories with optional pagination and filtering
    - update: Update an existing accessory (requires accessory_id and accessory_data)
    - delete: Delete an accessory (requires accessory_id)

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = _client.get_direct_api()

        if action == "create":
            if not accessory_data:
                return {"success": False, "error": "accessory_data is required for create action"}

            if not accessory_data.name or accessory_data.qty is None or not accessory_data.category_id:
                return {
                    "success": False,
                    "error": "name, qty, and category_id are required to create an accessory"
                }

            create_data = {k: v for k, v in accessory_data.model_dump().items() if v is not None}
            result = api.create("accessories", create_data)

            return {
                "success": True,
                "action": "create",
                "accessory": {
                    "id": result.get("payload", result).get("id"),
                    "name": result.get("payload", result).get("name"),
                    "qty": result.get("payload", result).get("qty"),
                }
            }

        elif action == "get":
            if not accessory_id:
                return {"success": False, "error": "accessory_id is required for get action"}

            accessory = api.get("accessories", accessory_id)

            return {
                "success": True,
                "action": "get",
                "accessory": {
                    "id": accessory.get("id"),
                    "name": accessory.get("name"),
                    "qty": accessory.get("qty"),
                    "remaining_qty": accessory.get("remaining_qty"),
                    "category": accessory.get("category"),
                    "company": accessory.get("company"),
                    "location": accessory.get("location"),
                    "manufacturer": accessory.get("manufacturer"),
                    "supplier": accessory.get("supplier"),
                    "model_number": accessory.get("model_number"),
                    "order_number": accessory.get("order_number"),
                    "purchase_cost": accessory.get("purchase_cost"),
                    "purchase_date": accessory.get("purchase_date"),
                    "min_amt": accessory.get("min_amt"),
                    "notes": accessory.get("notes"),
                }
            }

        elif action == "list":
            accessories, _total = api.list_page("accessories", limit=limit, offset=offset,
                                                search=search, sort=sort, order=order)

            accessories_list = [
                {
                    "id": acc.get("id"),
                    "name": acc.get("name"),
                    "qty": acc.get("qty"),
                    "remaining_qty": acc.get("remaining_qty"),
                    "category": acc.get("category", {}).get("name") if isinstance(acc.get("category"), dict) else None,
                    "model_number": acc.get("model_number"),
                }
                for acc in accessories
            ]

            return {
                "success": True,
                "action": "list",
                **_client.pagination_meta(len(accessories_list), _total, limit, offset),
                "accessories": accessories_list,
            }

        elif action == "update":
            if not accessory_id:
                return {"success": False, "error": "accessory_id is required for update action"}
            if not accessory_data:
                return {"success": False, "error": "accessory_data is required for update action"}

            update_data = {k: v for k, v in accessory_data.model_dump().items() if v is not None}
            result = api.update("accessories", accessory_id, update_data)

            return {
                "success": True,
                "action": "update",
                "accessory": {
                    "id": result.get("payload", result).get("id"),
                    "name": result.get("payload", result).get("name"),
                }
            }

        elif action == "delete":
            if not accessory_id:
                return {"success": False, "error": "accessory_id is required for delete action"}

            api.delete("accessories", accessory_id)

            return {
                "success": True,
                "action": "delete",
                "accessory_id": accessory_id,
                "message": "Accessory deleted successfully"
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Accessory not found: {e}")
        return {"success": False, "error": f"Accessory not found: {str(e)}"}
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
        logger.error(f"Unexpected error in manage_accessories: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    }
)
def accessory_operations(
    action: Annotated[
        Literal["checkout", "checkin", "list_checkouts"],
        "The operation to perform on the accessory"
    ],
    accessory_id: Annotated[int, "Accessory ID"],
    checkout_data: Annotated[AccessoryCheckout | None, "Checkout data (required for checkout action)"] = None,
    checkout_id: Annotated[int | None, "Checkout ID (required for checkin action)"] = None,
) -> dict[str, Any]:
    """Perform checkout/checkin operations on accessories.

    Accessories can be checked out to a user, asset, or location. Each
    checkout decrements the available quantity, and checkin increments it
    back.

    Operations:
    - checkout: Checkout an accessory to a user/asset/location (requires
      checkout_data with checkout_to_type and assigned_to_id)
    - checkin: Checkin an accessory (requires checkout_id from the checkout record)
    - list_checkouts: List all users who have this accessory checked out

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = _client.get_direct_api()

        if action == "checkout":
            if not checkout_data:
                return {"success": False, "error": "checkout_data is required for checkout action"}

            target_field = {
                "user": "assigned_user",
                "asset": "assigned_asset",
                "location": "assigned_location",
            }[checkout_data.checkout_to_type]
            checkout_payload: dict[str, Any] = {target_field: checkout_data.assigned_to_id}
            if checkout_data.checkout_qty is not None:
                checkout_payload["checkout_qty"] = checkout_data.checkout_qty
            if checkout_data.note is not None:
                checkout_payload["note"] = checkout_data.note

            result = api._request("POST", f"accessories/{accessory_id}/checkout", json=checkout_payload)

            return {
                "success": True,
                "action": "checkout",
                "accessory_id": accessory_id,
                "message": f"Accessory checked out to {checkout_data.checkout_to_type} {checkout_data.assigned_to_id}",
                "result": result
            }

        elif action == "checkin":
            if not checkout_id:
                return {"success": False, "error": "checkout_id is required for checkin action"}

            # Snipe-IT uses the checkout_id in the request body
            result = api._request("POST", f"accessories/{accessory_id}/checkin", json={"accessory_user_id": checkout_id})

            return {
                "success": True,
                "action": "checkin",
                "accessory_id": accessory_id,
                "checkout_id": checkout_id,
                "message": "Accessory checked in successfully",
                "result": result
            }

        elif action == "list_checkouts":
            result = api._request("GET", f"accessories/{accessory_id}/checkedout")
            checkouts = result.get("rows", [])

            checkouts_list = [
                {
                    "id": co.get("id"),
                    "assigned_to": co.get("assigned_to"),
                    "checkout_at": co.get("created_at"),
                    "note": co.get("note"),
                }
                for co in checkouts
            ]

            return {
                "success": True,
                "action": "list_checkouts",
                "accessory_id": accessory_id,
                "count": len(checkouts_list),
                "checkouts": checkouts_list
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Accessory not found: {e}")
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
        logger.error(f"Unexpected error in accessory_operations: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}




@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_components(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete"],
        "The action to perform on components"
    ],
    component_id: Annotated[int | None, "Component ID (required for get, update, delete)"] = None,
    component_data: Annotated[ComponentData | None, "Component data (required for create, optional for update)"] = None,
    limit: Annotated[int, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list action)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action)"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT components with CRUD operations.

    Components are items that can be checked out to assets (not users).
    Examples: RAM, hard drives, CPUs, etc.

    Actions:
    - create: Create a new component (requires component_data with name, qty, category_id)
    - get: Retrieve a single component by ID
    - list: List components with optional pagination and filtering
    - update: Update an existing component
    - delete: Delete a component

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = _client.get_direct_api()

        if action == "create":
            if not component_data:
                return {"success": False, "error": "component_data is required for create action"}

            if not component_data.name or not component_data.qty or not component_data.category_id:
                return {
                    "success": False,
                    "error": "name, qty, and category_id are required to create a component"
                }

            create_payload = {k: v for k, v in component_data.model_dump().items() if v is not None}
            result = api.create("components", create_payload)

            return {
                "success": True,
                "action": "create",
                "component": result
            }

        elif action == "get":
            if not component_id:
                return {"success": False, "error": "component_id is required for get action"}

            result = api.get("components", component_id)

            return {
                "success": True,
                "action": "get",
                "component": result
            }

        elif action == "list":
            params = {"limit": limit, "offset": offset}
            if search:
                params["search"] = search
            params["sort"] = sort or "id"
            params["order"] = order or "asc"

            components, _total = api.list_page("components", **params)

            components_list = [
                {
                    "id": comp.get("id"),
                    "name": comp.get("name"),
                    "qty": comp.get("qty"),
                    "remaining": comp.get("remaining"),
                    "category": comp.get("category"),
                    "location": comp.get("location"),
                }
                for comp in components
            ]

            return {
                "success": True,
                "action": "list",
                **_client.pagination_meta(len(components_list), _total, limit, offset),
                "components": components_list,
            }

        elif action == "update":
            if not component_id:
                return {"success": False, "error": "component_id is required for update action"}
            if not component_data:
                return {"success": False, "error": "component_data is required for update action"}

            update_payload = {k: v for k, v in component_data.model_dump().items() if v is not None}
            result = api.update("components", component_id, update_payload)

            return {
                "success": True,
                "action": "update",
                "component_id": component_id,
                "result": result
            }

        elif action == "delete":
            if not component_id:
                return {"success": False, "error": "component_id is required for delete action"}

            result = api.delete("components", component_id)

            return {
                "success": True,
                "action": "delete",
                "component_id": component_id,
                "message": "Component deleted successfully"
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Component not found: {e}")
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
        logger.error(f"Unexpected error in manage_components: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    }
)
def component_operations(
    action: Annotated[
        Literal["checkout", "checkin", "list_assets"],
        "The operation to perform on the component"
    ],
    component_id: Annotated[int, "Component ID"],
    checkout_data: Annotated[ComponentCheckout | None, "Checkout data (required for checkout action)"] = None,
    checkout_id: Annotated[int | None, "Component asset ID from checkout record (required for checkin)"] = None,
) -> dict[str, Any]:
    """Perform checkout/checkin operations on components.

    Components can be checked out to assets (not users). Each checkout
    decrements the available quantity.

    Operations:
    - checkout: Checkout component(s) to an asset (requires checkout_data with assigned_to asset ID)
    - checkin: Checkin component(s) from an asset (requires checkout_id)
    - list_assets: List all assets that have this component checked out

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = _client.get_direct_api()

        if action == "checkout":
            if not checkout_data:
                return {"success": False, "error": "checkout_data is required for checkout action"}

            checkout_payload = {k: v for k, v in checkout_data.model_dump().items() if v is not None}
            result = api._request("POST", f"components/{component_id}/checkout", json=checkout_payload)

            return {
                "success": True,
                "action": "checkout",
                "component_id": component_id,
                "message": f"Component checked out to asset {checkout_data.assigned_to}",
                "result": result
            }

        elif action == "checkin":
            if not checkout_id:
                return {"success": False, "error": "checkout_id is required for checkin action"}

            result = api._request("POST", f"components/{component_id}/checkin/{checkout_id}")

            return {
                "success": True,
                "action": "checkin",
                "component_id": component_id,
                "checkout_id": checkout_id,
                "message": "Component checked in successfully",
                "result": result
            }

        elif action == "list_assets":
            result = api._request("GET", f"components/{component_id}/assets")
            assets = result.get("rows", [])

            return {
                "success": True,
                "action": "list_assets",
                "component_id": component_id,
                "count": len(assets),
                "assets": assets
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Component not found: {e}")
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
        logger.error(f"Unexpected error in component_operations: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


