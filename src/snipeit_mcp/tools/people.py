"""Snipe-IT people tools: users (and 2FA reset), companies, departments, groups."""

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
from ..schemas import UserData, CompanyData, DepartmentData, GroupData

logger = logging.getLogger(__name__)


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_users(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete", "restore", "me"],
        "The action to perform on users"
    ],
    user_id: Annotated[int | None, "User ID (required for get, update, delete, restore)"] = None,
    user_data: Annotated[UserData | None, "User data (required for create, optional for update)"] = None,
    limit: Annotated[int, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list action)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action)"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
    username: Annotated[str | None, "Username for exact match (for list action)"] = None,
    email: Annotated[str | None, "Email for exact match (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT users with CRUD operations.

    This tool handles all user operations:
    - create: Create a new user (requires user_data with username, password, first_name)
    - get: Retrieve a single user by ID
    - list: List users with optional pagination and filtering
    - update: Update an existing user (requires user_id and user_data)
    - delete: Delete a user (requires user_id)
    - restore: Restore a soft-deleted user (requires user_id)
    - me: Get the currently authenticated user

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = _client.get_direct_api()

        if action == "create":
            if not user_data:
                return {"success": False, "error": "user_data is required for create action"}

            if not user_data.username or not user_data.password or not user_data.first_name:
                return {
                    "success": False,
                    "error": "username, password, and first_name are required to create a user"
                }

            create_payload = {k: v for k, v in user_data.model_dump().items() if v is not None}
            result = api.create("users", create_payload)

            return {
                "success": True,
                "action": "create",
                "user": {
                    "id": result.get("payload", {}).get("id") or result.get("id"),
                    "username": user_data.username,
                    "name": f"{user_data.first_name} {user_data.last_name or ''}".strip(),
                }
            }

        elif action == "get":
            if not user_id:
                return {"success": False, "error": "user_id is required for get action"}

            result = api.get("users", user_id)

            return {
                "success": True,
                "action": "get",
                "user": result
            }

        elif action == "list":
            extra = {}
            if username:
                extra["username"] = username
            if email:
                extra["email"] = email

            users, _total = api.list_page(
                "users", limit=limit, offset=offset,
                search=search, sort=sort, order=order,
                extra_params=extra or None,
            )

            users_list = [
                {
                    "id": user.get("id"),
                    "username": user.get("username"),
                    "name": user.get("name"),
                    "email": user.get("email"),
                    "department": user.get("department"),
                    "activated": user.get("activated"),
                }
                for user in users
            ]

            return {
                "success": True,
                "action": "list",
                **_client.pagination_meta(len(users_list), _total, limit, offset),
                "users": users_list,
            }

        elif action == "update":
            if not user_id:
                return {"success": False, "error": "user_id is required for update action"}
            if not user_data:
                return {"success": False, "error": "user_data is required for update action"}

            update_payload = {k: v for k, v in user_data.model_dump().items() if v is not None}
            result = api.update("users", user_id, update_payload)

            return {
                "success": True,
                "action": "update",
                "user_id": user_id,
                "result": result
            }

        elif action == "delete":
            if not user_id:
                return {"success": False, "error": "user_id is required for delete action"}

            result = api.delete("users", user_id)

            return {
                "success": True,
                "action": "delete",
                "user_id": user_id,
                "message": "User deleted successfully"
            }

        elif action == "restore":
            if not user_id:
                return {"success": False, "error": "user_id is required for restore action"}

            result = api._request("POST", f"users/{user_id}/restore")

            return {
                "success": True,
                "action": "restore",
                "user_id": user_id,
                "message": "User restored successfully"
            }

        elif action == "me":
            result = api._request("GET", "users/me")

            return {
                "success": True,
                "action": "me",
                "user": result
            }

    except SnipeITNotFoundError as e:
        logger.error(f"User not found: {e}")
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
        logger.error(f"Unexpected error in manage_users: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
def user_assets(
    user_id: Annotated[int, "User ID"],
    asset_type: Annotated[
        Literal["assets", "accessories", "licenses", "consumables", "eulas", "all"],
        "Type of items to retrieve"
    ] = "all",
) -> dict[str, Any]:
    """Get items checked out to a user.

    Retrieves assets, accessories, licenses, and/or consumables that are currently
    checked out to the specified user. Also supports retrieving pending EULA acceptances.

    Options:
    - assets: Hardware assets checked out to user
    - accessories: Accessories checked out to user
    - licenses: License seats assigned to user
    - consumables: Consumables checked out to user
    - eulas: Pending EULA/acceptance items (items requiring user acceptance)
    - all: All items except eulas (assets, accessories, licenses, consumables)

    Note: The eulas option returns items requiring user acceptance via web portal.
    This helps identify users with pending acceptances for follow-up.

    Returns:
        dict: Items checked out to the user
    """
    try:
        api = _client.get_direct_api()
        result = {}

        if asset_type in ("assets", "all"):
            assets = api._request("GET", f"users/{user_id}/assets")
            result["assets"] = assets.get("rows", [])

        if asset_type in ("accessories", "all"):
            accessories = api._request("GET", f"users/{user_id}/accessories")
            result["accessories"] = accessories.get("rows", [])

        if asset_type in ("licenses", "all"):
            licenses = api._request("GET", f"users/{user_id}/licenses")
            result["licenses"] = licenses.get("rows", [])

        if asset_type in ("consumables", "all"):
            consumables = api._request("GET", f"users/{user_id}/consumables")
            result["consumables"] = consumables.get("rows", [])

        if asset_type == "eulas":
            eulas = api._request("GET", f"users/{user_id}/eulas")
            result["eulas"] = eulas.get("rows", [])

        return {
            "success": True,
            "user_id": user_id,
            **result
        }

    except SnipeITNotFoundError as e:
        logger.error(f"User not found: {e}")
        return {"success": False, "error": f"Not found: {str(e)}"}
    except SnipeITAuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        return {"success": False, "error": f"Authentication failed: {str(e)}"}
    except SnipeITException as e:
        logger.error(f"Snipe-IT error: {e}")
        return {"success": False, "error": f"Snipe-IT error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error in user_assets: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}




@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_companies(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete"],
        "The action to perform on companies"
    ],
    company_id: Annotated[int | None, "Company ID (required for get, update, delete)"] = None,
    company_data: Annotated[CompanyData | None, "Company data (required for create, optional for update)"] = None,
    limit: Annotated[int, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list action)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action)"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT companies with CRUD operations.

    Companies allow you to segment your assets and users by organization.
    Useful for multi-tenant installations or tracking assets by subsidiary.

    Actions:
    - create: Create a new company (requires company_data with name)
    - get: Retrieve a single company by ID
    - list: List companies with optional pagination and filtering
    - update: Update an existing company
    - delete: Delete a company

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = _client.get_direct_api()

        if action == "create":
            if not company_data:
                return {"success": False, "error": "company_data is required for create action"}

            if not company_data.name:
                return {"success": False, "error": "name is required to create a company"}

            create_payload = {k: v for k, v in company_data.model_dump().items() if v is not None}
            result = api.create("companies", create_payload)

            return {
                "success": True,
                "action": "create",
                "company": result
            }

        elif action == "get":
            if not company_id:
                return {"success": False, "error": "company_id is required for get action"}

            result = api.get("companies", company_id)

            return {
                "success": True,
                "action": "get",
                "company": result
            }

        elif action == "list":
            params = {"limit": limit, "offset": offset}
            if search:
                params["search"] = search
            params["sort"] = sort or "id"
            params["order"] = order or "asc"

            companies, _total = api.list_page("companies", **params)

            companies_list = [
                {
                    "id": comp.get("id"),
                    "name": comp.get("name"),
                    "assets_count": comp.get("assets_count"),
                    "licenses_count": comp.get("licenses_count"),
                    "accessories_count": comp.get("accessories_count"),
                    "users_count": comp.get("users_count"),
                }
                for comp in companies
            ]

            return {
                "success": True,
                "action": "list",
                **_client.pagination_meta(len(companies_list), _total, limit, offset),
                "companies": companies_list,
            }

        elif action == "update":
            if not company_id:
                return {"success": False, "error": "company_id is required for update action"}
            if not company_data:
                return {"success": False, "error": "company_data is required for update action"}

            update_payload = {k: v for k, v in company_data.model_dump().items() if v is not None}
            result = api.update("companies", company_id, update_payload)

            return {
                "success": True,
                "action": "update",
                "company_id": company_id,
                "result": result
            }

        elif action == "delete":
            if not company_id:
                return {"success": False, "error": "company_id is required for delete action"}

            result = api.delete("companies", company_id)

            return {
                "success": True,
                "action": "delete",
                "company_id": company_id,
                "message": "Company deleted successfully"
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Company not found: {e}")
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
        logger.error(f"Unexpected error in manage_companies: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_departments(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete"],
        "The action to perform on departments"
    ],
    department_id: Annotated[int | None, "Department ID (required for get, update, delete)"] = None,
    department_data: Annotated[DepartmentData | None, "Department data (required for create, optional for update)"] = None,
    limit: Annotated[int, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list action)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
    sort: Annotated[str | None, "Field to sort by (for list action)"] = None,
    order: Annotated[Literal["asc", "desc"] | None, "Sort order (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT departments with CRUD operations.

    Departments are organizational units within a company that can be
    assigned to users.

    Actions:
    - create: Create a new department (requires department_data with name)
    - get: Retrieve a single department by ID
    - list: List departments with optional pagination and filtering
    - update: Update an existing department
    - delete: Delete a department

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = _client.get_direct_api()

        if action == "create":
            if not department_data:
                return {"success": False, "error": "department_data is required for create action"}

            if not department_data.name:
                return {"success": False, "error": "name is required to create a department"}

            create_payload = {k: v for k, v in department_data.model_dump().items() if v is not None}
            result = api.create("departments", create_payload)

            return {
                "success": True,
                "action": "create",
                "department": result
            }

        elif action == "get":
            if not department_id:
                return {"success": False, "error": "department_id is required for get action"}

            result = api.get("departments", department_id)

            return {
                "success": True,
                "action": "get",
                "department": result
            }

        elif action == "list":
            params = {"limit": limit, "offset": offset}
            if search:
                params["search"] = search
            params["sort"] = sort or "id"
            params["order"] = order or "asc"

            departments, _total = api.list_page("departments", **params)

            departments_list = [
                {
                    "id": dept.get("id"),
                    "name": dept.get("name"),
                    "company": dept.get("company"),
                    "manager": dept.get("manager"),
                    "location": dept.get("location"),
                    "users_count": dept.get("users_count"),
                }
                for dept in departments
            ]

            return {
                "success": True,
                "action": "list",
                **_client.pagination_meta(len(departments_list), _total, limit, offset),
                "departments": departments_list,
            }

        elif action == "update":
            if not department_id:
                return {"success": False, "error": "department_id is required for update action"}
            if not department_data:
                return {"success": False, "error": "department_data is required for update action"}

            update_payload = {k: v for k, v in department_data.model_dump().items() if v is not None}
            result = api.update("departments", department_id, update_payload)

            return {
                "success": True,
                "action": "update",
                "department_id": department_id,
                "result": result
            }

        elif action == "delete":
            if not department_id:
                return {"success": False, "error": "department_id is required for delete action"}

            result = api.delete("departments", department_id)

            return {
                "success": True,
                "action": "delete",
                "department_id": department_id,
                "message": "Department deleted successfully"
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Department not found: {e}")
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
        logger.error(f"Unexpected error in manage_departments: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def manage_groups(
    action: Annotated[
        Literal["create", "get", "list", "update", "delete"],
        "The action to perform on groups"
    ],
    group_id: Annotated[int | None, "Group ID (required for get, update, delete)"] = None,
    group_data: Annotated[GroupData | None, "Group data (required for create, optional for update)"] = None,
    limit: Annotated[int, "Number of results to return (for list action)"] = 50,
    offset: Annotated[int, "Number of results to skip (for list action)"] = 0,
    search: Annotated[str | None, "Search query (for list action)"] = None,
) -> dict[str, Any]:
    """Manage Snipe-IT permission groups with CRUD operations.

    Groups are used to manage permissions for multiple users at once.
    Users can belong to multiple groups, and permissions are cumulative.

    Actions:
    - create: Create a new group (requires group_data with name)
    - get: Retrieve a single group by ID
    - list: List groups with optional pagination and filtering
    - update: Update an existing group (including permissions)
    - delete: Delete a group

    Returns:
        dict: Result of the operation including success status and data
    """
    try:
        api = _client.get_direct_api()

        if action == "create":
            if not group_data:
                return {"success": False, "error": "group_data is required for create action"}

            if not group_data.name:
                return {"success": False, "error": "name is required to create a group"}

            create_payload = {k: v for k, v in group_data.model_dump().items() if v is not None}
            result = api.create("groups", create_payload)

            return {
                "success": True,
                "action": "create",
                "group": result
            }

        elif action == "get":
            if not group_id:
                return {"success": False, "error": "group_id is required for get action"}

            result = api.get("groups", group_id)

            return {
                "success": True,
                "action": "get",
                "group": result
            }

        elif action == "list":
            params = {"limit": limit, "offset": offset}
            if search:
                params["search"] = search

            groups, _total = api.list_page("groups", **params)

            groups_list = [
                {
                    "id": grp.get("id"),
                    "name": grp.get("name"),
                    "users_count": grp.get("users_count"),
                    "created_at": grp.get("created_at"),
                }
                for grp in groups
            ]

            return {
                "success": True,
                "action": "list",
                **_client.pagination_meta(len(groups_list), _total, limit, offset),
                "groups": groups_list,
            }

        elif action == "update":
            if not group_id:
                return {"success": False, "error": "group_id is required for update action"}
            if not group_data:
                return {"success": False, "error": "group_data is required for update action"}

            update_payload = {k: v for k, v in group_data.model_dump().items() if v is not None}
            result = api.update("groups", group_id, update_payload)

            return {
                "success": True,
                "action": "update",
                "group_id": group_id,
                "result": result
            }

        elif action == "delete":
            if not group_id:
                return {"success": False, "error": "group_id is required for delete action"}

            result = api.delete("groups", group_id)

            return {
                "success": True,
                "action": "delete",
                "group_id": group_id,
                "message": "Group deleted successfully"
            }

    except SnipeITNotFoundError as e:
        logger.error(f"Group not found: {e}")
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
        logger.error(f"Unexpected error in manage_groups: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}




@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def user_two_factor(
    action: Annotated[
        Literal["reset"],
        "The 2FA action to perform"
    ],
    user_id: Annotated[int, "User ID"],
) -> dict[str, Any]:
    """Manage user two-factor authentication.

    Administrative functions for managing user 2FA settings.

    Operations:
    - reset: Reset a user's 2FA, requiring them to re-enroll

    Note: This is an administrative function that affects user security.

    Returns:
        dict: Result of the operation
    """
    try:
        api = _client.get_direct_api()

        if action == "reset":
            result = api._request("POST", f"users/{user_id}/two_factor_reset")

            return {
                "success": True,
                "action": "reset",
                "user_id": user_id,
                "message": "Two-factor authentication reset successfully. User will need to re-enroll.",
                "result": result
            }

    except SnipeITNotFoundError as e:
        logger.error(f"User not found: {e}")
        return {"success": False, "error": f"User not found: {str(e)}"}
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
        logger.error(f"Unexpected error in user_two_factor: {e}", exc_info=True)
        return {"success": False, "error": f"Unexpected error: {str(e)}"}


