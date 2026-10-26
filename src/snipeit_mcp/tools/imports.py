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
        Literal["list", "get", "upload", "delete", "process"],
        "The import action to perform"
    ],
    import_id: Annotated[int | None, "Import file ID (required for get, delete, process)"] = None,
    file_path: Annotated[str | None, "Path to CSV file (required for upload action)"] = None,
    import_data: Annotated[
        ImportData | None,
        "Import type, column mapping and options (process action; import_type is required)",
    ] = None,
) -> dict[str, Any]:
    """Manage CSV import operations for bulk data import.

    The import workflow is: upload → process (with import_type and field_map).
    Snipe-IT saves the column mapping when the import is processed; there is
    no separate step to store it.

    Operations:
    - list: List all import files (with header row, first row and saved mapping)
    - get: Get one import file's details (taken from the list; Snipe-IT has no
      single-import endpoint)
    - upload: Upload a CSV file for import
    - delete: Delete an import file
    - process: Execute the import with import_data

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
            # ImportController::index returns a bare JSON array, not {rows: [...]}.
            imports = api._request("GET", "imports")

            return {
                "success": True,
                "action": "list",
                "count": len(imports),
                "imports": imports
            }

        elif action == "get":
            if not import_id:
                return {"success": False, "error": "import_id is required for get action"}

            # GET imports/{id} is routed but ImportController has no show()
            # (HTTP 500), so pick the import out of the index.
            imports = api._request("GET", "imports")
            match = next((i for i in imports if i.get("id") == import_id), None)
            if match is None:
                return {"success": False, "error": f"Not found: import {import_id}"}

            return {
                "success": True,
                "action": "get",
                "import": match
            }

        elif action == "upload":
            if not file_path:
                return {"success": False, "error": "file_path is required for upload action"}

            import os
            if not os.path.exists(file_path):
                return {"success": False, "error": f"File not found: {file_path}"}

            filename = os.path.basename(file_path)
            # ImportController::store loops over files[]; a single "file"
            # field gets a 422 "no files".
            result = api.upload_files("imports", [file_path], field="files[]")

            return {
                "success": True,
                "action": "upload",
                "message": f"File '{filename}' uploaded successfully",
                "import": result
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

            if not import_data or not import_data.import_type:
                return {"success": False, "error": "import_data.import_type is required for process action"}

            # Field names from ItemImportRequest / ImportController::process.
            payload = {
                "import-type": import_data.import_type,
                "column-mappings": import_data.field_map,
                "run-backup": import_data.run_backup,
                "import-update": import_data.update_existing,
                "import-preserve-blanks": import_data.preserve_blanks,
                "send-welcome": import_data.send_welcome,
            }
            payload = {k: v for k, v in payload.items() if v is not None}
            try:
                result = api._request("POST", f"imports/process/{import_id}", json=payload)
            except requests.HTTPError as e:
                # Row errors come back as HTTP 500 {"status": "import-errors"},
                # a concurrent run as 409 {"status": "error"}.
                try:
                    body = e.response.json()
                except ValueError:
                    raise e from None
                return {
                    "success": False,
                    "action": "process",
                    "import_id": import_id,
                    "error": f"Import failed: {body.get('messages')}",
                    "tally": (body.get("payload") or {}).get("tally"),
                }

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


