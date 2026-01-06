# Snipe-IT MCP Server

A comprehensive [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for managing [Snipe-IT](https://snipeitapp.com/) inventory systems. This server enables AI assistants to perform full CRUD operations across your entire Snipe-IT instance with **29 tools** covering all major API endpoints.

## Features

### Asset Management
- **Full CRUD Operations**: Create, read, update, delete, and search assets
- **Asset Operations**: Checkout, checkin, audit, and restore assets
- **File Attachments**: Upload, download, list, and delete asset files
- **Label Generation**: Generate printable PDF labels
- **Maintenance Tracking**: Create and manage maintenance records
- **License Associations**: View licenses assigned to assets

### Inventory Tracking
- **Consumables**: Complete management of consumable items
- **Components**: Manage components with checkout/checkin to assets
- **Accessories**: Track accessories with checkout/checkin to users

### Users & Organization
- **Users**: Full user management including restore and current user endpoint
- **User Assets**: View all items checked out to a user
- **Companies**: Multi-tenant company management
- **Departments**: Organizational department management
- **Groups**: Permission group management

### System Configuration
- **Categories**: Manage categories for all item types
- **Manufacturers**: Track manufacturer information
- **Models**: Define asset models with depreciation and custom fields
- **Status Labels**: Configure asset statuses
- **Locations**: Manage physical locations with hierarchy
- **Suppliers**: Track supplier information
- **Depreciations**: Define depreciation schedules

### Custom Fields
- **Fields**: Create and manage custom field definitions
- **Fieldsets**: Group custom fields for assignment to models
- **Field Association**: Associate/disassociate fields with fieldsets

### Licensing
- **License Management**: Full CRUD for software licenses
- **Seat Assignments**: Checkout/checkin license seats
- **License Files**: Manage license documentation

### Reporting
- **Activity Logs**: Query all activity history
- **Item Activity**: Get activity for specific items

## Requirements

- Python 3.11+
- [UV](https://github.com/astral-sh/uv) package manager
- Snipe-IT instance with API access
- API token with appropriate permissions

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/jameshgordy/snipeit-mcp.git
cd snipeit-mcp
```

### 2. Install dependencies

```bash
uv sync
```

### 3. Configure environment variables

Create a `.env` file:

```env
SNIPEIT_URL=https://your-snipeit-instance.com
SNIPEIT_TOKEN=your-api-token-here
```

**Getting an API Token:**
1. Log in to your Snipe-IT instance
2. Navigate to your user profile (top right menu)
3. Go to "Manage API Keys" or "Personal Access Tokens"
4. Generate a new token with required permissions

## MCP Client Configuration

### Claude Desktop / Claude Code

Add to your MCP configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "snipeit": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/snipeit-mcp",
        "run",
        "python",
        "server.py"
      ],
      "env": {
        "SNIPEIT_URL": "https://your-snipeit-instance.com",
        "SNIPEIT_TOKEN": "your-api-token-here"
      }
    }
  }
}
```

### Cursor

Add to your Cursor MCP settings with the same configuration format as above.

## Available Tools (29 Total)

### Asset Tools (6)

| Tool | Description |
|------|-------------|
| `manage_assets` | CRUD operations for assets (create, get, list, update, delete) |
| `asset_operations` | State operations (checkout, checkin, audit, restore) |
| `asset_files` | File attachments (upload, list, download, delete) |
| `asset_labels` | Generate printable PDF labels |
| `asset_maintenance` | Create maintenance records |
| `asset_licenses` | View licenses assigned to an asset |

### Inventory Tools (5)

| Tool | Description |
|------|-------------|
| `manage_consumables` | CRUD operations for consumables |
| `manage_components` | CRUD operations for components |
| `component_operations` | Checkout/checkin components to assets |
| `manage_accessories` | CRUD operations for accessories |
| `accessory_operations` | Checkout/checkin accessories to users |

### User & Organization Tools (5)

| Tool | Description |
|------|-------------|
| `manage_users` | CRUD operations for users (+ restore, me) |
| `user_assets` | Get all items checked out to a user |
| `manage_companies` | CRUD operations for companies |
| `manage_departments` | CRUD operations for departments |
| `manage_groups` | CRUD operations for permission groups |

### Configuration Tools (7)

| Tool | Description |
|------|-------------|
| `manage_categories` | Manage categories for all item types |
| `manage_manufacturers` | Manage manufacturer information |
| `manage_models` | Manage asset models |
| `manage_status_labels` | Manage asset status labels |
| `manage_locations` | Manage physical locations |
| `manage_suppliers` | Manage supplier information |
| `manage_depreciations` | Manage depreciation schedules |

### Custom Field Tools (2)

| Tool | Description |
|------|-------------|
| `manage_fields` | CRUD + associate/disassociate fields with fieldsets |
| `manage_fieldsets` | CRUD operations for fieldsets |

### License Tools (3)

| Tool | Description |
|------|-------------|
| `manage_licenses` | CRUD operations for licenses |
| `license_seats` | Manage license seat assignments |
| `license_files` | Manage license file attachments |

### Reporting Tools (1)

| Tool | Description |
|------|-------------|
| `activity_reports` | Query activity logs and item history |

## Usage Examples

### Create an Asset

```json
{
  "action": "create",
  "asset_data": {
    "status_id": 1,
    "model_id": 5,
    "asset_tag": "LAP-001",
    "name": "MacBook Pro 14",
    "serial": "C02X12345"
  }
}
```

### Create a User

```json
{
  "action": "create",
  "user_data": {
    "first_name": "John",
    "last_name": "Doe",
    "username": "jdoe",
    "email": "jdoe@example.com",
    "password": "securepassword",
    "password_confirmation": "securepassword",
    "department_id": 1
  }
}
```

### Get Items Checked Out to User

```json
{
  "user_id": 123,
  "asset_type": "all"
}
```

### Checkout Component to Asset

```json
{
  "action": "checkout",
  "component_id": 45,
  "checkout_data": {
    "assigned_to": 123,
    "assigned_qty": 2,
    "note": "RAM upgrade"
  }
}
```

### Query Activity Logs

```json
{
  "action": "list",
  "action_type": "checkout",
  "limit": 50
}
```

### Create Custom Field

```json
{
  "action": "create",
  "field_data": {
    "name": "MAC Address",
    "element": "text",
    "format": "MAC"
  }
}
```

### Associate Field with Fieldset

```json
{
  "action": "associate",
  "field_id": 5,
  "fieldset_id": 1,
  "required": true,
  "order": 1
}
```

## Response Format

All tools return structured JSON responses:

**Success:**
```json
{
  "success": true,
  "action": "create",
  "asset": {
    "id": 123,
    "asset_tag": "LAP-001",
    "name": "MacBook Pro 14"
  }
}
```

**Error:**
```json
{
  "success": false,
  "error": "Asset not found: Asset with tag LAP-999 not found."
}
```

## Architecture

Built with:
- **[FastMCP](https://gofastmcp.com)**: Python framework for MCP servers
- **[snipeit-python-api](https://github.com/lfctech/snipeit-python-api)**: Snipe-IT API client
- **[Pydantic](https://docs.pydantic.dev)**: Data validation and type safety

## Troubleshooting

### Authentication Errors
- Verify your Snipe-IT URL includes the protocol (`https://`)
- Check that your API token is valid and not expired
- Ensure the token has appropriate permissions for the operations

### Connection Errors
- Verify network connectivity to your Snipe-IT instance
- Check for any firewall or proxy restrictions
- Ensure the Snipe-IT instance is running

### Validation Errors
- Check that required fields are provided (e.g., `status_id` and `model_id` for assets)
- Verify that referenced IDs exist (categories, models, locations, etc.)
- Review the tool documentation for required parameters

## License

MIT License

## Contributing

Contributions welcome! Please open an issue or submit a pull request.
