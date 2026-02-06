# Task: Add CSV Import Management

**Priority: High**

## Objective

Add CSV import management capabilities to the snipeit-mcp server.py.

## Requirements

### Create New Tool: `manage_imports`

Implement the following actions:

| Action | Method | Endpoint | Description |
|--------|--------|----------|-------------|
| `list` | GET | `/imports` | List all import files |
| `get` | GET | `/imports/{id}` | Get import file details including column mappings |
| `upload` | POST | `/imports` | Upload a CSV file for import |
| `update` | PATCH | `/imports/{id}` | Update import column mappings |
| `delete` | DELETE | `/imports/{id}` | Delete an import file |
| `process` | POST | `/imports/process/{id}` | Execute the import |

### Pydantic Model: `ImportData`

Create a model for the update action:

```python
class ImportData(BaseModel):
    """Model for import configuration."""
    import_type: Literal["asset", "accessory", "consumable", "component", "license", "user", "location"] | None = Field(
        None, description="Type of data being imported"
    )
    field_map: dict | None = Field(
        None, description="Maps CSV column names to Snipe-IT field names"
    )
    run_backup: bool | None = Field(
        None, description="Whether to backup database before import"
    )
```

### Upload Action

For the upload action:
- Accept a `file_path` parameter pointing to the local CSV file
- Handle multipart form upload (not JSON)
- Return the created import ID for subsequent mapping/processing

## Implementation Notes

- Use the `SnipeITDirectAPI` class
- For file upload, use `requests` with `files=` parameter (similar to `license_files` upload)
- Match existing patterns for error handling and response formatting
- The import workflow is: upload → update mappings → process

## Example Usage

```python
# Upload a CSV file
result = manage_imports(action="upload", file_path="/path/to/assets.csv")
import_id = result["import"]["id"]

# Configure column mappings
manage_imports(
    action="update",
    import_id=import_id,
    import_data={
        "import_type": "asset",
        "field_map": {
            "Asset Tag": "asset_tag",
            "Serial Number": "serial",
            "Model": "model_id",
            "Status": "status_id"
        },
        "run_backup": True
    }
)

# Execute the import
manage_imports(action="process", import_id=import_id)
```

## Field Mapping Reference

Common field mappings for assets:
- `asset_tag`, `name`, `serial`, `model_id`, `status_id`
- `purchase_date`, `purchase_cost`, `order_number`
- `notes`, `warranty_months`, `supplier_id`
- `location_id`, `company_id`, `category_id`
