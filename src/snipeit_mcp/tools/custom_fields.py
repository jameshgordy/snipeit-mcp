"""Snipe-IT custom field tools: fields and fieldsets."""

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
from ..schemas import FieldData, FieldsetData

logger = logging.getLogger(__name__)


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_fields(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete", "associate", "disassociate"],
        "The action to perform on custom fields"
    ],
    field_id: Annotated[int | None, "Field ID (required for get, update, delete, associate, disassociate)"] = None,
    field_data: Annotated[FieldData | None, "Field data (required for create, optional for update)"] = None,
    fieldset_id: Annotated[int | None, "Fieldset ID (required for associate/disassociate actions)"] = None,
    limit: Annotated[int, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list action)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    required: Annotated[bool | None, "Whether field is required in fieldset (for associate action)"] = False,
    order: Annotated[int | None, "Display order in fieldset (for associate action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT custom fields with CRUD operations.

    Custom fields allow you to add additional data fields to assets beyond
    the built-in fields. Fields must be associated with fieldsets to be used.

    Actions:
    - create: Create a new custom field (requires field_data with name, element)
    - get: Retrieve a single field by ID
    - list: List fields with optional pagination and filtering
    - update: Update an existing field
    - delete: Delete a field
    - associate: Associate a field with a fieldset
    - disassociate: Remove a field from a fieldset

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = _client.get_direct_api()

        if action == "create":
            if not field_data:
                return {"success": False, "error": "field_data is required for create action"}

            if not field_data.name or not field_data.element:
                return {"success": False, "error": "name and element are required to create a field"}

            create_payload = {k: v for k, v in field_data.model_dump().items() if v is not None}
            result = api.create("fields", create_payload)

            return {
                "success": True,
                "action": "create",
                "field": result
            }

        elif action == "get":
            if not field_id:
                return {"success": False, "error": "field_id is required for get action"}

            result = api.get("fields", field_id)

            return {
                "success": True,
                "action": "get",
                "field": result
            }

        elif action == "list":
            params = {"limit": limit, "offset": offset}
            if search:
                params["search"] = search

            fields, _total = api.list_page("fields", **params)

            fields_list = [
                {
                    "id": fld.get("id"),
                    "name": fld.get("name"),
                    "db_column_name": fld.get("db_column_name"),
                    "element": fld.get("element"),
                    "format": fld.get("format"),
                    "field_encrypted": fld.get("field_encrypted"),
                }
                for fld in fields
            ]

            return {
                "success": True,
                "action": "list",
                **_client.pagination_meta(len(fields_list), _total, limit, offset),
                "fields": fields_list,
            }

        elif action == "update":
            if not field_id:
                return {"success": False, "error": "field_id is required for update action"}
            if not field_data:
                return {"success": False, "error": "field_data is required for update action"}

            update_payload = {k: v for k, v in field_data.model_dump().items() if v is not None}
            result = api.update("fields", field_id, update_payload)

            return {
                "success": True,
                "action": "update",
                "field_id": field_id,
                "result": result
            }

        elif action == "delete":
            if not field_id:
                return {"success": False, "error": "field_id is required for delete action"}

            result = api.delete("fields", field_id)

            return {
                "success": True,
                "action": "delete",
                "field_id": field_id,
                "message": "Field deleted successfully"
            }

        elif action == "associate":
            if not field_id or not fieldset_id:
                return {"success": False, "error": "field_id and fieldset_id are required for associate action"}

            payload = {"required": required}
            if order is not None:
                payload["order"] = order

            result = api._request("POST", f"fields/{field_id}/associate/{fieldset_id}", json=payload)

            return {
                "success": True,
                "action": "associate",
                "field_id": field_id,
                "fieldset_id": fieldset_id,
                "message": "Field associated with fieldset successfully"
            }

        elif action == "disassociate":
            if not field_id or not fieldset_id:
                return {"success": False, "error": "field_id and fieldset_id are required for disassociate action"}

            result = api._request("POST", f"fields/{field_id}/disassociate/{fieldset_id}")

            return {
                "success": True,
                "action": "disassociate",
                "field_id": field_id,
                "fieldset_id": fieldset_id,
                "message": "Field disassociated from fieldset successfully"
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Field not found: {e}")
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
        logger.error(f"Unexpected error in manage_fields: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_fieldsets(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete", "fields", "reorder"],
        "The action to perform on fieldsets"
    ],
    fieldset_id: Annotated[int | None, "Fieldset ID (required for get, update, delete, fields, reorder)"] = None,
    fieldset_data: Annotated[FieldsetData | None, "Fieldset data (required for create, optional for update)"] = None,
    limit: Annotated[int, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list action)"] = 0,
    field_order: Annotated[list[int] | None, "Ordered list of field IDs (for reorder action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT fieldsets with CRUD operations.

    Fieldsets are collections of custom fields that can be assigned to asset
    models. Each model can have one fieldset, and all assets of that model
    will have the custom fields defined in the fieldset.

    Actions:
    - create: Create a new fieldset (requires fieldset_data with name)
    - get: Retrieve a single fieldset by ID
    - list: List fieldsets with optional pagination
    - update: Update an existing fieldset
    - delete: Delete a fieldset
    - fields: List all fields in a fieldset
    - reorder: Reorder fields in a fieldset (requires field_order list of field IDs)

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = _client.get_direct_api()

        if action == "create":
            if not fieldset_data:
                return {"success": False, "error": "fieldset_data is required for create action"}

            if not fieldset_data.name:
                return {"success": False, "error": "name is required to create a fieldset"}

            create_payload = {k: v for k, v in fieldset_data.model_dump().items() if v is not None}
            result = api.create("fieldsets", create_payload)

            return {
                "success": True,
                "action": "create",
                "fieldset": result
            }

        elif action == "get":
            if not fieldset_id:
                return {"success": False, "error": "fieldset_id is required for get action"}

            result = api.get("fieldsets", fieldset_id)

            return {
                "success": True,
                "action": "get",
                "fieldset": result
            }

        elif action == "list":
            params = {"limit": limit, "offset": offset}
            fieldsets, _total = api.list_page("fieldsets", **params)

            fieldsets_list = [
                {
                    "id": fs.get("id"),
                    "name": fs.get("name"),
                    "fields_count": fs.get("fields_count"),
                    "models_count": fs.get("models_count"),
                }
                for fs in fieldsets
            ]

            return {
                "success": True,
                "action": "list",
                **_client.pagination_meta(len(fieldsets_list), _total, limit, offset),
                "fieldsets": fieldsets_list,
            }

        elif action == "update":
            if not fieldset_id:
                return {"success": False, "error": "fieldset_id is required for update action"}
            if not fieldset_data:
                return {"success": False, "error": "fieldset_data is required for update action"}

            update_payload = {k: v for k, v in fieldset_data.model_dump().items() if v is not None}
            result = api.update("fieldsets", fieldset_id, update_payload)

            return {
                "success": True,
                "action": "update",
                "fieldset_id": fieldset_id,
                "result": result
            }

        elif action == "delete":
            if not fieldset_id:
                return {"success": False, "error": "fieldset_id is required for delete action"}

            result = api.delete("fieldsets", fieldset_id)

            return {
                "success": True,
                "action": "delete",
                "fieldset_id": fieldset_id,
                "message": "Fieldset deleted successfully"
            }

        elif action == "fields":
            if not fieldset_id:
                return {"success": False, "error": "fieldset_id is required for fields action"}

            result = api._request("GET", f"fieldsets/{fieldset_id}/fields")
            fields = result.get("rows", []) if isinstance(result, dict) else result

            return {
                "success": True,
                "action": "fields",
                "fieldset_id": fieldset_id,
                "fields": fields
            }

        elif action == "reorder":
            if not fieldset_id:
                return {"success": False, "error": "fieldset_id is required for reorder action"}
            if not field_order:
                return {"success": False, "error": "field_order is required for reorder action"}

            result = api._request(
                "POST",
                f"fields/fieldsets/{fieldset_id}/order",
                json={"item": field_order}
            )

            return {
                "success": True,
                "action": "reorder",
                "fieldset_id": fieldset_id,
                "message": "Field order updated successfully",
                "result": result
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Fieldset not found: {e}")
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
        logger.error(f"Unexpected error in manage_fieldsets: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


