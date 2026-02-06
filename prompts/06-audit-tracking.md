# Task: Add Audit Tracking Endpoints

**Priority: Medium**

## Objective

Add audit due/overdue tracking endpoints for compliance workflows.

## Requirements

### Create New Tool: `audit_tracking`

Implement the following actions:

| Action | Endpoint | Description |
|--------|----------|-------------|
| `due` | `GET /hardware/audit/due` | Assets approaching audit date (within threshold) |
| `overdue` | `GET /hardware/audit/overdue` | Assets past their audit date |

### Tool Signature

```python
@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
def audit_tracking(
    action: Annotated[
        Literal["due", "overdue", "summary"],
        "The audit tracking action"
    ],
    limit: Annotated[int | None, "Number of results to return"] = 50,
    offset: Annotated[int | None, "Number of results to skip"] = 0,
) -> dict[str, Any]:
    """Track asset audit status for compliance.
    
    Snipe-IT tracks when assets were last audited and calculates
    when they're due for re-audit based on the configured threshold.
    
    Operations:
    - due: Assets approaching their audit date (within warning threshold)
    - overdue: Assets that have passed their audit date
    - summary: Combined counts of due and overdue assets
    
    The audit threshold is configured in Admin Settings → Notifications
    and determines the lookahead window for "due" assets.
    
    Returns:
        dict: Audit status with asset details
    """
```

### Summary Action

The `summary` action should call both endpoints and return:

```python
{
    "success": True,
    "action": "summary",
    "due_count": 15,
    "overdue_count": 3,
    "due_assets": [...],  # First few due assets
    "overdue_assets": [...]  # All overdue assets (typically fewer)
}
```

## Implementation Notes

- Use `SnipeITDirectAPI` for the endpoints
- Both endpoints return paginated asset lists
- Include relevant audit fields in response: `last_audit_date`, `next_audit_date`
- The audit threshold is a system setting (not accessible via API)

## Response Format

```python
{
    "success": True,
    "action": "due",
    "count": 15,
    "assets": [
        {
            "id": 123,
            "asset_tag": "ASSET-001",
            "name": "MacBook Pro",
            "serial": "C02X12345",
            "last_audit_date": "2024-06-15",
            "next_audit_date": "2025-01-15",
            "location": {"id": 1, "name": "Office A"},
            "assigned_to": {"id": 5, "name": "John Doe"}
        },
        ...
    ]
}
```

## Example Usage

```python
# Get assets due for audit
audit_tracking(action="due", limit=100)

# Get overdue assets (compliance risk)
audit_tracking(action="overdue")

# Get summary for dashboard
audit_tracking(action="summary")
```

## Integration with Existing Audit Function

The existing `asset_operations` tool has an `audit` action that marks an asset as audited:

```python
asset_operations(
    action="audit",
    asset_id=123,
    audit_data={"location_id": 1, "note": "Annual audit complete"}
)
```

The new `audit_tracking` tool complements this by identifying WHICH assets need auditing.
