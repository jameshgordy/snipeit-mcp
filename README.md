# Snipe-IT MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for managing [Snipe-IT](https://snipeitapp.com/) inventory systems. This server enables AI assistants to perform comprehensive CRUD operations across your entire Snipe-IT instance.

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
- **Accessories**: Track accessories with checkout/checkin operations

### System Configuration
- **Categories**: Manage asset, accessory, consumable, component, and license categories
- **Manufacturers**: Track manufacturer information and support contacts
- **Models**: Define asset models with depreciation and custom fields
- **Status Labels**: Configure asset statuses (deployable, pending, archived, etc.)
- **Locations**: Manage physical locations with hierarchy support
- **Suppliers**: Track supplier information and contacts
- **Depreciations**: Define depreciation schedules

### Licensing
- **License Management**: Full CRUD for software licenses
- **Seat Assignments**: Checkout/checkin license seats to users or assets
- **License Files**: Manage license documentation and attachments

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

Add to your Cursor MCP settings:

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

## Available Tools

### Asset Tools

| Tool | Description |
|------|-------------|
| `manage_assets` | CRUD operations for assets (create, get, list, update, delete) |
| `asset_operations` | State operations (checkout, checkin, audit, restore) |
| `asset_files` | File attachments (upload, list, download, delete) |
| `asset_labels` | Generate printable PDF labels |
| `asset_maintenance` | Create maintenance records |
| `asset_licenses` | View licenses assigned to an asset |

### Inventory Tools

| Tool | Description |
|------|-------------|
| `manage_consumables` | CRUD operations for consumables |
| `manage_accessories` | CRUD operations for accessories |
| `accessory_operations` | Checkout/checkin accessories to users |

### Configuration Tools

| Tool | Description |
|------|-------------|
| `manage_categories` | Manage categories for all item types |
| `manage_manufacturers` | Manage manufacturer information |
| `manage_models` | Manage asset models |
| `manage_status_labels` | Manage asset status labels |
| `manage_locations` | Manage physical locations |
| `manage_suppliers` | Manage supplier information |
| `manage_depreciations` | Manage depreciation schedules |

### License Tools

| Tool | Description |
|------|-------------|
| `manage_licenses` | CRUD operations for licenses |
| `license_seats` | Manage license seat assignments |
| `license_files` | Manage license file attachments |

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

### Checkout Asset to User

```json
{
  "action": "checkout",
  "asset_id": 123,
  "checkout_data": {
    "checkout_to_type": "user",
    "assigned_to_id": 45,
    "expected_checkin": "2025-12-31",
    "note": "Issued for remote work"
  }
}
```

### List Assets with Search

```json
{
  "action": "list",
  "limit": 20,
  "search": "macbook"
}
```

### Create a Consumable

```json
{
  "action": "create",
  "consumable_data": {
    "name": "USB-C Cable",
    "qty": 50,
    "category_id": 3,
    "min_amt": 10
  }
}
```

### Generate Asset Labels

```json
{
  "asset_ids": [123, 124, 125],
  "save_path": "/tmp/asset_labels.pdf"
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
