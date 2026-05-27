"""Snipe-IT asset tools (/hardware): CRUD, checkout/checkin/audit, file attachments, labels, maintenance, licenses, and checkout requests."""

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
from ..client import HARDWARE_STANDARD_FIELDS
from ..mcp_server import mcp
from ..schemas import AssetData, CheckoutData, CheckinData, AuditData, MaintenanceData, AssetRequestData

logger = logging.getLogger(__name__)


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_assets(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete"],
        "The action to perform on assets"
    ],
    asset_id: Annotated[int | None, "Asset ID (required for get, update, delete)"] = None,
    asset_tag: Annotated[str | None, "Asset tag (alternative to asset_id for get)"] = None,
    serial: Annotated[str | None, "Serial number (alternative to asset_id for get)"] = None,
    asset_data: Annotated[
        AssetData | None,
        Field(
            description="Asset data for standard fields (required for create, optional for update)",
            json_schema_extra={"type": "object", "additionalProperties": True},
        ),
    ] = None,
    extra_fields: Annotated[
        dict[str, Any] | None,
        Field(
            description="Additional fields not in AssetData: asset_eol_date, custom fields (_snipeit_*), etc. For update, fields are validated against the asset's model fieldset.",
            json_schema_extra={"type": "object", "additionalProperties": True},
        ),
    ] = None,
    limit: Annotated[int, "Number of results to return per page (for list action). Default 20 because each asset payload is large (~5KB with custom fields)."] = 20,
    offset: Annotated[int, "Number of results to skip (for list action)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action). Valid fields: id, name, asset_tag, serial, model, model_number, last_checkout, category, manufacturer, notes, expected_checkin, order_number, companyName, location, image, status_label, assigned_to, created_at, purchase_date, purchase_cost"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
    status_id: Annotated[int | None, "Filter by status label ID (for list action)"] = None,
    model_id: Annotated[int | None, "Filter by model ID (for list action)"] = None,
    company_id: Annotated[int | None, "Filter by company ID (for list action)"] = None,
    location_id: Annotated[int | None, "Filter by location ID (for list action)"] = None,
    category_id: Annotated[int | None, "Filter by category ID (for list action)"] = None,
    manufacturer_id: Annotated[int | None, "Filter by manufacturer ID (for list action)"] = None,
    assigned_to: Annotated[int | None, "Filter by assigned user/asset/location ID (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT assets with CRUD operations.

    This tool handles all basic asset operations:
    - create: Create a new asset (requires asset_data with at least status_id and model_id)
    - get: Retrieve a single asset by ID, asset_tag, or serial number (uses dedicated bytag/byserial endpoints for reliable barcode scanning workflows)
    - list: List assets with optional pagination, filtering by status/model/company/location/category/manufacturer/assigned_to
    - update: Update an existing asset (requires asset_id and asset_data/extra_fields)
    - delete: Delete an asset (requires asset_id)

    Use extra_fields for fields not in AssetData: asset_eol_date, custom fields (_snipeit_*), etc.
    For both create and update, extra_fields are validated against the model's fieldset before sending.
    Invalid field names will be rejected with a list of available fields.

    Note: list action returns full asset objects. With high limits this can produce large responses.
    Use pagination (limit/offset) to control response size.

    Sortable fields for list: id, name, asset_tag, serial, model, model_number, last_checkout,
    category, manufacturer, notes, expected_checkin, order_number, companyName, location,
    image, status_label, assigned_to, created_at, purchase_date, purchase_cost

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        client = _client.get_snipeit_client()
        
        with client:
            if action == "create":
                if not asset_data:
                    return {"success": False, "error": "asset_data is required for create action"}

                if not asset_data.status_id or not asset_data.model_id:
                    return {
                        "success": False,
                        "error": "status_id and model_id are required to create an asset"
                    }

                # Build creation payload
                payload = {k: v for k, v in asset_data.model_dump().items() if v is not None}

                api = _client.get_direct_api()

                # Validate extra_fields against model's fieldset
                if extra_fields:
                    valid_standard = HARDWARE_STANDARD_FIELDS
                    valid_custom = set()

                    # Fetch model to discover valid custom fields from its fieldset
                    model_info = api._request("GET", f"models/{asset_data.model_id}")
                    fieldset = model_info.get("fieldset") or {}
                    fieldset_id = fieldset.get("id") if isinstance(fieldset, dict) else None
                    if fieldset_id:
                        fieldset_detail = api._request("GET", f"fieldsets/{fieldset_id}")
                        fields_data = fieldset_detail.get("fields", {})
                        for field in fields_data.get("rows", []):
                            db_col = field.get("db_column_name")
                            if db_col:
                                valid_custom.add(db_col)

                    all_valid = valid_standard | valid_custom
                    invalid_fields = set(extra_fields.keys()) - all_valid

                    if invalid_fields:
                        return {
                            "success": False,
                            "error": f"Unknown fields: {sorted(invalid_fields)}. "
                                     f"Available standard fields: {sorted(valid_standard)}. "
                                     f"Available custom fields: {sorted(valid_custom)}"
                        }

                    payload.update(extra_fields)

                result = api._request("POST", "hardware", json=payload)
                return {
                    "success": True,
                    "action": "create",
                    "asset": result
                }
            
            elif action == "get":
                # Use direct API for bytag/byserial lookups (more reliable for barcode scanning)
                if asset_tag:
                    api = _client.get_direct_api()
                    asset_data_result = api._request("GET", f"hardware/bytag/{asset_tag}")
                    return {
                        "success": True,
                        "action": "get",
                        "asset": asset_data_result
                    }
                elif serial:
                    api = _client.get_direct_api()
                    asset_data_result = api._request("GET", f"hardware/byserial/{serial}")
                    # byserial may return rows array
                    if "rows" in asset_data_result:
                        assets = asset_data_result.get("rows", [])
                        if not assets:
                            return {"success": False, "error": f"No asset found with serial: {serial}"}
                        return {
                            "success": True,
                            "action": "get",
                            "asset": assets[0] if len(assets) == 1 else None,
                            "assets": assets if len(assets) > 1 else None,
                            "count": len(assets)
                        }
                    return {
                        "success": True,
                        "action": "get",
                        "asset": asset_data_result
                    }
                elif asset_id:
                    # Use direct API to get full asset data including custom fields
                    api = _client.get_direct_api()
                    asset_data_result = api._request("GET", f"hardware/{asset_id}")
                    return {
                        "success": True,
                        "action": "get",
                        "asset": asset_data_result
                    }
                else:
                    return {
                        "success": False,
                        "error": "One of asset_id, asset_tag, or serial is required for get action"
                    }
            
            elif action == "list":
                params = {"limit": limit, "offset": offset}
                if search:
                    params["search"] = search
                # Default sort=id, order=asc for stable offset-based pagination
                params["sort"] = sort or "id"
                params["order"] = order or "asc"
                # Add filter parameters
                if status_id:
                    params["status_id"] = status_id
                if model_id:
                    params["model_id"] = model_id
                if company_id:
                    params["company_id"] = company_id
                if location_id:
                    params["location_id"] = location_id
                if category_id:
                    params["category_id"] = category_id
                if manufacturer_id:
                    params["manufacturer_id"] = manufacturer_id
                if assigned_to:
                    params["assigned_to"] = assigned_to

                # Use direct API to get full asset data including custom fields
                api = _client.get_direct_api()
                assets_result = api._request("GET", "hardware", params=params)
                rows = assets_result.get("rows", [])

                return {
                    "success": True,
                    "action": "list",
                    **_client.pagination_meta(len(rows), assets_result.get("total", len(rows)), limit, offset),
                    "assets": rows,
                }
            
            elif action == "update":
                if not asset_id:
                    return {"success": False, "error": "asset_id is required for update action"}
                if not asset_data and not extra_fields:
                    return {"success": False, "error": "asset_data or extra_fields is required for update action"}

                api = _client.get_direct_api()

                # Build update payload from standard fields
                payload = {}
                if asset_data:
                    payload.update({k: v for k, v in asset_data.model_dump().items() if v is not None})

                # Validate and merge extra_fields
                if extra_fields:
                    # Extra GET to discover valid custom fields from the asset's model fieldset.
                    # Adds one round-trip but prevents silent field name typos.
                    current_asset = api._request("GET", f"hardware/{asset_id}")

                    valid_standard = HARDWARE_STANDARD_FIELDS

                    # Extract valid custom field db_columns from asset
                    valid_custom = set()
                    custom_fields_info = current_asset.get("custom_fields", {})
                    if isinstance(custom_fields_info, dict):
                        for field_info in custom_fields_info.values():
                            if isinstance(field_info, dict) and "field" in field_info:
                                db_col = field_info["field"]
                                if db_col:
                                    valid_custom.add(db_col)

                    all_valid = valid_standard | valid_custom
                    invalid_fields = set(extra_fields.keys()) - all_valid

                    if invalid_fields:
                        return {
                            "success": False,
                            "error": f"Unknown fields: {sorted(invalid_fields)}. "
                                     f"Available standard fields: {sorted(valid_standard)}. "
                                     f"Available custom fields: {sorted(valid_custom)}"
                        }

                    payload.update(extra_fields)

                if not payload:
                    return {"success": False, "error": "No fields to update (all values are None)"}

                result = api._request("PATCH", f"hardware/{asset_id}", json=payload)
                return {
                    "success": True,
                    "action": "update",
                    "asset": result
                }
            
            elif action == "delete":
                if not asset_id:
                    return {"success": False, "error": "asset_id is required for delete action"}
                
                client.assets.delete(asset_id)
                
                return {
                    "success": True,
                    "action": "delete",
                    "asset_id": asset_id,
                    "message": "Asset deleted successfully"
                }
            
    except SnipeITNotFoundError as e:
        logger.error(f"Asset not found: {e}")
        return {"success": False, "error": f"Asset not found: {str(e)}"}
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
        logger.error(f"Unexpected error in manage_assets: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    }
)
def asset_operations(
    action: Annotated[
        Literal["checkout", "checkin", "audit", "restore"],
        "The operation to perform on the asset"
    ],
    asset_id: Annotated[int, "Asset ID"],
    checkout_data: Annotated[CheckoutData | None, "Checkout details (required for checkout action)"] = None,
    checkin_data: Annotated[CheckinData | None, "Checkin details (optional for checkin action)"] = None,
    audit_data: Annotated[AuditData | None, "Audit details (optional for audit action)"] = None,
) -> dict[str, Any]:
    """Perform state operations on assets (checkout, checkin, audit, restore).
    
    Operations:
    - checkout: Check out an asset to a user, location, or another asset
    - checkin: Check in an asset back to inventory
    - audit: Mark an asset as audited
    - restore: Restore a soft-deleted asset
    
    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        client = _client.get_snipeit_client()
        
        with client:
            asset = client.assets.get(asset_id)
            
            if action == "checkout":
                if not checkout_data:
                    return {"success": False, "error": "checkout_data is required for checkout action"}
                
                # Build checkout kwargs
                checkout_kwargs = {
                    "checkout_to_type": checkout_data.checkout_to_type,
                    "assigned_to_id": checkout_data.assigned_to_id,
                }
                
                if checkout_data.expected_checkin:
                    checkout_kwargs["expected_checkin"] = checkout_data.expected_checkin
                if checkout_data.checkout_at:
                    checkout_kwargs["checkout_at"] = checkout_data.checkout_at
                if checkout_data.note:
                    checkout_kwargs["note"] = checkout_data.note
                if checkout_data.name:
                    checkout_kwargs["name"] = checkout_data.name
                
                updated_asset = asset.checkout(**checkout_kwargs)
                
                return {
                    "success": True,
                    "action": "checkout",
                    "asset_id": asset_id,
                    "message": f"Asset checked out to {checkout_data.checkout_to_type} {checkout_data.assigned_to_id}",
                    "asset": {
                        "id": updated_asset.id,
                        "asset_tag": getattr(updated_asset, "asset_tag", None),
                        "assigned_to": getattr(updated_asset, "assigned_to", None),
                    }
                }
            
            elif action == "checkin":
                checkin_kwargs = {}
                if checkin_data:
                    if checkin_data.note:
                        checkin_kwargs["note"] = checkin_data.note
                    if checkin_data.location_id:
                        checkin_kwargs["location_id"] = checkin_data.location_id
                
                updated_asset = asset.checkin(**checkin_kwargs)
                
                return {
                    "success": True,
                    "action": "checkin",
                    "asset_id": asset_id,
                    "message": "Asset checked in successfully",
                    "asset": {
                        "id": updated_asset.id,
                        "asset_tag": getattr(updated_asset, "asset_tag", None),
                    }
                }
            
            elif action == "audit":
                audit_kwargs = {}
                if audit_data:
                    if audit_data.location_id:
                        audit_kwargs["location_id"] = audit_data.location_id
                    if audit_data.note:
                        audit_kwargs["note"] = audit_data.note
                    if audit_data.next_audit_date:
                        audit_kwargs["next_audit_date"] = audit_data.next_audit_date
                
                updated_asset = asset.audit(**audit_kwargs)
                
                return {
                    "success": True,
                    "action": "audit",
                    "asset_id": asset_id,
                    "message": "Asset audited successfully",
                    "asset": {
                        "id": updated_asset.id,
                        "asset_tag": getattr(updated_asset, "asset_tag", None),
                    }
                }
            
            elif action == "restore":
                updated_asset = asset.restore()
                
                return {
                    "success": True,
                    "action": "restore",
                    "asset_id": asset_id,
                    "message": "Asset restored successfully",
                    "asset": {
                        "id": updated_asset.id,
                        "asset_tag": getattr(updated_asset, "asset_tag", None),
                    }
                }
    
    except SnipeITNotFoundError as e:
        logger.error(f"Asset not found: {e}")
        return {"success": False, "error": f"Asset not found: {str(e)}"}
    except SnipeITException as e:
        logger.error(f"Snipe-IT error: {e}")
        return {"success": False, "error": f"Snipe-IT error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error in asset_operations: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def asset_files(
    action: Annotated[
        Literal["upload", "list", "download", "delete"],
        "The file operation to perform"
    ],
    asset_id: Annotated[int, "Asset ID"],
    file_paths: Annotated[list[str] | None, "List of file paths to upload (for upload action)"] = None,
    notes: Annotated[str | None, "Notes for uploaded files (for upload action)"] = None,
    file_id: Annotated[int | None, "File ID (required for download and delete actions)"] = None,
    save_path: Annotated[str | None, "Path to save downloaded file (for download action)"] = None,
) -> dict[str, Any]:
    """Manage file attachments for assets.
    
    Operations:
    - upload: Upload one or more files to an asset
    - list: List all files attached to an asset
    - download: Download a specific file from an asset
    - delete: Delete a specific file from an asset
    
    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        client = _client.get_snipeit_client()
        
        with client:
            if action == "upload":
                if not file_paths:
                    return {"success": False, "error": "file_paths is required for upload action"}
                
                result = client.assets.upload_files(asset_id, file_paths, notes)
                
                return {
                    "success": True,
                    "action": "upload",
                    "asset_id": asset_id,
                    "message": f"Uploaded {len(file_paths)} file(s) successfully",
                    "result": result
                }
            
            elif action == "list":
                result = client.assets.list_files(asset_id)
                
                return {
                    "success": True,
                    "action": "list",
                    "asset_id": asset_id,
                    "files": result
                }
            
            elif action == "download":
                if file_id is None:
                    return {"success": False, "error": "file_id is required for download action"}
                if not save_path:
                    return {"success": False, "error": "save_path is required for download action"}
                
                downloaded_path = client.assets.download_file(asset_id, file_id, save_path)
                
                return {
                    "success": True,
                    "action": "download",
                    "asset_id": asset_id,
                    "file_id": file_id,
                    "saved_to": downloaded_path,
                    "message": f"File downloaded to {downloaded_path}"
                }
            
            elif action == "delete":
                if file_id is None:
                    return {"success": False, "error": "file_id is required for delete action"}
                
                client.assets.delete_file(asset_id, file_id)
                
                return {
                    "success": True,
                    "action": "delete",
                    "asset_id": asset_id,
                    "file_id": file_id,
                    "message": "File deleted successfully"
                }
    
    except SnipeITNotFoundError as e:
        logger.error(f"Asset or file not found: {e}")
        return {"success": False, "error": f"Not found: {str(e)}"}
    except SnipeITException as e:
        logger.error(f"Snipe-IT error: {e}")
        return {"success": False, "error": f"Snipe-IT error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error in asset_files: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    }
)
def asset_labels(
    asset_ids: Annotated[list[int] | None, "List of asset IDs to generate labels for"] = None,
    asset_tags: Annotated[list[str] | None, "List of asset tags to generate labels for"] = None,
    save_path: Annotated[str, "Path where the PDF labels file should be saved"] = "/tmp/asset_labels.pdf",
) -> dict[str, Any]:
    """Generate printable labels for assets.
    
    Provide either asset_ids or asset_tags to generate labels for specific assets.
    The labels will be saved as a PDF file to the specified save_path.
    
    Returns:
        dict: Result with path to generated labels PDF
    """
    try:
        client = _client.get_snipeit_client()
        
        if not asset_ids and not asset_tags:
            return {
                "success": False,
                "error": "Either asset_ids or asset_tags must be provided"
            }
        
        with client:
            # If asset_ids provided, get the Asset objects
            if asset_ids:
                assets = [client.assets.get(asset_id) for asset_id in asset_ids]
                saved_path = client.assets.labels(save_path, assets)
            else:
                # Use asset_tags directly
                saved_path = client.assets.labels(save_path, asset_tags)
            
            return {
                "success": True,
                "action": "generate_labels",
                "saved_to": saved_path,
                "message": f"Labels generated and saved to {saved_path}"
            }
    
    except SnipeITNotFoundError as e:
        logger.error(f"Asset not found: {e}")
        return {"success": False, "error": f"Asset not found: {str(e)}"}
    except SnipeITException as e:
        logger.error(f"Snipe-IT error: {e}")
        return {"success": False, "error": f"Snipe-IT error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error in asset_labels: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    }
)
def asset_maintenance(
    action: Annotated[
        Literal["create"],
        "The maintenance operation to perform (currently only create is supported)"
    ],
    asset_id: Annotated[int, "Asset ID"],
    maintenance_data: Annotated[MaintenanceData, "Maintenance record data (required for create action)"],
) -> dict[str, Any]:
    """Manage maintenance records for assets.
    
    Currently supports:
    - create: Create a new maintenance record for an asset
    
    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        client = _client.get_snipeit_client()
        
        with client:
            if action == "create":
                # Build maintenance payload
                maintenance_kwargs = {
                    "asset_id": asset_id,
                    "asset_improvement": maintenance_data.asset_improvement,
                    "supplier_id": maintenance_data.supplier_id,
                    "title": maintenance_data.title,
                }
                
                if maintenance_data.cost is not None:
                    maintenance_kwargs["cost"] = maintenance_data.cost
                if maintenance_data.start_date:
                    maintenance_kwargs["start_date"] = maintenance_data.start_date
                if maintenance_data.completion_date:
                    maintenance_kwargs["completion_date"] = maintenance_data.completion_date
                if maintenance_data.notes:
                    maintenance_kwargs["notes"] = maintenance_data.notes
                
                result = client.assets.create_maintenance(**maintenance_kwargs)
                
                return {
                    "success": True,
                    "action": "create",
                    "asset_id": asset_id,
                    "message": "Maintenance record created successfully",
                    "maintenance": result
                }
    
    except SnipeITNotFoundError as e:
        logger.error(f"Asset not found: {e}")
        return {"success": False, "error": f"Asset not found: {str(e)}"}
    except SnipeITException as e:
        logger.error(f"Snipe-IT error: {e}")
        return {"success": False, "error": f"Snipe-IT error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error in asset_maintenance: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
def asset_licenses(
    asset_id: Annotated[int, "Asset ID"],
) -> dict[str, Any]:
    """Get all licenses checked out to an asset.
    
    Returns:
        dict: List of licenses associated with the asset
    """
    try:
        client = _client.get_snipeit_client()
        
        with client:
            result = client.assets.get_licenses(asset_id)
            
            return {
                "success": True,
                "asset_id": asset_id,
                "licenses": result
            }
    
    except SnipeITNotFoundError as e:
        logger.error(f"Asset not found: {e}")
        return {"success": False, "error": f"Asset not found: {str(e)}"}
    except SnipeITException as e:
        logger.error(f"Snipe-IT error: {e}")
        return {"success": False, "error": f"Snipe-IT error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error in asset_licenses: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}




@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    }
)
def asset_requests(
    action: Annotated[
        Literal["request", "cancel"],
        "The request action to perform"
    ],
    asset_id: Annotated[int, "Asset ID (must be a requestable asset)"],
    request_data: Annotated[AssetRequestData | None, "Request details (for request action)"] = None,
) -> dict[str, Any]:
    """Manage asset checkout requests.

    Allows users to request checkout of requestable assets. Assets must have
    the 'requestable' flag set (either on the asset or its model).

    Operations:
    - request: Submit a request to checkout an asset
    - cancel: Cancel a pending request

    Note: Viewing the request queue and approving/denying requests is only
    available through the web UI - there are no API endpoints for these
    administrative functions.

    Returns:
        dict: Result of the operation including success status
    """
    try:
        api = _client.get_direct_api()

        if action == "request":
            payload = {}
            if request_data:
                if request_data.expected_checkout:
                    payload["expected_checkout"] = request_data.expected_checkout
                if request_data.note:
                    payload["note"] = request_data.note

            result = api._request("POST", f"hardware/{asset_id}/request", json=payload if payload else None)

            return {
                "success": True,
                "action": "request",
                "asset_id": asset_id,
                "message": "Checkout request submitted",
                "result": result
            }

        elif action == "cancel":
            result = api._request("POST", f"hardware/{asset_id}/request/cancel")

            return {
                "success": True,
                "action": "cancel",
                "asset_id": asset_id,
                "message": "Checkout request cancelled",
                "result": result
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Asset not found: {e}")
        return {"success": False, "error": f"Asset not found: {str(e)}"}
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
        logger.error(f"Unexpected error in asset_requests: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


