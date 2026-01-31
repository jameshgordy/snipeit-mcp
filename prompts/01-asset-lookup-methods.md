# Task: Add Asset Lookup Methods

**Priority: High**

## Objective

Add asset lookup methods and enhanced filtering to the snipeit-mcp server.py.

## Requirements

### 1. Dedicated Lookup Endpoints

Extend `manage_assets` tool to support lookup by asset_tag and serial number using dedicated API endpoints:

- `GET /hardware/bytag/{asset_tag}`
- `GET /hardware/byserial/{serial}`

Currently the implementation uses the snipeit-python-api library methods but these dedicated endpoints are more reliable for barcode scanning workflows.

### 2. Filter Parameters

Add the following filter parameters to the `manage_assets` list action:

| Parameter | Type | Description |
|-----------|------|-------------|
| `status_id` | int | Filter by status label |
| `model_id` | int | Filter by model |
| `company_id` | int | Filter by company |
| `location_id` | int | Filter by location |
| `category_id` | int | Filter by category |
| `manufacturer_id` | int | Filter by manufacturer |
| `assigned_to` | int | Filter by assigned user/asset/location ID |

### 3. Sortable Columns

Add sortable column support matching Snipe-IT's available sort fields:

```
id, name, asset_tag, serial, model, model_number, last_checkout, 
category, manufacturer, notes, expected_checkin, order_number, 
companyName, location, image, status_label, assigned_to, 
created_at, purchase_date, purchase_cost
```

## Implementation Notes

- Use the existing `SnipeITDirectAPI` class for the bytag/byserial endpoints
- Match existing code patterns and error handling
- Update the tool's docstring to document new parameters
- Add appropriate type hints using `Annotated`

## Example Usage

```python
# Lookup by asset tag (barcode scan)
manage_assets(action="get", asset_tag="ASSET-001")

# Lookup by serial number
manage_assets(action="get", serial="C02X12345")

# List with filters
manage_assets(
    action="list", 
    status_id=1, 
    location_id=5, 
    sort="purchase_date", 
    order="desc"
)
```
