"""Snipe-IT license tools: licenses, license seats, license file attachments."""

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
from ..schemas import LicenseData, LicenseSeatCheckout

logger = logging.getLogger(__name__)


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
        api = _client.get_direct_api()

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
        api = _client.get_direct_api()

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
        api = _client.get_direct_api()

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
                    "Authorization": f"Bearer {_client.SNIPEIT_TOKEN}",
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
                "Authorization": f"Bearer {_client.SNIPEIT_TOKEN}",
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


