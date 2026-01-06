# Changelog

All notable changes to the Snipe-IT MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2025-01-06

### Added
- **User Management Tools**
  - `manage_users` - Full CRUD for users with restore and /me endpoint
  - `user_assets` - Get all assets, accessories, licenses checked out to a user

- **Component Tools**
  - `manage_components` - CRUD operations for components (RAM, drives, etc.)
  - `component_operations` - Checkout/checkin components to assets

- **Organization Tools**
  - `manage_companies` - CRUD operations for multi-tenant company management
  - `manage_departments` - CRUD operations for organizational departments
  - `manage_groups` - CRUD operations for permission groups

- **Custom Field Tools**
  - `manage_fields` - CRUD for custom fields with associate/disassociate actions
  - `manage_fieldsets` - CRUD for fieldsets with field listing

- **Reporting Tools**
  - `activity_reports` - Query activity logs with filtering by type, target, action

- **New Pydantic Models**
  - UserData, ComponentData, ComponentCheckout, CompanyData
  - DepartmentData, GroupData, FieldData, FieldsetData

### Changed
- Server now provides 29 comprehensive tools (up from 19)
- Updated module docstring with complete tool listing
- Version bumped to 0.3.0

## [0.2.0] - 2025-01-06

### Added
- `manage_licenses` tool for comprehensive license CRUD operations
- `license_seats` tool for managing license seat assignments (checkout/checkin)
- `license_files` tool for license file attachment management
- `manage_accessories` tool for accessory CRUD operations
- `accessory_operations` tool for accessory checkout/checkin to users
- `manage_categories` tool for category management across all item types
- `manage_manufacturers` tool for manufacturer information management
- `manage_models` tool for asset model management
- `manage_status_labels` tool for status label configuration
- `manage_locations` tool for physical location management
- `manage_suppliers` tool for supplier information management
- `manage_depreciations` tool for depreciation schedule management
- `SnipeITDirectAPI` class for extended API endpoint support

### Changed
- Updated snipeit-python-api dependency to GitHub source
- Expanded tool documentation in module docstring

## [0.1.0] - 2025-01-03

### Added
- Initial implementation of Snipe-IT MCP Server
- `manage_assets` tool for comprehensive asset CRUD operations
- `asset_operations` tool for asset state management (checkout, checkin, audit, restore)
- `asset_files` tool for file attachment management
- `asset_labels` tool for generating printable PDF labels
- `asset_maintenance` tool for maintenance record management
- `asset_licenses` tool for viewing licenses associated with assets
- `manage_consumables` tool for consumable CRUD operations
- Comprehensive error handling with structured responses
- Type-safe Pydantic models for all tool inputs
- Environment variable configuration for Snipe-IT credentials

### Technical Details
- Built with FastMCP 2.x
- Uses snipeit-python-api for backend API communication
- Python 3.11+ required
- UV package manager support
- Stdio transport for MCP communication

[0.3.0]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/v0.3.0
[0.2.0]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/v0.2.0
[0.1.0]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/v0.1.0
