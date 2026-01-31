# Task: Add Settings and System Info Endpoints

**Priority: Low**

## Objective

Add system information, backup management, and LDAP sync capabilities.

## Requirements

### 1. Create Tool: `system_info`

Simple read-only tool for version information:

```python
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
```

Endpoint: `GET /version`

### 2. Create Tool: `manage_backups`

Database backup management:

```python
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
```

Endpoints:
- `GET /settings/backups` - List backups
- `GET /settings/backups/download/{filename}` - Download backup

### 3. Create Tool: `ldap_operations`

LDAP synchronization (added in recent Snipe-IT versions):

```python
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
```

Endpoints:
- `POST /settings/ldapsync` - Trigger sync
- `GET /settings/ldaptest` - Test connection

## Implementation Notes

- Use `SnipeITDirectAPI` for all endpoints
- Backup download should save binary data to file
- LDAP endpoints may require specific permissions
- Handle cases where LDAP is not configured

## Example Usage

```python
# Check Snipe-IT version
system_info()
# Returns: {"version": "6.3.0", "full_version": "v6.3.0", ...}

# List available backups
manage_backups(action="list")
# Returns: {"backups": ["2025-01-15-backup.sql", ...]}

# Download a backup
manage_backups(
    action="download",
    filename="2025-01-15-backup.sql",
    save_path="/backups/snipeit-2025-01-15.sql"
)

# Trigger LDAP sync
ldap_operations(action="sync")
# Returns: {"synced": 150, "created": 5, "updated": 12, ...}

# Test LDAP connection
ldap_operations(action="test")
# Returns: {"success": True, "message": "Connection successful"}
```

## Permissions Note

These endpoints may require administrative API tokens. If permissions errors occur, document the required permission level.
