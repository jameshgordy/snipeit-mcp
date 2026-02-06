# Task: Add Relationship Query Endpoints

**Priority: Medium**

## Objective

Add relationship-based query endpoints to enable location/status/model-based reporting without full asset list filtering.

## Requirements

### 1. Extend `manage_locations`

Add new actions:

| Action | Endpoint | Description |
|--------|----------|-------------|
| `assets` | `GET /locations/{id}/assets` | List all assets at a specific location |
| `users` | `GET /locations/{id}/users` | List all users assigned to a location |

Parameters: `location_id` (required), `limit`, `offset`

### 2. Extend `manage_status_labels`

Add new action:

| Action | Endpoint | Description |
|--------|----------|-------------|
| `assets` | `GET /statuslabels/{id}/assetlist` | List assets with that status label |

Parameters: `status_label_id` (required), `limit`, `offset`

### 3. Extend `manage_models`

Add new action:

| Action | Endpoint | Description |
|--------|----------|-------------|
| `assets` | `GET /models/{id}/assets` | List all assets of a specific model |

Parameters: `model_id` (required), `limit`, `offset`

### 4. Create New Tool: `status_summary`

Create a read-only tool that calls:

```
GET /statuslabels/assets
```

Returns asset counts grouped by status label - useful for dashboards.

```python
@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
def status_summary() -> dict[str, Any]:
    """Get asset counts grouped by status label.
    
    Returns a summary of how many assets are in each status,
    useful for dashboard displays and reporting.
    """
```

## Implementation Notes

- All new actions should support `limit`/`offset` pagination parameters
- Use `SnipeITDirectAPI` for all new endpoints
- Match existing patterns for response formatting
- Update action `Literal` types to include new options

## Example Usage

```python
# Get all assets at a location
manage_locations(action="assets", location_id=5, limit=100)

# Get users assigned to a location  
manage_locations(action="users", location_id=5)

# Get assets with a specific status
manage_status_labels(action="assets", status_label_id=2)

# Get all assets of a model type
manage_models(action="assets", model_id=10)

# Get status summary for dashboard
status_summary()
# Returns: {"Deployed": 150, "Ready to Deploy": 45, "Pending": 12, ...}
```

## Response Format

For relationship queries, return structured data:

```python
{
    "success": True,
    "action": "assets",
    "location_id": 5,
    "count": 25,
    "assets": [
        {"id": 1, "asset_tag": "...", "name": "...", ...},
        ...
    ]
}
```
