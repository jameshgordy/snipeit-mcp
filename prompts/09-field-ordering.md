# Task: Add Custom Field Ordering

**Priority: Low**

## Objective

Extend `manage_fieldsets` to support reordering custom fields within a fieldset.

## Requirements

### Extend `manage_fieldsets` Tool

Add a new action `reorder`:

Update the action Literal:
```python
action: Annotated[
    Literal["create", "get", "list", "update", "delete", "fields", "reorder"],
    "The action to perform on fieldsets"
]
```

Add new parameters:
```python
field_order: Annotated[list[int] | None, "Ordered list of field IDs (for reorder action)"] = None,
```

### Implementation

```python
elif action == "reorder":
    if not fieldset_id:
        return {"success": False, "error": "fieldset_id is required for reorder action"}
    if not field_order:
        return {"success": False, "error": "field_order is required for reorder action"}
    
    # field_order should be a list of field IDs in desired display order
    result = api._request(
        "POST",
        f"fields/fieldsets/{fieldset_id}/order",
        json={"item": field_order}  # Verify actual payload format
    )
    
    return {
        "success": True,
        "action": "reorder",
        "fieldset_id": fieldset_id,
        "message": "Field order updated successfully",
        "result": result
    }
```

### Endpoint

`POST /fields/fieldsets/{id}/order`

Payload format (verify against API):
```json
{
    "item": [5, 2, 8, 1, 3]
}
```

Where the array contains field IDs in the desired display order.

## Implementation Notes

- Use `SnipeITDirectAPI`
- The payload format may vary - test against actual API
- Field IDs must belong to the specified fieldset
- Order affects display in forms and detail views

## Example Usage

```python
# First, get current fields in a fieldset
result = manage_fieldsets(action="fields", fieldset_id=1)
# Returns: {"fields": [{"id": 5, "name": "MAC Address"}, {"id": 2, "name": "IP Address"}, ...]}

# Reorder fields - put IP Address first, then MAC Address
manage_fieldsets(
    action="reorder",
    fieldset_id=1,
    field_order=[2, 5, 8, 1, 3]  # Field IDs in desired order
)
```

## Workflow

1. Get fieldset fields: `manage_fieldsets(action="fields", fieldset_id=1)`
2. Determine desired order from the field IDs returned
3. Call reorder with the field IDs in new order
4. Verify with another fields call

## Error Handling

Handle these cases:
- Field ID not in fieldset
- Duplicate field IDs in order list
- Missing field IDs (partial reorder may or may not be supported)
