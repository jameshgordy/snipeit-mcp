# Snipe-IT MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for managing [Snipe-IT](https://snipeitapp.com/) inventory systems. This server provides AI assistants with tools to perform CRUD operations on assets and consumables in your Snipe-IT instance.

## Features

- **Comprehensive Asset Management**: Create, read, update, delete, and search assets
- **Asset Operations**: Checkout, checkin, audit, and restore assets
- **File Management**: Upload, download, list, and delete asset attachments
- **Label Generation**: Generate printable PDF labels for assets
- **Maintenance Tracking**: Create maintenance records for assets
- **License Management**: View licenses associated with assets
- **Consumable Management**: Full CRUD operations for consumables
- **Type-Safe**: Built with Pydantic models for robust validation
- **Error Handling**: Comprehensive error handling and logging

## Requirements

- Python 3.11 or higher
- [UV](https://github.com/astral-sh/uv) package manager
- A running Snipe-IT instance with API access
- Snipe-IT API token with appropriate permissions

## Installation

### 1. Clone or download this repository

```bash
git clone <repository-url>
cd snipeit-mcp
```

### 2. Install dependencies using UV

```bash
# Install dependencies and create virtual environment
uv sync

# This will:
# - Create a virtual environment at .venv
# - Install fastmcp, requests, and snipeit-python-api
# - Set up the project for development
```

**Note:** The first time you run `uv sync`, it will install the snipeit-python-api from the local path at `/Users/work/Documents/Projects/Inventory/snipeit-python-api`. Make sure that directory exists.

Alternatively, if you want to manually set up:

```bash
# Create virtual environment
uv venv --python 3.11

# Install dependencies
uv pip install fastmcp requests /Users/work/Documents/Projects/Inventory/snipeit-python-api
```

### 3. Configure environment variables

Create a `.env` file or export these environment variables:

```bash
export SNIPEIT_URL="https://your-snipeit-instance.com"
export SNIPEIT_TOKEN="your-api-token-here"
```

Or create a `.env` file:

```env
SNIPEIT_URL=https://your-snipeit-instance.com
SNIPEIT_TOKEN=your-api-token-here
```

To get a Snipe-IT API token:
1. Log in to your Snipe-IT instance
2. Go to your user profile (click your name in the top right)
3. Navigate to "API Tokens" or "Personal Access Tokens"
4. Generate a new token with appropriate permissions

## Usage

### Running the Server

#### Method 1: Direct Python execution

```bash
# Make sure environment variables are set
export SNIPEIT_URL="https://your-snipeit-instance.com"
export SNIPEIT_TOKEN="your-api-token-here"

# Run the server
python server.py
```

#### Method 2: Using FastMCP CLI

```bash
# With environment variables
fastmcp run server.py:mcp --transport stdio

# Or with HTTP transport for remote access
fastmcp run server.py:mcp --transport http --port 8000
```

### Available Tools

The server provides the following tools for interacting with your Snipe-IT instance:

#### 1. `manage_assets`
Comprehensive asset management with CRUD operations.

**Actions:**
- `create`: Create a new asset
- `get`: Retrieve a single asset by ID, asset tag, or serial number
- `list`: List assets with optional pagination and filtering
- `update`: Update an existing asset
- `delete`: Delete an asset

**Example:**
```python
# Create an asset
{
    "action": "create",
    "asset_data": {
        "status_id": 1,
        "model_id": 5,
        "asset_tag": "LAP-001",
        "name": "Dell Laptop",
        "serial": "ABC123XYZ"
    }
}

# Get an asset by tag
{
    "action": "get",
    "asset_tag": "LAP-001"
}

# List assets
{
    "action": "list",
    "limit": 20,
    "search": "laptop"
}
```

#### 2. `asset_operations`
Perform state operations on assets.

**Actions:**
- `checkout`: Check out an asset to a user, location, or another asset
- `checkin`: Check in an asset back to inventory
- `audit`: Mark an asset as audited
- `restore`: Restore a soft-deleted asset

**Example:**
```python
# Checkout asset to user
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

# Checkin asset
{
    "action": "checkin",
    "asset_id": 123,
    "checkin_data": {
        "note": "Returned in good condition"
    }
}
```

#### 3. `asset_files`
Manage file attachments for assets.

**Actions:**
- `upload`: Upload one or more files to an asset
- `list`: List all files attached to an asset
- `download`: Download a specific file from an asset
- `delete`: Delete a specific file from an asset

**Example:**
```python
# Upload files
{
    "action": "upload",
    "asset_id": 123,
    "file_paths": ["/path/to/receipt.pdf", "/path/to/warranty.pdf"],
    "notes": "Purchase documentation"
}

# List files
{
    "action": "list",
    "asset_id": 123
}
```

#### 4. `asset_labels`
Generate printable PDF labels for assets.

**Example:**
```python
# Generate labels by asset IDs
{
    "asset_ids": [123, 124, 125],
    "save_path": "/tmp/asset_labels.pdf"
}

# Generate labels by asset tags
{
    "asset_tags": ["LAP-001", "LAP-002"],
    "save_path": "/tmp/labels.pdf"
}
```

#### 5. `asset_maintenance`
Create maintenance records for assets.

**Example:**
```python
{
    "action": "create",
    "asset_id": 123,
    "maintenance_data": {
        "asset_improvement": "repair",
        "supplier_id": 10,
        "title": "Screen Replacement",
        "cost": 250.00,
        "start_date": "2025-10-10",
        "completion_date": "2025-10-11",
        "notes": "Replaced cracked screen"
    }
}
```

#### 6. `asset_licenses`
Get all licenses checked out to an asset.

**Example:**
```python
{
    "asset_id": 123
}
```

#### 7. `manage_consumables`
Comprehensive consumable management with CRUD operations.

**Actions:**
- `create`: Create a new consumable
- `get`: Retrieve a single consumable by ID
- `list`: List consumables with optional pagination and filtering
- `update`: Update an existing consumable
- `delete`: Delete a consumable

**Example:**
```python
# Create a consumable
{
    "action": "create",
    "consumable_data": {
        "name": "USB-C Cable",
        "qty": 50,
        "category_id": 3,
        "min_amt": 10
    }
}

# List consumables
{
    "action": "list",
    "limit": 20,
    "search": "cable"
}
```

## Integration with MCP Clients

### Claude Desktop

Add this configuration to your Claude Desktop config file:

**Location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

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

Add this to your Cursor MCP settings:

```json
{
  "mcpServers": {
    "snipeit": {
      "command": "python",
      "args": ["/path/to/snipeit-mcp/server.py"],
      "env": {
        "SNIPEIT_URL": "https://your-snipeit-instance.com",
        "SNIPEIT_TOKEN": "your-api-token-here"
      }
    }
  }
}
```

## Architecture

The server is built using:

- **FastMCP**: A Python framework for building MCP servers
- **snipeit-python-api**: Python client library for Snipe-IT API
- **Pydantic**: Data validation and settings management

### Tool Design

The server consolidates operations into a minimal number of tools:

- Single tool for Asset CRUD operations (`manage_assets`)
- Single tool for Asset state operations (`asset_operations`)
- Specialized tools for specific features (files, labels, maintenance, licenses)
- Single tool for Consumable CRUD operations (`manage_consumables`)

This design minimizes the cognitive load on AI assistants while providing comprehensive functionality.

## Error Handling

All tools return structured responses with success status:

```json
{
  "success": true,
  "action": "create",
  "asset": {
    "id": 123,
    "asset_tag": "LAP-001",
    "name": "Dell Laptop"
  }
}
```

Error responses include descriptive messages:

```json
{
  "success": false,
  "error": "Asset not found: Asset with tag LAP-999 not found."
}
```

## Troubleshooting

### Authentication Errors

**Problem:** "Authentication failed" error

**Solution:** 
- Verify your Snipe-IT URL is correct and accessible
- Check that your API token is valid and not expired
- Ensure the token has appropriate permissions

### Connection Errors

**Problem:** Cannot connect to Snipe-IT instance

**Solution:**
- Verify the URL is correct (include `https://` or `http://`)
- Check network connectivity
- Ensure Snipe-IT instance is running and accessible

### Tool Execution Errors

**Problem:** Tool returns validation errors

**Solution:**
- Check that required fields are provided (e.g., `status_id` and `model_id` for asset creation)
- Verify foreign key IDs exist (e.g., category_id, model_id)
- Review the tool documentation for required parameters

### Environment Variable Issues

**Problem:** "Snipe-IT credentials not configured" error

**Solution:**
- Ensure `SNIPEIT_URL` and `SNIPEIT_TOKEN` are set in your environment
- If using a `.env` file, make sure it's in the correct location
- Check that the variables are exported before running the server

## Development

### Project Structure

```
snipeit-mcp/
├── server.py           # Main MCP server implementation
├── pyproject.toml      # Project configuration
├── README.md           # This file
├── .gitignore         # Git ignore rules
└── .venv/             # Virtual environment (created by uv)
```

### Running in Development Mode

```bash
# Activate virtual environment
source .venv/bin/activate

# Run with debug logging
export LOG_LEVEL=DEBUG
python server.py
```

## License

This project is provided as-is for use with Snipe-IT inventory management systems.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues related to:
- **This MCP Server**: Open an issue in this repository
- **Snipe-IT**: Visit [Snipe-IT support](https://snipeitapp.com/support)
- **FastMCP**: Visit [FastMCP documentation](https://gofastmcp.com)

## Acknowledgments

- Built with [FastMCP](https://gofastmcp.com)
- Uses [snipeit-python-api](https://github.com/lfctech/snipeit-python-api) for Snipe-IT integration
- Designed for [Snipe-IT](https://snipeitapp.com/) asset management system
