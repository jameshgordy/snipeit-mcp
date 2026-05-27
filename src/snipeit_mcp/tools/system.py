"""Snipe-IT system administration tools: version info, backups, LDAP."""

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

logger = logging.getLogger(__name__)


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
def system_info() -> dict[str, Any]:
    """Get Snipe-IT system information.

    Returns version and installation details. Useful for
    compatibility checking and deployment verification.

    Returns:
        dict: System version information
    """
    try:
        api = _client.get_direct_api()
        result = api._request("GET", "version")

        return {
            "success": True,
            "version_info": result
        }

    except SnipeITAuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        return {"success": False, "error": f"Authentication failed: {str(e)}"}
    except SnipeITException as e:
        logger.error(f"Snipe-IT error: {e}")
        return {"success": False, "error": f"Snipe-IT error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error in system_info: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
def manage_backups(
    action: Annotated[
        Literal["list", "download"],
        "The backup action to perform"
    ],
    filename: Annotated[str | None, "Backup filename (for download)"] = None,
    save_path: Annotated[str | None, "Local path to save backup (for download)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT database backups.

    Operations:
    - list: List available database backup files
    - download: Download a specific backup file

    Note: Backup creation is triggered via web UI or CLI,
    not available via API.

    Returns:
        dict: Backup list or download result
    """
    try:
        api = _client.get_direct_api()

        if action == "list":
            result = api._request("GET", "settings/backups")
            backups = result.get("rows", result.get("backups", []))

            return {
                "success": True,
                "action": "list",
                "backups": backups
            }

        elif action == "download":
            if not filename:
                return {"success": False, "error": "filename is required for download action"}
            if not save_path:
                return {"success": False, "error": "save_path is required for download action"}

            url = f"{api.base_url}/api/v1/settings/backups/download/{filename}"
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
                "filename": filename,
                "saved_to": save_path,
                "message": f"Backup downloaded to {save_path}"
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Backup not found: {e}")
        return {"success": False, "error": f"Not found: {str(e)}"}
    except SnipeITAuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        return {"success": False, "error": f"Authentication failed: {str(e)}"}
    except SnipeITException as e:
        logger.error(f"Snipe-IT error: {e}")
        return {"success": False, "error": f"Snipe-IT error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error in manage_backups: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    }
)
def ldap_operations(
    action: Annotated[
        Literal["sync", "test"],
        "The LDAP action to perform"
    ],
) -> dict[str, Any]:
    """Manage LDAP synchronization.

    Operations:
    - sync: Trigger LDAP user synchronization
    - test: Test LDAP connection settings

    Note: LDAP must be configured in Snipe-IT settings before use.
    Previously required CLI (php artisan snipeit:ldap-sync) or web UI.

    Returns:
        dict: Sync results or connection test status
    """
    try:
        api = _client.get_direct_api()

        if action == "sync":
            result = api._request("POST", "settings/ldapsync")

            return {
                "success": True,
                "action": "sync",
                "message": "LDAP sync triggered",
                "result": result
            }

        elif action == "test":
            result = api._request("GET", "settings/ldaptest")

            return {
                "success": True,
                "action": "test",
                "result": result
            }

    except SnipeITNotFoundError as e:
        logger.error(f"LDAP endpoint not found: {e}")
        return {"success": False, "error": f"Not found (LDAP may not be configured): {str(e)}"}
    except SnipeITAuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        return {"success": False, "error": f"Authentication failed: {str(e)}"}
    except SnipeITException as e:
        logger.error(f"Snipe-IT error: {e}")
        return {"success": False, "error": f"Snipe-IT error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error in ldap_operations: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


