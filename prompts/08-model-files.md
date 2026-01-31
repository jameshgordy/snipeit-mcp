# Task: Add Model File Attachments

**Priority: Low**

## Objective

Add file attachment support for asset models, mirroring the existing `asset_files` tool pattern.

## Requirements

### Create New Tool: `model_files`

```python
@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": False,
    }
)
def model_files(
    action: Annotated[
        Literal["upload", "list", "download", "delete"],
        "The file operation to perform"
    ],
    model_id: Annotated[int, "Model ID"],
    file_path: Annotated[str | None, "File path to upload (for upload action)"] = None,
    file_id: Annotated[int | None, "File ID (required for download and delete actions)"] = None,
    save_path: Annotated[str | None, "Path to save downloaded file (for download action)"] = None,
) -> dict[str, Any]:
    """Manage file attachments for asset models.
    
    Models can have attached files such as documentation, manuals,
    datasheets, or images that apply to all assets of that model.
    
    Operations:
    - upload: Upload a file to a model
    - list: List all files attached to a model
    - download: Download a specific file from a model
    - delete: Delete a specific file from a model
    
    Returns:
        dict: Result of the operation including success status and data
    """
```

### Endpoints

| Action | Method | Endpoint |
|--------|--------|----------|
| `list` | GET | `/models/{id}/files` |
| `upload` | POST | `/models/{id}/files` |
| `download` | GET | `/models/{id}/files/{file_id}` |
| `delete` | DELETE | `/models/{id}/files/{file_id}` |

## Implementation Notes

- Mirror the `license_files` implementation pattern
- Use multipart form upload for file uploads (not JSON)
- Handle binary download and save to specified path
- Use `SnipeITDirectAPI` base but custom handling for file operations

## Reference: Existing license_files Pattern

```python
# Upload pattern from license_files
if action == "upload":
    if not file_path:
        return {"success": False, "error": "file_path is required for upload action"}

    import os
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}

    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        files = {"file": (filename, f)}
        url = f"{api.base_url}/api/v1/models/{model_id}/files"
        headers = {
            "Authorization": f"Bearer {SNIPEIT_TOKEN}",
            "Accept": "application/json",
        }
        response = requests.post(url, headers=headers, files=files)
        response.raise_for_status()
        result = response.json()
```

## Example Usage

```python
# List files attached to a model
model_files(action="list", model_id=5)
# Returns: {"files": [{"id": 1, "filename": "manual.pdf", ...}]}

# Upload documentation to a model
model_files(
    action="upload",
    model_id=5,
    file_path="/docs/macbook-pro-manual.pdf"
)

# Download a file
model_files(
    action="download",
    model_id=5,
    file_id=1,
    save_path="/downloads/manual.pdf"
)

# Delete a file
model_files(action="delete", model_id=5, file_id=1)
```

## Use Cases

- Attach product manuals to models
- Store warranty documentation
- Keep datasheets for reference
- Attach setup/configuration guides

Files attached to models are inherited context for all assets of that model type.
