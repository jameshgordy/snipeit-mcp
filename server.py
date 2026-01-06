"""Snipe-IT MCP Server

A Model Context Protocol (MCP) server for managing Snipe-IT inventory.
Provides tools for CRUD operations on:
- Assets (manage_assets, asset_operations, asset_files, asset_labels, asset_maintenance, asset_licenses)
- Licenses (manage_licenses, license_seats, license_files)
- Accessories (manage_accessories, accessory_operations)
- Consumables (manage_consumables)
- Categories (manage_categories)
- Manufacturers (manage_manufacturers)
- Models (manage_models)
- Status Labels (manage_status_labels)
- Locations (manage_locations)
- Suppliers (manage_suppliers)
- Depreciations (manage_depreciations)
"""

import os
import logging
from typing import Literal, Annotated, Any
from pydantic import BaseModel, Field
import requests

from fastmcp import FastMCP
from snipeit import SnipeIT
from snipeit.exceptions import (
    SnipeITException,
    SnipeITNotFoundError,
    SnipeITAuthenticationError,
    SnipeITValidationError
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP(
    name="Snipe-IT MCP Server"
)

# Get Snipe-IT configuration from environment variables
SNIPEIT_URL = os.getenv("SNIPEIT_URL")
SNIPEIT_TOKEN = os.getenv("SNIPEIT_TOKEN")

if not SNIPEIT_URL or not SNIPEIT_TOKEN:
    logger.warning(
        "SNIPEIT_URL and SNIPEIT_TOKEN environment variables must be set. "
        "Server will start but tools will fail until these are configured."
    )

# Initialize Snipe-IT client (will be used in tools)
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
        """List resources with pagination."""
        params = {"limit": limit, "offset": offset}
        if search:
            params["search"] = search
        if sort:
            params["sort"] = sort
        if order:
            params["order"] = order

        data = self._request("GET", endpoint, params=params)
        return data.get("rows", [])

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


# ============================================================================
# Pydantic Models for Tool Input/Output
# ============================================================================

class AssetData(BaseModel):
    """Model for asset data used in create/update operations."""
    status_id: int | None = Field(None, description="ID of the status label")
    model_id: int | None = Field(None, description="ID of the asset model")
    asset_tag: str | None = Field(None, description="Asset tag identifier")
    name: str | None = Field(None, description="Asset name")
    serial: str | None = Field(None, description="Serial number")
    purchase_date: str | None = Field(None, description="Purchase date (YYYY-MM-DD)")
    purchase_cost: float | None = Field(None, description="Purchase cost")
    order_number: str | None = Field(None, description="Order number")
    notes: str | None = Field(None, description="Additional notes")
    warranty_months: int | None = Field(None, description="Warranty period in months")
    location_id: int | None = Field(None, description="Location ID")
    rtd_location_id: int | None = Field(None, description="Default location ID")
    supplier_id: int | None = Field(None, description="Supplier ID")
    company_id: int | None = Field(None, description="Company ID")
    requestable: bool | None = Field(None, description="Whether asset is requestable")


class CheckoutData(BaseModel):
    """Model for asset checkout operations."""
    checkout_to_type: Literal["user", "asset", "location"] = Field(
        ..., 
        description="Type of entity to checkout to"
    )
    assigned_to_id: int = Field(..., description="ID of the user/asset/location")
    expected_checkin: str | None = Field(None, description="Expected checkin date (YYYY-MM-DD)")
    checkout_at: str | None = Field(None, description="Checkout date (YYYY-MM-DD)")
    note: str | None = Field(None, description="Checkout notes")
    name: str | None = Field(None, description="Name for the checkout")


class CheckinData(BaseModel):
    """Model for asset checkin operations."""
    note: str | None = Field(None, description="Checkin notes")
    location_id: int | None = Field(None, description="Location ID to checkin to")


class AuditData(BaseModel):
    """Model for asset audit operations."""
    location_id: int | None = Field(None, description="Location ID")
    note: str | None = Field(None, description="Audit notes")
    next_audit_date: str | None = Field(None, description="Next audit date (YYYY-MM-DD)")


class MaintenanceData(BaseModel):
    """Model for asset maintenance records."""
    asset_improvement: str = Field(..., description="Type of maintenance/improvement")
    supplier_id: int = Field(..., description="Supplier ID")
    title: str = Field(..., description="Maintenance title")
    cost: float | None = Field(None, description="Maintenance cost")
    start_date: str | None = Field(None, description="Start date (YYYY-MM-DD)")
    completion_date: str | None = Field(None, description="Completion date (YYYY-MM-DD)")
    notes: str | None = Field(None, description="Maintenance notes")


class ConsumableData(BaseModel):
    """Model for consumable data used in create/update operations."""
    name: str | None = Field(None, description="Consumable name")
    qty: int | None = Field(None, description="Quantity")
    category_id: int | None = Field(None, description="Category ID")
    company_id: int | None = Field(None, description="Company ID")
    location_id: int | None = Field(None, description="Location ID")
    manufacturer_id: int | None = Field(None, description="Manufacturer ID")
    model_number: str | None = Field(None, description="Model number")
    item_no: str | None = Field(None, description="Item number")
    order_number: str | None = Field(None, description="Order number")
    purchase_date: str | None = Field(None, description="Purchase date (YYYY-MM-DD)")
    purchase_cost: float | None = Field(None, description="Purchase cost")
    min_amt: int | None = Field(None, description="Minimum quantity threshold")
    notes: str | None = Field(None, description="Additional notes")


class CategoryData(BaseModel):
    """Model for category data used in create/update operations."""
    name: str | None = Field(None, description="Category name")
    category_type: Literal["asset", "accessory", "consumable", "component", "license"] | None = Field(
        None, description="Type of category"
    )
    eula_text: str | None = Field(None, description="EULA text for this category")
    use_default_eula: bool | None = Field(None, description="Use default EULA")
    require_acceptance: bool | None = Field(None, description="Require users to accept EULA")
    checkin_email: bool | None = Field(None, description="Send email on checkin")
    image: str | None = Field(None, description="Image filename")


class ManufacturerData(BaseModel):
    """Model for manufacturer data used in create/update operations."""
    name: str | None = Field(None, description="Manufacturer name")
    url: str | None = Field(None, description="Manufacturer URL")
    support_url: str | None = Field(None, description="Support URL")
    support_phone: str | None = Field(None, description="Support phone number")
    support_email: str | None = Field(None, description="Support email address")
    image: str | None = Field(None, description="Image filename")


class AssetModelData(BaseModel):
    """Model for asset model data used in create/update operations."""
    name: str | None = Field(None, description="Model name")
    model_number: str | None = Field(None, description="Model number")
    manufacturer_id: int | None = Field(None, description="Manufacturer ID")
    category_id: int | None = Field(None, description="Category ID")
    eol: int | None = Field(None, description="End of life in months")
    depreciation_id: int | None = Field(None, description="Depreciation ID")
    notes: str | None = Field(None, description="Additional notes")
    fieldset_id: int | None = Field(None, description="Custom fieldset ID")
    requestable: bool | None = Field(None, description="Whether assets of this model are requestable")
    image: str | None = Field(None, description="Image filename")


class StatusLabelData(BaseModel):
    """Model for status label data used in create/update operations."""
    name: str | None = Field(None, description="Status label name")
    type: Literal["deployable", "pending", "archived", "undeployable"] | None = Field(
        None, description="Status type"
    )
    color: str | None = Field(None, description="Color hex code (e.g., #ff0000)")
    show_in_nav: bool | None = Field(None, description="Show in navigation")
    default_label: bool | None = Field(None, description="Use as default status")
    notes: str | None = Field(None, description="Additional notes")


class LocationData(BaseModel):
    """Model for location data used in create/update operations."""
    name: str | None = Field(None, description="Location name")
    address: str | None = Field(None, description="Street address")
    address2: str | None = Field(None, description="Address line 2")
    city: str | None = Field(None, description="City")
    state: str | None = Field(None, description="State/Province")
    country: str | None = Field(None, description="Country (2-letter ISO code)")
    zip: str | None = Field(None, description="ZIP/Postal code")
    ldap_ou: str | None = Field(None, description="LDAP OU")
    manager_id: int | None = Field(None, description="Manager user ID")
    parent_id: int | None = Field(None, description="Parent location ID")
    currency: str | None = Field(None, description="Currency code (e.g., USD)")
    image: str | None = Field(None, description="Image filename")


class SupplierData(BaseModel):
    """Model for supplier data used in create/update operations."""
    name: str | None = Field(None, description="Supplier name")
    address: str | None = Field(None, description="Street address")
    address2: str | None = Field(None, description="Address line 2")
    city: str | None = Field(None, description="City")
    state: str | None = Field(None, description="State/Province")
    country: str | None = Field(None, description="Country (2-letter ISO code)")
    zip: str | None = Field(None, description="ZIP/Postal code")
    phone: str | None = Field(None, description="Phone number")
    fax: str | None = Field(None, description="Fax number")
    email: str | None = Field(None, description="Email address")
    contact: str | None = Field(None, description="Contact person name")
    url: str | None = Field(None, description="Website URL")
    notes: str | None = Field(None, description="Additional notes")
    image: str | None = Field(None, description="Image filename")


class DepreciationData(BaseModel):
    """Model for depreciation data used in create/update operations."""
    name: str | None = Field(None, description="Depreciation name (e.g., 'Computer Equipment (3 Years)')")
    months: int | None = Field(None, description="Depreciation period in months")


class LicenseData(BaseModel):
    """Model for license data used in create/update operations."""
    name: str | None = Field(None, description="License name")
    seats: int | None = Field(None, description="Number of seats/installations allowed")
    category_id: int | None = Field(None, description="Category ID")
    company_id: int | None = Field(None, description="Company ID")
    manufacturer_id: int | None = Field(None, description="Manufacturer ID")
    serial: str | None = Field(None, description="License key/serial number")
    purchase_date: str | None = Field(None, description="Purchase date (YYYY-MM-DD)")
    purchase_cost: float | None = Field(None, description="Purchase cost")
    expiration_date: str | None = Field(None, description="Expiration date (YYYY-MM-DD)")
    license_name: str | None = Field(None, description="Licensed to name")
    license_email: str | None = Field(None, description="Licensed to email")
    maintained: bool | None = Field(None, description="Whether license has maintenance/support")
    reassignable: bool | None = Field(None, description="Whether license can be reassigned")
    notes: str | None = Field(None, description="Additional notes")
    order_number: str | None = Field(None, description="Order number")
    supplier_id: int | None = Field(None, description="Supplier ID")
    termination_date: str | None = Field(None, description="Termination date (YYYY-MM-DD)")


class LicenseSeatCheckout(BaseModel):
    """Model for license seat checkout operations."""
    assigned_to: int | None = Field(None, description="User ID to assign the seat to")
    asset_id: int | None = Field(None, description="Asset ID to assign the seat to")
    note: str | None = Field(None, description="Checkout notes")


class AccessoryData(BaseModel):
    """Model for accessory data used in create/update operations."""
    name: str | None = Field(None, description="Accessory name")
    qty: int | None = Field(None, description="Total quantity available")
    category_id: int | None = Field(None, description="Category ID (must be accessory-type)")
    manufacturer_id: int | None = Field(None, description="Manufacturer ID")
    supplier_id: int | None = Field(None, description="Supplier ID")
    location_id: int | None = Field(None, description="Location ID")
    company_id: int | None = Field(None, description="Company ID")
    model_number: str | None = Field(None, description="Model number")
    order_number: str | None = Field(None, description="Order number")
    purchase_cost: float | None = Field(None, description="Purchase cost")
    purchase_date: str | None = Field(None, description="Purchase date (YYYY-MM-DD)")
    min_amt: int | None = Field(None, description="Minimum quantity threshold for reorder alerts")
    notes: str | None = Field(None, description="Additional notes")


class AccessoryCheckout(BaseModel):
    """Model for accessory checkout operations."""
    assigned_to: int | None = Field(None, description="User ID to checkout to")
    note: str | None = Field(None, description="Checkout notes")


# ============================================================================
# Asset Tools
# ============================================================================

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
    asset_data: Annotated[AssetData | None, "Asset data (required for create, optional for update)"] = None,
    limit: Annotated[int | None, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int | None, "Number of results to skip (for list action)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action)"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT assets with CRUD operations.
    
    This tool handles all basic asset operations:
    - create: Create a new asset (requires asset_data with at least status_id and model_id)
    - get: Retrieve a single asset by ID, asset_tag, or serial number
    - list: List assets with optional pagination and filtering
    - update: Update an existing asset (requires asset_id and asset_data)
    - delete: Delete an asset (requires asset_id)
    
    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        client = get_snipeit_client()
        
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
                create_kwargs = {k: v for k, v in asset_data.model_dump().items() if v is not None}
                asset = client.assets.create(**create_kwargs)
                
                return {
                    "success": True,
                    "action": "create",
                    "asset": {
                        "id": asset.id,
                        "asset_tag": getattr(asset, "asset_tag", None),
                        "name": getattr(asset, "name", None),
                        "serial": getattr(asset, "serial", None),
                    }
                }
            
            elif action == "get":
                if asset_tag:
                    asset = client.assets.get_by_tag(asset_tag)
                elif serial:
                    asset = client.assets.get_by_serial(serial)
                elif asset_id:
                    asset = client.assets.get(asset_id)
                else:
                    return {
                        "success": False,
                        "error": "One of asset_id, asset_tag, or serial is required for get action"
                    }
                
                # Extract asset data
                asset_dict = {
                    "id": asset.id,
                    "asset_tag": getattr(asset, "asset_tag", None),
                    "name": getattr(asset, "name", None),
                    "serial": getattr(asset, "serial", None),
                    "model": getattr(asset, "model", None),
                    "status_label": getattr(asset, "status_label", None),
                    "category": getattr(asset, "category", None),
                    "manufacturer": getattr(asset, "manufacturer", None),
                    "supplier": getattr(asset, "supplier", None),
                    "notes": getattr(asset, "notes", None),
                    "location": getattr(asset, "location", None),
                    "assigned_to": getattr(asset, "assigned_to", None),
                    "purchase_date": getattr(asset, "purchase_date", None),
                    "purchase_cost": getattr(asset, "purchase_cost", None),
                }
                
                return {
                    "success": True,
                    "action": "get",
                    "asset": asset_dict
                }
            
            elif action == "list":
                params = {"limit": limit, "offset": offset}
                if search:
                    params["search"] = search
                if sort:
                    params["sort"] = sort
                if order:
                    params["order"] = order
                
                assets = client.assets.list(**params)
                
                assets_list = [
                    {
                        "id": asset.id,
                        "asset_tag": getattr(asset, "asset_tag", None),
                        "name": getattr(asset, "name", None),
                        "serial": getattr(asset, "serial", None),
                        "model": getattr(asset, "model", {}).get("name") if hasattr(asset, "model") and isinstance(getattr(asset, "model", None), dict) else None,
                    }
                    for asset in assets
                ]
                
                return {
                    "success": True,
                    "action": "list",
                    "count": len(assets_list),
                    "assets": assets_list
                }
            
            elif action == "update":
                if not asset_id:
                    return {"success": False, "error": "asset_id is required for update action"}
                if not asset_data:
                    return {"success": False, "error": "asset_data is required for update action"}
                
                # Build update payload (only include non-None values)
                update_kwargs = {k: v for k, v in asset_data.model_dump().items() if v is not None}
                
                asset = client.assets.patch(asset_id, **update_kwargs)
                
                return {
                    "success": True,
                    "action": "update",
                    "asset": {
                        "id": asset.id,
                        "asset_tag": getattr(asset, "asset_tag", None),
                        "name": getattr(asset, "name", None),
                    }
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
        client = get_snipeit_client()
        
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
        client = get_snipeit_client()
        
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
        client = get_snipeit_client()
        
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
        client = get_snipeit_client()
        
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
        client = get_snipeit_client()
        
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


# ============================================================================
# Consumable Tools
# ============================================================================

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
    limit: Annotated[int | None, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int | None, "Number of results to skip (for list action)"] = 0,
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
        client = get_snipeit_client()
        
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
                if sort:
                    params["sort"] = sort
                if order:
                    params["order"] = order
                
                consumables = client.consumables.list(**params)
                
                consumables_list = [
                    {
                        "id": consumable.id,
                        "name": getattr(consumable, "name", None),
                        "qty": getattr(consumable, "qty", None),
                        "remaining": getattr(consumable, "remaining", None),
                    }
                    for consumable in consumables
                ]
                
                return {
                    "success": True,
                    "action": "list",
                    "count": len(consumables_list),
                    "consumables": consumables_list
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


# ============================================================================
# Foundational Entity Tools
# ============================================================================

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
    limit: Annotated[int | None, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int | None, "Number of results to skip (for list action)"] = 0,
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
        client = get_snipeit_client()

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
                if sort:
                    params["sort"] = sort
                if order:
                    params["order"] = order

                categories = client.categories.list(**params)

                categories_list = [
                    {
                        "id": cat.id,
                        "name": getattr(cat, "name", None),
                        "category_type": getattr(cat, "category_type", None),
                        "assets_count": getattr(cat, "assets_count", None),
                    }
                    for cat in categories
                ]

                return {
                    "success": True,
                    "action": "list",
                    "count": len(categories_list),
                    "categories": categories_list
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
    limit: Annotated[int | None, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int | None, "Number of results to skip (for list action)"] = 0,
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
        client = get_snipeit_client()

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
                if sort:
                    params["sort"] = sort
                if order:
                    params["order"] = order

                manufacturers = client.manufacturers.list(**params)

                manufacturers_list = [
                    {
                        "id": mfr.id,
                        "name": getattr(mfr, "name", None),
                        "assets_count": getattr(mfr, "assets_count", None),
                    }
                    for mfr in manufacturers
                ]

                return {
                    "success": True,
                    "action": "list",
                    "count": len(manufacturers_list),
                    "manufacturers": manufacturers_list
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
        Literal["create", "get", "list", "update", "delete"],
        "The action to perform on asset models"
    ],
    model_id: Annotated[int | None, "Model ID (required for get, update, delete)"] = None,
    model_data: Annotated[AssetModelData | None, "Model data (required for create, optional for update)"] = None,
    limit: Annotated[int | None, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int | None, "Number of results to skip (for list action)"] = 0,
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

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        client = get_snipeit_client()

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
                if sort:
                    params["sort"] = sort
                if order:
                    params["order"] = order

                models = client.models.list(**params)

                models_list = [
                    {
                        "id": m.id,
                        "name": getattr(m, "name", None),
                        "model_number": getattr(m, "model_number", None),
                        "manufacturer": getattr(m, "manufacturer", {}).get("name") if hasattr(m, "manufacturer") and isinstance(getattr(m, "manufacturer", None), dict) else None,
                        "assets_count": getattr(m, "assets_count", None),
                    }
                    for m in models
                ]

                return {
                    "success": True,
                    "action": "list",
                    "count": len(models_list),
                    "models": models_list
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
        Literal["create", "get", "list", "update", "delete"],
        "The action to perform on status labels"
    ],
    status_label_id: Annotated[int | None, "Status label ID (required for get, update, delete)"] = None,
    status_label_data: Annotated[StatusLabelData | None, "Status label data (required for create, optional for update)"] = None,
    limit: Annotated[int | None, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int | None, "Number of results to skip (for list action)"] = 0,
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

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = get_direct_api()

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
            status_labels = api.list("statuslabels", limit=limit or 50, offset=offset or 0,
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
                "count": len(status_labels_list),
                "status_labels": status_labels_list
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
        Literal["create", "get", "list", "update", "delete"],
        "The action to perform on locations"
    ],
    location_id: Annotated[int | None, "Location ID (required for get, update, delete)"] = None,
    location_data: Annotated[LocationData | None, "Location data (required for create, optional for update)"] = None,
    limit: Annotated[int | None, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int | None, "Number of results to skip (for list action)"] = 0,
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

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        client = get_snipeit_client()

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
                if sort:
                    params["sort"] = sort
                if order:
                    params["order"] = order

                locations = client.locations.list(**params)

                locations_list = [
                    {
                        "id": loc.id,
                        "name": getattr(loc, "name", None),
                        "city": getattr(loc, "city", None),
                        "assets_count": getattr(loc, "assets_count", None),
                    }
                    for loc in locations
                ]

                return {
                    "success": True,
                    "action": "list",
                    "count": len(locations_list),
                    "locations": locations_list
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
    limit: Annotated[int | None, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int | None, "Number of results to skip (for list action)"] = 0,
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
        api = get_direct_api()

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
            suppliers = api.list("suppliers", limit=limit or 50, offset=offset or 0,
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
                "count": len(suppliers_list),
                "suppliers": suppliers_list
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
    limit: Annotated[int | None, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int | None, "Number of results to skip (for list action)"] = 0,
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
        api = get_direct_api()

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
            depreciations = api.list("depreciations", limit=limit or 50, offset=offset or 0,
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
                "count": len(depreciations_list),
                "depreciations": depreciations_list
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


# ============================================================================
# License Tools
# ============================================================================

@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_licenses(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete"],
        "The action to perform on licenses"
    ],
    license_id: Annotated[int | None, "License ID (required for get, update, delete)"] = None,
    license_data: Annotated[LicenseData | None, "License data (required for create, optional for update)"] = None,
    limit: Annotated[int | None, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int | None, "Number of results to skip (for list action)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action)"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT licenses with CRUD operations.

    Licenses track software licenses with seat-based allocation.

    Operations:
    - create: Create a new license (requires license_data with name and seats)
    - get: Retrieve a single license by ID
    - list: List licenses with optional pagination and filtering
    - update: Update an existing license (requires license_id and license_data)
    - delete: Delete a license (requires license_id)

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = get_direct_api()

        if action == "create":
            if not license_data:
                return {"success": False, "error": "license_data is required for create action"}

            if not license_data.name or license_data.seats is None:
                return {
                    "success": False,
                    "error": "name and seats are required to create a license"
                }

            create_data = {k: v for k, v in license_data.model_dump().items() if v is not None}
            result = api.create("licenses", create_data)

            return {
                "success": True,
                "action": "create",
                "license": {
                    "id": result.get("payload", result).get("id"),
                    "name": result.get("payload", result).get("name"),
                    "seats": result.get("payload", result).get("seats"),
                }
            }

        elif action == "get":
            if not license_id:
                return {"success": False, "error": "license_id is required for get action"}

            license_obj = api.get("licenses", license_id)

            return {
                "success": True,
                "action": "get",
                "license": {
                    "id": license_obj.get("id"),
                    "name": license_obj.get("name"),
                    "seats": license_obj.get("seats"),
                    "free_seats_count": license_obj.get("free_seats_count"),
                    "serial": license_obj.get("serial"),
                    "category": license_obj.get("category"),
                    "company": license_obj.get("company"),
                    "manufacturer": license_obj.get("manufacturer"),
                    "supplier": license_obj.get("supplier"),
                    "purchase_date": license_obj.get("purchase_date"),
                    "purchase_cost": license_obj.get("purchase_cost"),
                    "expiration_date": license_obj.get("expiration_date"),
                    "license_name": license_obj.get("license_name"),
                    "license_email": license_obj.get("license_email"),
                    "maintained": license_obj.get("maintained"),
                    "reassignable": license_obj.get("reassignable"),
                    "notes": license_obj.get("notes"),
                }
            }

        elif action == "list":
            licenses = api.list("licenses", limit=limit or 50, offset=offset or 0,
                               search=search, sort=sort, order=order)

            licenses_list = [
                {
                    "id": lic.get("id"),
                    "name": lic.get("name"),
                    "seats": lic.get("seats"),
                    "free_seats_count": lic.get("free_seats_count"),
                    "company": lic.get("company", {}).get("name") if isinstance(lic.get("company"), dict) else None,
                }
                for lic in licenses
            ]

            return {
                "success": True,
                "action": "list",
                "count": len(licenses_list),
                "licenses": licenses_list
            }

        elif action == "update":
            if not license_id:
                return {"success": False, "error": "license_id is required for update action"}
            if not license_data:
                return {"success": False, "error": "license_data is required for update action"}

            update_data = {k: v for k, v in license_data.model_dump().items() if v is not None}
            result = api.update("licenses", license_id, update_data)

            return {
                "success": True,
                "action": "update",
                "license": {
                    "id": result.get("payload", result).get("id"),
                    "name": result.get("payload", result).get("name"),
                }
            }

        elif action == "delete":
            if not license_id:
                return {"success": False, "error": "license_id is required for delete action"}

            api.delete("licenses", license_id)

            return {
                "success": True,
                "action": "delete",
                "license_id": license_id,
                "message": "License deleted successfully"
            }

    except SnipeITNotFoundError as e:
        logger.error(f"License not found: {e}")
        return {"success": False, "error": f"License not found: {str(e)}"}
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
        logger.error(f"Unexpected error in manage_licenses: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    }
)
def license_seats(
    action: Annotated[
        Literal["list", "checkout", "checkin"],
        "The action to perform on license seats"
    ],
    license_id: Annotated[int | None, "License ID (required for list and checkout)"] = None,
    seat_id: Annotated[int | None, "Seat ID (required for checkout and checkin)"] = None,
    checkout_data: Annotated[LicenseSeatCheckout | None, "Checkout data (required for checkout action)"] = None,
) -> dict[str, Any]:
    """Manage license seat checkouts and checkins.

    License seats can be assigned to users or assets.

    Operations:
    - list: List all seats for a license (requires license_id)
    - checkout: Checkout a seat to a user or asset (requires license_id, seat_id, and checkout_data)
    - checkin: Checkin a seat (requires seat_id)

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = get_direct_api()

        if action == "list":
            if not license_id:
                return {"success": False, "error": "license_id is required for list action"}

            result = api._request("GET", f"licenses/{license_id}/seats")
            seats = result.get("rows", [])

            seats_list = [
                {
                    "id": seat.get("id"),
                    "name": seat.get("name"),
                    "assigned_user": seat.get("assigned_user"),
                    "assigned_asset": seat.get("assigned_asset"),
                    "location": seat.get("location"),
                    "reassignable": seat.get("reassignable"),
                }
                for seat in seats
            ]

            return {
                "success": True,
                "action": "list",
                "license_id": license_id,
                "count": len(seats_list),
                "seats": seats_list
            }

        elif action == "checkout":
            if not license_id:
                return {"success": False, "error": "license_id is required for checkout action"}
            if not seat_id:
                return {"success": False, "error": "seat_id is required for checkout action"}
            if not checkout_data:
                return {"success": False, "error": "checkout_data is required for checkout action"}

            if not checkout_data.assigned_to and not checkout_data.asset_id:
                return {
                    "success": False,
                    "error": "Either assigned_to (user ID) or asset_id is required for checkout"
                }

            checkout_payload = {k: v for k, v in checkout_data.model_dump().items() if v is not None}
            result = api._request("POST", f"licenses/{license_id}/seats/{seat_id}/checkout", json=checkout_payload)

            return {
                "success": True,
                "action": "checkout",
                "license_id": license_id,
                "seat_id": seat_id,
                "message": "License seat checked out successfully",
                "result": result
            }

        elif action == "checkin":
            if not seat_id:
                return {"success": False, "error": "seat_id is required for checkin action"}

            result = api._request("POST", f"licenses/seats/{seat_id}/checkin")

            return {
                "success": True,
                "action": "checkin",
                "seat_id": seat_id,
                "message": "License seat checked in successfully",
                "result": result
            }

    except SnipeITNotFoundError as e:
        logger.error(f"License or seat not found: {e}")
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
        logger.error(f"Unexpected error in license_seats: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def license_files(
    action: Annotated[
        Literal["upload", "list", "download", "delete"],
        "The file operation to perform"
    ],
    license_id: Annotated[int, "License ID"],
    file_path: Annotated[str | None, "File path to upload (for upload action)"] = None,
    file_id: Annotated[int | None, "File ID (required for download and delete actions)"] = None,
    save_path: Annotated[str | None, "Path to save downloaded file (for download action)"] = None,
) -> dict[str, Any]:
    """Manage file attachments for licenses.

    Operations:
    - upload: Upload a file to a license
    - list: List all files attached to a license
    - download: Download a specific file from a license
    - delete: Delete a specific file from a license

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = get_direct_api()

        if action == "upload":
            if not file_path:
                return {"success": False, "error": "file_path is required for upload action"}

            # Read the file and upload it
            import os
            if not os.path.exists(file_path):
                return {"success": False, "error": f"File not found: {file_path}"}

            filename = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                files = {"file": (filename, f)}
                # Use a separate request without JSON content type for file upload
                url = f"{api.base_url}/api/v1/licenses/{license_id}/upload"
                headers = {
                    "Authorization": f"Bearer {SNIPEIT_TOKEN}",
                    "Accept": "application/json",
                }
                response = requests.post(url, headers=headers, files=files)
                response.raise_for_status()
                result = response.json()

            return {
                "success": True,
                "action": "upload",
                "license_id": license_id,
                "message": f"File '{filename}' uploaded successfully",
                "result": result
            }

        elif action == "list":
            result = api._request("GET", f"licenses/{license_id}/uploads")
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
                "license_id": license_id,
                "count": len(files_list),
                "files": files_list
            }

        elif action == "download":
            if file_id is None:
                return {"success": False, "error": "file_id is required for download action"}
            if not save_path:
                return {"success": False, "error": "save_path is required for download action"}

            # Get the file download URL and download
            url = f"{api.base_url}/api/v1/licenses/{license_id}/uploads/{file_id}"
            headers = {
                "Authorization": f"Bearer {SNIPEIT_TOKEN}",
                "Accept": "application/octet-stream",
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            # Save the file
            import os
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(response.content)

            return {
                "success": True,
                "action": "download",
                "license_id": license_id,
                "file_id": file_id,
                "saved_to": save_path,
                "message": f"File downloaded to {save_path}"
            }

        elif action == "delete":
            if file_id is None:
                return {"success": False, "error": "file_id is required for delete action"}

            api._request("DELETE", f"licenses/{license_id}/uploads/{file_id}")

            return {
                "success": True,
                "action": "delete",
                "license_id": license_id,
                "file_id": file_id,
                "message": "File deleted successfully"
            }

    except SnipeITNotFoundError as e:
        logger.error(f"License or file not found: {e}")
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
        logger.error(f"Unexpected error in license_files: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


# ============================================================================
# Accessory Tools
# ============================================================================

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
    limit: Annotated[int | None, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int | None, "Number of results to skip (for list action)"] = 0,
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
        api = get_direct_api()

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
            accessories = api.list("accessories", limit=limit or 50, offset=offset or 0,
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
                "count": len(accessories_list),
                "accessories": accessories_list
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

    Accessories can be checked out to users. Each checkout decrements the available
    quantity, and checkin increments it back.

    Operations:
    - checkout: Checkout an accessory to a user (requires checkout_data with assigned_to)
    - checkin: Checkin an accessory (requires checkout_id from the checkout record)
    - list_checkouts: List all users who have this accessory checked out

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = get_direct_api()

        if action == "checkout":
            if not checkout_data:
                return {"success": False, "error": "checkout_data is required for checkout action"}

            if not checkout_data.assigned_to:
                return {
                    "success": False,
                    "error": "assigned_to (user ID) is required for checkout"
                }

            checkout_payload = {k: v for k, v in checkout_data.model_dump().items() if v is not None}
            result = api._request("POST", f"accessories/{accessory_id}/checkout", json=checkout_payload)

            return {
                "success": True,
                "action": "checkout",
                "accessory_id": accessory_id,
                "message": f"Accessory checked out to user {checkout_data.assigned_to}",
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


# ============================================================================
# Server Entry Point
# ============================================================================

if __name__ == "__main__":
    # Run the server with stdio transport (default for MCP)
    mcp.run(transport="stdio")
