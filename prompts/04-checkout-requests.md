# Task: Add Checkout Request Workflow

**Priority: Medium**

## Objective

Add checkout request functionality to enable self-service asset request workflows.

## Requirements

### Create New Tool: `asset_requests`

Implement the following actions:

| Action | Method | Endpoint | Description |
|--------|--------|----------|-------------|
| `request` | POST | `/hardware/request/{asset_id}` | Submit a checkout request for a requestable asset |
| `cancel` | POST | `/hardware/request/{asset_id}/cancel` | Cancel a pending request |

### Pydantic Model: `AssetRequestData`

```python
class AssetRequestData(BaseModel):
    """Model for asset checkout request."""
    expected_checkout: str | None = Field(
        None, description="Expected checkout date (YYYY-MM-DD)"
    )
    note: str | None = Field(
        None, description="Note explaining the request"
    )
```

### Tool Signature

```python
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
```

## Implementation Notes

- Use `SnipeITDirectAPI` for the endpoints
- These endpoints are undocumented but exist in the Snipe-IT routes
- The asset must have `requestable: true` for requests to work
- Document the limitation that approval/denial is web-only in the docstring

## Important Limitations

Document these clearly:

1. **No queue viewing** - Cannot list pending requests via API
2. **No approval/denial** - Administrators must use web UI
3. **No notification control** - Email notifications configured in settings

## Example Usage

```python
# Submit a request for an asset
asset_requests(
    action="request",
    asset_id=123,
    request_data={
        "expected_checkout": "2025-02-01",
        "note": "Need for Q1 project work"
    }
)

# Cancel a pending request
asset_requests(action="cancel", asset_id=123)
```

## Prerequisites

For an asset to be requestable:
1. The asset's model must have `requestable: true`, OR
2. The asset itself must have `requestable: true`

Set via:
```python
manage_models(action="update", model_id=5, model_data={"requestable": True})
# or
manage_assets(action="update", asset_id=123, asset_data={"requestable": True})
```
