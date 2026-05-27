"""Snipe-IT import management tools: CSV import workflow (upload, map, process)."""

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
from ..schemas import ImportData

logger = logging.getLogger(__name__)


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_imports(
    action: Annotated[
        Literal["list", "get", "upload", "update", "delete", "process"],
        "The import action to perform"
    ],
    import_id: Annotated[int | None, "Import file ID (required for get, update, delete, process)"] = None,
    file_path: Annotated[str | None, "Path to CSV file (required for upload action)"] = None,
    import_data: Annotated[ImportData | None, "Import configuration (for update action)"] = None,
) -> dict[str, Any]:
    """Manage CSV import operations for bulk data import.

    The import workflow is: upload → update mappings → process

    Operations:
    - list: List all import files
    - get: Get import file details including column mappings
    - upload: Upload a CSV file for import
    - update: Update import column mappings and settings
    - delete: Delete an import file
    - process: Execute the import

    Common field mappings for assets:
    - asset_tag, name, serial, model_id, status_id
    - purchase_date, purchase_cost, order_number
    - notes, warranty_months, supplier_id
    - location_id, company_id, category_id

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = _client.get_direct_api()

        if action == "list":
            result = api._request("GET", "imports")
            imports = result.get("rows", [])

            return {
                "success": True,
                "action": "list",
                "count": len(imports),
                "imports": imports
            }

        elif action == "get":
            if not import_id:
                return {"success": False, "error": "import_id is required for get action"}

            result = api._request("GET", f"imports/{import_id}")

            return {
                "success": True,
                "action": "get",
                "import": result
            }

        elif action == "upload":
            if not file_path:
                return {"success": False, "error": "file_path is required for upload action"}

            import os
            if not os.path.exists(file_path):
                return {"success": False, "error": f"File not found: {file_path}"}

            filename = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                files = {"file": (filename, f, "text/csv")}
                url = f"{api.base_url}/api/v1/imports"
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
                "message": f"File '{filename}' uploaded successfully",
                "import": result
            }

        elif action == "update":
            if not import_id:
                return {"success": False, "error": "import_id is required for update action"}
            if not import_data:
                return {"success": False, "error": "import_data is required for update action"}

            update_payload = {k: v for k, v in import_data.model_dump().items() if v is not None}
            result = api._request("PATCH", f"imports/{import_id}", json=update_payload)

            return {
                "success": True,
                "action": "update",
                "import_id": import_id,
                "result": result
            }

        elif action == "delete":
            if not import_id:
                return {"success": False, "error": "import_id is required for delete action"}

            api._request("DELETE", f"imports/{import_id}")

            return {
                "success": True,
                "action": "delete",
                "import_id": import_id,
                "message": "Import file deleted successfully"
            }

        elif action == "process":
            if not import_id:
                return {"success": False, "error": "import_id is required for process action"}

            result = api._request("POST", f"imports/process/{import_id}")

            return {
                "success": True,
                "action": "process",
                "import_id": import_id,
                "message": "Import processed",
                "result": result
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Import not found: {e}")
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
        logger.error(f"Unexpected error in manage_imports: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


