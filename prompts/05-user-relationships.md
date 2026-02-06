# Task: Extend User Relationship Endpoints

**Priority: Medium**

## Objective

Extend the `user_assets` tool and add user administration functions.

## Requirements

### 1. Extend `user_assets` Tool

Currently supports: `"assets"`, `"accessories"`, `"licenses"`, `"all"`

Add new options:

| Option | Endpoint | Description |
|--------|----------|-------------|
| `consumables` | `GET /users/{id}/consumables` | Consumables checked out to user |
| `eulas` | `GET /users/{id}/eulas` | Pending EULA/acceptance items |

Update the `asset_type` Literal:

```python
asset_type: Annotated[
    Literal["assets", "accessories", "licenses", "consumables", "eulas", "all"],
    "Type of items to retrieve"
] = "all",
```

When `all` is selected, also fetch consumables (but not eulas - those are separate workflow).

### 2. Create New Tool: `user_two_factor`

Admin function to reset a user's two-factor authentication:

```python
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
```

Endpoint: `POST /users/{user_id}/two_factor_reset`

## Implementation Notes

- Use `SnipeITDirectAPI` for new endpoints
- The EULA endpoint is important for checkout acceptance workflows
- Match existing error handling patterns
- The 2FA reset is a security-sensitive operation - note this in responses

## Example Usage

```python
# Get all items checked out to a user (now includes consumables)
user_assets(user_id=42, asset_type="all")

# Get just consumables
user_assets(user_id=42, asset_type="consumables")

# Check pending acceptances for a user
user_assets(user_id=42, asset_type="eulas")
# Returns items requiring user acceptance (EULA acceptance workflow)

# Reset user's 2FA (admin function)
user_two_factor(action="reset", user_id=42)
```

## EULA/Acceptance Workflow Context

When assets are checked out with `require_acceptance: true` (set on category):
1. User receives notification to accept terms
2. Asset shows as "pending acceptance" 
3. `GET /users/{id}/eulas` returns these pending items
4. User accepts via web portal (no API for acceptance)

This endpoint helps identify users with pending acceptances for follow-up.
