"""Snipe-IT foundational entity tools: categories, manufacturers, asset models (and their file attachments), status labels, locations, suppliers, depreciations."""

import logging
from typing import Annotated, Any, Literal

import requests
from pydantic import Field
from snipeit.exceptions import (
    SnipeITAuthenticationError,
    SnipeITException,
    SnipeITNotFoundError,
    SnipeITValidationError,
)

from .. import client as _client
from ..mcp_server import mcp
from ..schemas import CategoryData, ManufacturerData, AssetModelData, StatusLabelData, LocationData, SupplierData, DepreciationData

logger = logging.getLogger(__name__)


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_categories(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete"],
        "The action to perform on categories"
    ],
    category_id: Annotated[int | None, "Category ID (required for get, update, delete)"] = None,
    category_data: Annotated[CategoryData | None, "Category data (required for create, optional for update)"] = None,
    limit: Annotated[int, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list action)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action)"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT categories with CRUD operations.

    Categories organize assets, accessories, consumables, components, and licenses.

    Operations:
    - create: Create a new category (requires category_data with name and category_type)
    - get: Retrieve a single category by ID
    - list: List categories with optional pagination and filtering
    - update: Update an existing category (requires category_id and category_data)
    - delete: Delete a category (requires category_id)

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        client = _client.get_snipeit_client()

        with client:
            if action == "create":
                if not category_data:
                    return {"success": False, "error": "category_data is required for create action"}

                if not category_data.name or not category_data.category_type:
                    return {
                        "success": False,
                        "error": "name and category_type are required to create a category"
                    }

                create_kwargs = {k: v for k, v in category_data.model_dump().items() if v is not None}
                category = client.categories.create(**create_kwargs)

                return {
                    "success": True,
                    "action": "create",
                    "category": {
                        "id": category.id,
                        "name": getattr(category, "name", None),
                        "category_type": getattr(category, "category_type", None),
                    }
                }

            elif action == "get":
                if not category_id:
                    return {"success": False, "error": "category_id is required for get action"}

                category = client.categories.get(category_id)

                category_dict = {
                    "id": category.id,
                    "name": getattr(category, "name", None),
                    "category_type": getattr(category, "category_type", None),
                    "eula_text": getattr(category, "eula_text", None),
                    "use_default_eula": getattr(category, "use_default_eula", None),
                    "require_acceptance": getattr(category, "require_acceptance", None),
                    "checkin_email": getattr(category, "checkin_email", None),
                    "assets_count": getattr(category, "assets_count", None),
                    "accessories_count": getattr(category, "accessories_count", None),
                    "consumables_count": getattr(category, "consumables_count", None),
                    "components_count": getattr(category, "components_count", None),
                    "licenses_count": getattr(category, "licenses_count", None),
                }

                return {
                    "success": True,
                    "action": "get",
                    "category": category_dict
                }

            elif action == "list":
                params = {"limit": limit, "offset": offset}
                if search:
                    params["search"] = search
                # Default sort=id, order=asc for stable offset-based pagination
                params["sort"] = sort or "id"
                params["order"] = order or "asc"

                api = _client.get_direct_api()
                categories, _total = api.list_page("categories", **params)

                categories_list = [
                    {
                        "id": cat.get("id"),
                        "name": cat.get("name"),
                        "category_type": cat.get("category_type"),
                        "assets_count": cat.get("assets_count"),
                    }
                    for cat in categories
                ]

                return {
                    "success": True,
                    "action": "list",
                    **_client.pagination_meta(len(categories_list), _total, limit, offset),
                    "categories": categories_list,
                }

            elif action == "update":
                if not category_id:
                    return {"success": False, "error": "category_id is required for update action"}
                if not category_data:
                    return {"success": False, "error": "category_data is required for update action"}

                update_kwargs = {k: v for k, v in category_data.model_dump().items() if v is not None}
                category = client.categories.patch(category_id, **update_kwargs)

                return {
                    "success": True,
                    "action": "update",
                    "category": {
                        "id": category.id,
                        "name": getattr(category, "name", None),
                    }
                }

            elif action == "delete":
                if not category_id:
                    return {"success": False, "error": "category_id is required for delete action"}

                client.categories.delete(category_id)

                return {
                    "success": True,
                    "action": "delete",
                    "category_id": category_id,
                    "message": "Category deleted successfully"
                }

    except SnipeITNotFoundError as e:
        logger.error(f"Category not found: {e}")
        return {"success": False, "error": f"Category not found: {str(e)}"}
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
        logger.error(f"Unexpected error in manage_categories: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_manufacturers(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete"],
        "The action to perform on manufacturers"
    ],
    manufacturer_id: Annotated[int | None, "Manufacturer ID (required for get, update, delete)"] = None,
    manufacturer_data: Annotated[ManufacturerData | None, "Manufacturer data (required for create, optional for update)"] = None,
    limit: Annotated[int, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list action)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action)"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT manufacturers with CRUD operations.

    Manufacturers represent the companies that produce assets.

    Operations:
    - create: Create a new manufacturer (requires manufacturer_data with name)
    - get: Retrieve a single manufacturer by ID
    - list: List manufacturers with optional pagination and filtering
    - update: Update an existing manufacturer (requires manufacturer_id and manufacturer_data)
    - delete: Delete a manufacturer (requires manufacturer_id)

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        client = _client.get_snipeit_client()

        with client:
            if action == "create":
                if not manufacturer_data:
                    return {"success": False, "error": "manufacturer_data is required for create action"}

                if not manufacturer_data.name:
                    return {
                        "success": False,
                        "error": "name is required to create a manufacturer"
                    }

                create_kwargs = {k: v for k, v in manufacturer_data.model_dump().items() if v is not None}
                manufacturer = client.manufacturers.create(**create_kwargs)

                return {
                    "success": True,
                    "action": "create",
                    "manufacturer": {
                        "id": manufacturer.id,
                        "name": getattr(manufacturer, "name", None),
                    }
                }

            elif action == "get":
                if not manufacturer_id:
                    return {"success": False, "error": "manufacturer_id is required for get action"}

                manufacturer = client.manufacturers.get(manufacturer_id)

                manufacturer_dict = {
                    "id": manufacturer.id,
                    "name": getattr(manufacturer, "name", None),
                    "url": getattr(manufacturer, "url", None),
                    "support_url": getattr(manufacturer, "support_url", None),
                    "support_phone": getattr(manufacturer, "support_phone", None),
                    "support_email": getattr(manufacturer, "support_email", None),
                    "assets_count": getattr(manufacturer, "assets_count", None),
                    "licenses_count": getattr(manufacturer, "licenses_count", None),
                    "consumables_count": getattr(manufacturer, "consumables_count", None),
                    "accessories_count": getattr(manufacturer, "accessories_count", None),
                }

                return {
                    "success": True,
                    "action": "get",
                    "manufacturer": manufacturer_dict
                }

            elif action == "list":
                params = {"limit": limit, "offset": offset}
                if search:
                    params["search"] = search
                # Default sort=id, order=asc for stable offset-based pagination
                params["sort"] = sort or "id"
                params["order"] = order or "asc"

                api = _client.get_direct_api()
                manufacturers, _total = api.list_page("manufacturers", **params)

                manufacturers_list = [
                    {
                        "id": mfr.get("id"),
                        "name": mfr.get("name"),
                        "assets_count": mfr.get("assets_count"),
                    }
                    for mfr in manufacturers
                ]

                return {
                    "success": True,
                    "action": "list",
                    **_client.pagination_meta(len(manufacturers_list), _total, limit, offset),
                    "manufacturers": manufacturers_list,
                }

            elif action == "update":
                if not manufacturer_id:
                    return {"success": False, "error": "manufacturer_id is required for update action"}
                if not manufacturer_data:
                    return {"success": False, "error": "manufacturer_data is required for update action"}

                update_kwargs = {k: v for k, v in manufacturer_data.model_dump().items() if v is not None}
                manufacturer = client.manufacturers.patch(manufacturer_id, **update_kwargs)

                return {
                    "success": True,
                    "action": "update",
                    "manufacturer": {
                        "id": manufacturer.id,
                        "name": getattr(manufacturer, "name", None),
                    }
                }

            elif action == "delete":
                if not manufacturer_id:
                    return {"success": False, "error": "manufacturer_id is required for delete action"}

                client.manufacturers.delete(manufacturer_id)

                return {
                    "success": True,
                    "action": "delete",
                    "manufacturer_id": manufacturer_id,
                    "message": "Manufacturer deleted successfully"
                }

    except SnipeITNotFoundError as e:
        logger.error(f"Manufacturer not found: {e}")
        return {"success": False, "error": f"Manufacturer not found: {str(e)}"}
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
        logger.error(f"Unexpected error in manage_manufacturers: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_models(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete", "assets"],
        "The action to perform on asset models"
    ],
    model_id: Annotated[int | None, "Model ID (required for get, update, delete, assets)"] = None,
    model_data: Annotated[AssetModelData | None, "Model data (required for create, optional for update)"] = None,
    limit: Annotated[int, "Number of results to return (for list/assets actions)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list/assets actions)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action)"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT asset models with CRUD operations.

    Models define types of assets (e.g., 'MacBook Pro 14"', 'Dell XPS 15').

    Operations:
    - create: Create a new model (requires model_data with name and category_id)
    - get: Retrieve a single model by ID
    - list: List models with optional pagination and filtering
    - update: Update an existing model (requires model_id and model_data)
    - delete: Delete a model (requires model_id)
    - assets: List all assets of a specific model

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        client = _client.get_snipeit_client()

        with client:
            if action == "create":
                if not model_data:
                    return {"success": False, "error": "model_data is required for create action"}

                if not model_data.name or not model_data.category_id:
                    return {
                        "success": False,
                        "error": "name and category_id are required to create a model"
                    }

                create_kwargs = {k: v for k, v in model_data.model_dump().items() if v is not None}
                model = client.models.create(**create_kwargs)

                return {
                    "success": True,
                    "action": "create",
                    "model": {
                        "id": model.id,
                        "name": getattr(model, "name", None),
                        "model_number": getattr(model, "model_number", None),
                    }
                }

            elif action == "get":
                if not model_id:
                    return {"success": False, "error": "model_id is required for get action"}

                model = client.models.get(model_id)

                model_dict = {
                    "id": model.id,
                    "name": getattr(model, "name", None),
                    "model_number": getattr(model, "model_number", None),
                    "manufacturer": getattr(model, "manufacturer", None),
                    "category": getattr(model, "category", None),
                    "eol": getattr(model, "eol", None),
                    "depreciation": getattr(model, "depreciation", None),
                    "notes": getattr(model, "notes", None),
                    "fieldset": getattr(model, "fieldset", None),
                    "requestable": getattr(model, "requestable", None),
                    "assets_count": getattr(model, "assets_count", None),
                }

                return {
                    "success": True,
                    "action": "get",
                    "model": model_dict
                }

            elif action == "list":
                params = {"limit": limit, "offset": offset}
                if search:
                    params["search"] = search
                # Default sort=id, order=asc for stable offset-based pagination
                params["sort"] = sort or "id"
                params["order"] = order or "asc"

                api = _client.get_direct_api()
                models, _total = api.list_page("models", **params)

                models_list = [
                    {
                        "id": m.get("id"),
                        "name": m.get("name"),
                        "model_number": m.get("model_number"),
                        "manufacturer": (m.get("manufacturer") or {}).get("name") if isinstance(m.get("manufacturer"), dict) else None,
                        "assets_count": m.get("assets_count"),
                    }
                    for m in models
                ]

                return {
                    "success": True,
                    "action": "list",
                    **_client.pagination_meta(len(models_list), _total, limit, offset),
                    "models": models_list,
                }

            elif action == "update":
                if not model_id:
                    return {"success": False, "error": "model_id is required for update action"}
                if not model_data:
                    return {"success": False, "error": "model_data is required for update action"}

                update_kwargs = {k: v for k, v in model_data.model_dump().items() if v is not None}
                model = client.models.patch(model_id, **update_kwargs)

                return {
                    "success": True,
                    "action": "update",
                    "model": {
                        "id": model.id,
                        "name": getattr(model, "name", None),
                    }
                }

            elif action == "delete":
                if not model_id:
                    return {"success": False, "error": "model_id is required for delete action"}

                client.models.delete(model_id)

                return {
                    "success": True,
                    "action": "delete",
                    "model_id": model_id,
                    "message": "Model deleted successfully"
                }

            elif action == "assets":
                if not model_id:
                    return {"success": False, "error": "model_id is required for assets action"}

                api = _client.get_direct_api()
                params = {"limit": limit, "offset": offset}
                result = api._request("GET", f"models/{model_id}/assets", params=params)
                assets = result.get("rows", [])

                return {
                    "success": True,
                    "action": "assets",
                    "model_id": model_id,
                    **_client.pagination_meta(len(assets), result.get("total", len(assets)), limit, offset),
                    "assets": assets,
                }

    except SnipeITNotFoundError as e:
        logger.error(f"Model not found: {e}")
        return {"success": False, "error": f"Model not found: {str(e)}"}
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
        logger.error(f"Unexpected error in manage_models: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_status_labels(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete", "assets"],
        "The action to perform on status labels"
    ],
    status_label_id: Annotated[int | None, "Status label ID (required for get, update, delete, assets)"] = None,
    status_label_data: Annotated[StatusLabelData | None, "Status label data (required for create, optional for update)"] = None,
    limit: Annotated[int, "Number of results to return (for list/assets actions)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list/assets actions)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action)"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT status labels with CRUD operations.

    Status labels define the state of assets (deployable, pending, archived, etc.).

    Operations:
    - create: Create a new status label (requires status_label_data with name and type)
    - get: Retrieve a single status label by ID
    - list: List status labels with optional pagination and filtering
    - update: Update an existing status label (requires status_label_id and status_label_data)
    - delete: Delete a status label (requires status_label_id)
    - assets: List all assets with a specific status label

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = _client.get_direct_api()

        if action == "create":
            if not status_label_data:
                return {"success": False, "error": "status_label_data is required for create action"}

            if not status_label_data.name or not status_label_data.type:
                return {
                    "success": False,
                    "error": "name and type are required to create a status label"
                }

            create_data = {k: v for k, v in status_label_data.model_dump().items() if v is not None}
            result = api.create("statuslabels", create_data)

            return {
                "success": True,
                "action": "create",
                "status_label": {
                    "id": result.get("payload", result).get("id"),
                    "name": result.get("payload", result).get("name"),
                    "type": result.get("payload", result).get("type"),
                }
            }

        elif action == "get":
            if not status_label_id:
                return {"success": False, "error": "status_label_id is required for get action"}

            status_label = api.get("statuslabels", status_label_id)

            return {
                "success": True,
                "action": "get",
                "status_label": {
                    "id": status_label.get("id"),
                    "name": status_label.get("name"),
                    "type": status_label.get("type"),
                    "color": status_label.get("color"),
                    "show_in_nav": status_label.get("show_in_nav"),
                    "default_label": status_label.get("default_label"),
                    "notes": status_label.get("notes"),
                    "assets_count": status_label.get("assets_count"),
                }
            }

        elif action == "list":
            status_labels, _total = api.list_page("statuslabels", limit=limit, offset=offset,
                                                  search=search, sort=sort, order=order)

            status_labels_list = [
                {
                    "id": sl.get("id"),
                    "name": sl.get("name"),
                    "type": sl.get("type"),
                    "assets_count": sl.get("assets_count"),
                }
                for sl in status_labels
            ]

            return {
                "success": True,
                "action": "list",
                **_client.pagination_meta(len(status_labels_list), _total, limit, offset),
                "status_labels": status_labels_list,
            }

        elif action == "update":
            if not status_label_id:
                return {"success": False, "error": "status_label_id is required for update action"}
            if not status_label_data:
                return {"success": False, "error": "status_label_data is required for update action"}

            update_data = {k: v for k, v in status_label_data.model_dump().items() if v is not None}
            result = api.update("statuslabels", status_label_id, update_data)

            return {
                "success": True,
                "action": "update",
                "status_label": {
                    "id": result.get("payload", result).get("id"),
                    "name": result.get("payload", result).get("name"),
                }
            }

        elif action == "delete":
            if not status_label_id:
                return {"success": False, "error": "status_label_id is required for delete action"}

            api.delete("statuslabels", status_label_id)

            return {
                "success": True,
                "action": "delete",
                "status_label_id": status_label_id,
                "message": "Status label deleted successfully"
            }

        elif action == "assets":
            if not status_label_id:
                return {"success": False, "error": "status_label_id is required for assets action"}

            params = {"limit": limit, "offset": offset}
            result = api._request("GET", f"statuslabels/{status_label_id}/assetlist", params=params)
            assets = result.get("rows", [])

            return {
                "success": True,
                "action": "assets",
                "status_label_id": status_label_id,
                **_client.pagination_meta(len(assets), result.get("total", len(assets)), limit, offset),
                "assets": assets,
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Status label not found: {e}")
        return {"success": False, "error": f"Status label not found: {str(e)}"}
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
        logger.error(f"Unexpected error in manage_status_labels: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_locations(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete", "assets", "users"],
        "The action to perform on locations"
    ],
    location_id: Annotated[int | None, "Location ID (required for get, update, delete, assets, users)"] = None,
    location_data: Annotated[LocationData | None, "Location data (required for create, optional for update)"] = None,
    limit: Annotated[int, "Number of results to return (for list/assets/users actions)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list/assets/users actions)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action)"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT locations with CRUD operations.

    Locations represent physical places where assets are stored or deployed.

    Operations:
    - create: Create a new location (requires location_data with name)
    - get: Retrieve a single location by ID
    - list: List locations with optional pagination and filtering
    - update: Update an existing location (requires location_id and location_data)
    - delete: Delete a location (requires location_id)
    - assets: List all assets at a specific location
    - users: List all users assigned to a location

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        client = _client.get_snipeit_client()

        with client:
            if action == "create":
                if not location_data:
                    return {"success": False, "error": "location_data is required for create action"}

                if not location_data.name:
                    return {
                        "success": False,
                        "error": "name is required to create a location"
                    }

                create_kwargs = {k: v for k, v in location_data.model_dump().items() if v is not None}
                location = client.locations.create(**create_kwargs)

                return {
                    "success": True,
                    "action": "create",
                    "location": {
                        "id": location.id,
                        "name": getattr(location, "name", None),
                    }
                }

            elif action == "get":
                if not location_id:
                    return {"success": False, "error": "location_id is required for get action"}

                location = client.locations.get(location_id)

                location_dict = {
                    "id": location.id,
                    "name": getattr(location, "name", None),
                    "address": getattr(location, "address", None),
                    "address2": getattr(location, "address2", None),
                    "city": getattr(location, "city", None),
                    "state": getattr(location, "state", None),
                    "country": getattr(location, "country", None),
                    "zip": getattr(location, "zip", None),
                    "ldap_ou": getattr(location, "ldap_ou", None),
                    "manager": getattr(location, "manager", None),
                    "parent": getattr(location, "parent", None),
                    "currency": getattr(location, "currency", None),
                    "assets_count": getattr(location, "assets_count", None),
                    "assigned_assets_count": getattr(location, "assigned_assets_count", None),
                    "users_count": getattr(location, "users_count", None),
                }

                return {
                    "success": True,
                    "action": "get",
                    "location": location_dict
                }

            elif action == "list":
                params = {"limit": limit, "offset": offset}
                if search:
                    params["search"] = search
                # Default sort=id, order=asc for stable offset-based pagination
                params["sort"] = sort or "id"
                params["order"] = order or "asc"

                api = _client.get_direct_api()
                locations, _total = api.list_page("locations", **params)

                locations_list = [
                    {
                        "id": loc.get("id"),
                        "name": loc.get("name"),
                        "city": loc.get("city"),
                        "assets_count": loc.get("assets_count"),
                    }
                    for loc in locations
                ]

                return {
                    "success": True,
                    "action": "list",
                    **_client.pagination_meta(len(locations_list), _total, limit, offset),
                    "locations": locations_list,
                }

            elif action == "update":
                if not location_id:
                    return {"success": False, "error": "location_id is required for update action"}
                if not location_data:
                    return {"success": False, "error": "location_data is required for update action"}

                update_kwargs = {k: v for k, v in location_data.model_dump().items() if v is not None}
                location = client.locations.patch(location_id, **update_kwargs)

                return {
                    "success": True,
                    "action": "update",
                    "location": {
                        "id": location.id,
                        "name": getattr(location, "name", None),
                    }
                }

            elif action == "delete":
                if not location_id:
                    return {"success": False, "error": "location_id is required for delete action"}

                client.locations.delete(location_id)

                return {
                    "success": True,
                    "action": "delete",
                    "location_id": location_id,
                    "message": "Location deleted successfully"
                }

            elif action == "assets":
                if not location_id:
                    return {"success": False, "error": "location_id is required for assets action"}

                api = _client.get_direct_api()
                params = {"limit": limit, "offset": offset}
                result = api._request("GET", f"locations/{location_id}/assets", params=params)
                assets = result.get("rows", [])

                return {
                    "success": True,
                    "action": "assets",
                    "location_id": location_id,
                    **_client.pagination_meta(len(assets), result.get("total", len(assets)), limit, offset),
                    "assets": assets,
                }

            elif action == "users":
                if not location_id:
                    return {"success": False, "error": "location_id is required for users action"}

                api = _client.get_direct_api()
                params = {"limit": limit, "offset": offset}
                result = api._request("GET", f"locations/{location_id}/users", params=params)
                users = result.get("rows", [])

                return {
                    "success": True,
                    "action": "users",
                    "location_id": location_id,
                    **_client.pagination_meta(len(users), result.get("total", len(users)), limit, offset),
                    "users": users,
                }

    except SnipeITNotFoundError as e:
        logger.error(f"Location not found: {e}")
        return {"success": False, "error": f"Location not found: {str(e)}"}
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
        logger.error(f"Unexpected error in manage_locations: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_suppliers(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete"],
        "The action to perform on suppliers"
    ],
    supplier_id: Annotated[int | None, "Supplier ID (required for get, update, delete)"] = None,
    supplier_data: Annotated[SupplierData | None, "Supplier data (required for create, optional for update)"] = None,
    limit: Annotated[int, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list action)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action)"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT suppliers with CRUD operations.

    Suppliers are vendors from whom assets and consumables are purchased.

    Operations:
    - create: Create a new supplier (requires supplier_data with name)
    - get: Retrieve a single supplier by ID
    - list: List suppliers with optional pagination and filtering
    - update: Update an existing supplier (requires supplier_id and supplier_data)
    - delete: Delete a supplier (requires supplier_id)

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = _client.get_direct_api()

        if action == "create":
            if not supplier_data:
                return {"success": False, "error": "supplier_data is required for create action"}

            if not supplier_data.name:
                return {
                    "success": False,
                    "error": "name is required to create a supplier"
                }

            create_data = {k: v for k, v in supplier_data.model_dump().items() if v is not None}
            result = api.create("suppliers", create_data)

            return {
                "success": True,
                "action": "create",
                "supplier": {
                    "id": result.get("payload", result).get("id"),
                    "name": result.get("payload", result).get("name"),
                }
            }

        elif action == "get":
            if not supplier_id:
                return {"success": False, "error": "supplier_id is required for get action"}

            supplier = api.get("suppliers", supplier_id)

            return {
                "success": True,
                "action": "get",
                "supplier": {
                    "id": supplier.get("id"),
                    "name": supplier.get("name"),
                    "address": supplier.get("address"),
                    "address2": supplier.get("address2"),
                    "city": supplier.get("city"),
                    "state": supplier.get("state"),
                    "country": supplier.get("country"),
                    "zip": supplier.get("zip"),
                    "phone": supplier.get("phone"),
                    "fax": supplier.get("fax"),
                    "email": supplier.get("email"),
                    "contact": supplier.get("contact"),
                    "url": supplier.get("url"),
                    "notes": supplier.get("notes"),
                    "assets_count": supplier.get("assets_count"),
                    "accessories_count": supplier.get("accessories_count"),
                    "licenses_count": supplier.get("licenses_count"),
                }
            }

        elif action == "list":
            suppliers, _total = api.list_page("suppliers", limit=limit, offset=offset,
                                              search=search, sort=sort, order=order)

            suppliers_list = [
                {
                    "id": sup.get("id"),
                    "name": sup.get("name"),
                    "assets_count": sup.get("assets_count"),
                }
                for sup in suppliers
            ]

            return {
                "success": True,
                "action": "list",
                **_client.pagination_meta(len(suppliers_list), _total, limit, offset),
                "suppliers": suppliers_list,
            }

        elif action == "update":
            if not supplier_id:
                return {"success": False, "error": "supplier_id is required for update action"}
            if not supplier_data:
                return {"success": False, "error": "supplier_data is required for update action"}

            update_data = {k: v for k, v in supplier_data.model_dump().items() if v is not None}
            result = api.update("suppliers", supplier_id, update_data)

            return {
                "success": True,
                "action": "update",
                "supplier": {
                    "id": result.get("payload", result).get("id"),
                    "name": result.get("payload", result).get("name"),
                }
            }

        elif action == "delete":
            if not supplier_id:
                return {"success": False, "error": "supplier_id is required for delete action"}

            api.delete("suppliers", supplier_id)

            return {
                "success": True,
                "action": "delete",
                "supplier_id": supplier_id,
                "message": "Supplier deleted successfully"
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Supplier not found: {e}")
        return {"success": False, "error": f"Supplier not found: {str(e)}"}
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
        logger.error(f"Unexpected error in manage_suppliers: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_depreciations(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete"],
        "The action to perform on depreciations"
    ],
    depreciation_id: Annotated[int | None, "Depreciation ID (required for get, update, delete)"] = None,
    depreciation_data: Annotated[DepreciationData | None, "Depreciation data (required for create, optional for update)"] = None,
    limit: Annotated[int, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list action)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action)"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT depreciations with CRUD operations.

    Depreciations define how assets lose value over time (e.g., 3-year straight-line).

    Operations:
    - create: Create a new depreciation (requires depreciation_data with name and months)
    - get: Retrieve a single depreciation by ID
    - list: List depreciations with optional pagination and filtering
    - update: Update an existing depreciation (requires depreciation_id and depreciation_data)
    - delete: Delete a depreciation (requires depreciation_id)

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = _client.get_direct_api()

        if action == "create":
            if not depreciation_data:
                return {"success": False, "error": "depreciation_data is required for create action"}

            if not depreciation_data.name or depreciation_data.months is None:
                return {
                    "success": False,
                    "error": "name and months are required to create a depreciation"
                }

            create_data = {k: v for k, v in depreciation_data.model_dump().items() if v is not None}
            result = api.create("depreciations", create_data)

            return {
                "success": True,
                "action": "create",
                "depreciation": {
                    "id": result.get("payload", result).get("id"),
                    "name": result.get("payload", result).get("name"),
                    "months": result.get("payload", result).get("months"),
                }
            }

        elif action == "get":
            if not depreciation_id:
                return {"success": False, "error": "depreciation_id is required for get action"}

            depreciation = api.get("depreciations", depreciation_id)

            return {
                "success": True,
                "action": "get",
                "depreciation": {
                    "id": depreciation.get("id"),
                    "name": depreciation.get("name"),
                    "months": depreciation.get("months"),
                }
            }

        elif action == "list":
            depreciations, _total = api.list_page("depreciations", limit=limit, offset=offset,
                                                  search=search, sort=sort, order=order)

            depreciations_list = [
                {
                    "id": dep.get("id"),
                    "name": dep.get("name"),
                    "months": dep.get("months"),
                }
                for dep in depreciations
            ]

            return {
                "success": True,
                "action": "list",
                **_client.pagination_meta(len(depreciations_list), _total, limit, offset),
                "depreciations": depreciations_list,
            }

        elif action == "update":
            if not depreciation_id:
                return {"success": False, "error": "depreciation_id is required for update action"}
            if not depreciation_data:
                return {"success": False, "error": "depreciation_data is required for update action"}

            update_data = {k: v for k, v in depreciation_data.model_dump().items() if v is not None}
            result = api.update("depreciations", depreciation_id, update_data)

            return {
                "success": True,
                "action": "update",
                "depreciation": {
                    "id": result.get("payload", result).get("id"),
                    "name": result.get("payload", result).get("name"),
                }
            }

        elif action == "delete":
            if not depreciation_id:
                return {"success": False, "error": "depreciation_id is required for delete action"}

            api.delete("depreciations", depreciation_id)

            return {
                "success": True,
                "action": "delete",
                "depreciation_id": depreciation_id,
                "message": "Depreciation deleted successfully"
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Depreciation not found: {e}")
        return {"success": False, "error": f"Depreciation not found: {str(e)}"}
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
        logger.error(f"Unexpected error in manage_depreciations: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}




@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def model_files(
    action: Annotated[
        Literal["upload", "list", "download", "delete"],
        "The file operation to perform"
    ],
    model_id: Annotated[int, "Model ID"],
    file_path: Annotated[str | None, "File path to upload (for upload action)"] = None,
    file_id: Annotated[int | None, "File ID (required for download and delete actions)"] = None,
    save_path: Annotated[str | None, "Path to save downloaded file (for download action)"] = None,
) -> dict[str, Any]:
    """Manage file attachments for asset models.

    Models can have attached files such as documentation, manuals,
    datasheets, or images that apply to all assets of that model.

    Operations:
    - upload: Upload a file to a model
    - list: List all files attached to a model
    - download: Download a specific file from a model
    - delete: Delete a specific file from a model

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = _client.get_direct_api()

        if action == "upload":
            if not file_path:
                return {"success": False, "error": "file_path is required for upload action"}

            import os
            if not os.path.exists(file_path):
                return {"success": False, "error": f"File not found: {file_path}"}

            filename = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                files = {"file": (filename, f)}
                url = f"{api.base_url}/api/v1/models/{model_id}/files"
                headers = {
                    "Authorization": f"Bearer {_client.SNIPEIT_TOKEN}",
                    "Accept": "application/json",
                }
                response = requests.post(url, headers=headers, files=files)
                response.raise_for_status()
                result = response.json()

            return {
                "success": True,
                "action": "upload",
                "model_id": model_id,
                "message": f"File '{filename}' uploaded successfully",
                "result": result
            }

        elif action == "list":
            result = api._request("GET", f"models/{model_id}/files")
            files = result.get("rows", [])

            files_list = [
                {
                    "id": f.get("id"),
                    "filename": f.get("filename"),
                    "url": f.get("url"),
                    "created_at": f.get("created_at"),
                    "notes": f.get("notes"),
                }
                for f in files
            ]

            return {
                "success": True,
                "action": "list",
                "model_id": model_id,
                "count": len(files_list),
                "files": files_list
            }

        elif action == "download":
            if file_id is None:
                return {"success": False, "error": "file_id is required for download action"}
            if not save_path:
                return {"success": False, "error": "save_path is required for download action"}

            url = f"{api.base_url}/api/v1/models/{model_id}/files/{file_id}"
            headers = {
                "Authorization": f"Bearer {_client.SNIPEIT_TOKEN}",
                "Accept": "application/octet-stream",
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            import os
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(response.content)

            return {
                "success": True,
                "action": "download",
                "model_id": model_id,
                "file_id": file_id,
                "saved_to": save_path,
                "message": f"File downloaded to {save_path}"
            }

        elif action == "delete":
            if file_id is None:
                return {"success": False, "error": "file_id is required for delete action"}

            api._request("DELETE", f"models/{model_id}/files/{file_id}")

            return {
                "success": True,
                "action": "delete",
                "model_id": model_id,
                "file_id": file_id,
                "message": "File deleted successfully"
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Model or file not found: {e}")
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
        logger.error(f"Unexpected error in model_files: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


