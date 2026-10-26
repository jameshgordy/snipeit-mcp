# Changelog

All notable changes to the Snipe-IT MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.9.3] - 2026-10-26

### Fixed
`manage_imports` brought in line with Snipe-IT v8.8.1, whose `ImportController`
has only `index`, `store`, `process` and `destroy`.
- `list` crashed with `'list' object has no attribute 'get'`: the index returns
  a bare JSON array, not `{rows: [...]}`.
- `get` called `GET imports/{id}`, which is routed but has no controller method
  (HTTP 500). It now picks the import out of the list, which already carries
  the header row, first row and saved mapping.
- `process` sent no body, so Snipe-IT rejected it ("The import-type field is
  required"). It now takes `import_data` and sends `import-type`,
  `column-mappings`, `run-backup`, `import-update`, `import-preserve-blanks`
  and `send-welcome`. Row errors (HTTP 500 `{"status": "import-errors"}`) are
  reported with Snipe-IT's messages and tally instead of a bare "500 Server Error".

### Removed
- `manage_imports` `update`: `PATCH imports/{id}` has no controller method
  (HTTP 500). Snipe-IT saves the column mapping when the import is processed,
  so pass `import_data` to `process` instead.

### Changed
- `ImportData.import_type` accepts every v8.8.1 importer (adds `assetHistory`,
  `assetModel`, `supplier`, `manufacturer`, `category`); new `update_existing`,
  `preserve_blanks` and `send_welcome` options.

## [1.9.2] - 2026-10-26

### Fixed
File tools brought in line with Snipe-IT v8.8.1, which routes every object's
files through `{type}/{id}/files` (`UploadedFilesController`).
- `model_files` `upload` sent a single `file` field. The controller loops over
  `file[]`, so nothing was attached, yet the tool reported success because it
  never checked Snipe-IT's HTTP 200 `{"status": "error"}`. It now uses
  `SnipeITDirectAPI.upload_files`. `delete` now calls
  `DELETE models/{id}/files/{file_id}/delete` (the `/delete` was missing).
- `license_files` called `licenses/{id}/upload` and `licenses/{id}/uploads[/{file_id}]`,
  which v8.8.1 does not route. Upload, list, download and delete now use
  `licenses/{id}/files`, `.../files/{file_id}` and `.../files/{file_id}/delete`.
- `manage_imports` `upload` sent `file`. `ImportController::store` loops over
  `files[]`, so Snipe-IT answered 422 "no files". It now sends `files[]`.
- `model_files` / `license_files` `list` returned `notes: null` for every file;
  the API field is `note`.
- `model_files` / `license_files` `download` saved Snipe-IT's JSON error body
  (HTTP 200 `{"status": "error"}`) as the downloaded file. The new
  `SnipeITDirectAPI.download_file` raises on it instead.

### Changed
- `SnipeITDirectAPI.upload_files` takes a `field` argument (default `file[]`).

## [1.9.1] - 2026-10-26

### Fixed
- `asset_files` `upload` failed every time with "Snipe-IT error: Invalid JSON"
  and attached nothing. The snipeit-api SDK's `assets.upload_files` posts
  multipart through a session whose default `Content-Type: application/json`
  replaces the multipart boundary. Uploads now go through the new
  `SnipeITDirectAPI.upload_files`, which sends `file[]` multipart fields to
  `POST /api/v1/hardware/{id}/files` without the JSON content type and raises
  on Snipe-IT's HTTP 200 `{"status": "error"}` replies like `_request` does.

## [1.9.0] - 2026-08-27

### Added
- **Multi-identity mode** (Mode C, `AuthMode.MULTI_IDENTITY`): one container
  serves all people, each with their own Snipe-IT personal access token.
  Identities come from `SNIPEIT_IDENTITY_<KEY>_*` environment variables (or a
  `SNIPEIT_IDENTITIES_FILE` JSON file, which wins over env vars). The HTTP
  auth layer validates `Authorization: Bearer <mcp_token>` per request
  (401 + `WWW-Authenticate: Bearer` before any tool runs, constant-time token
  comparison) and resolves the request's Snipe-IT PAT via a request-scoped
  context variable. Supports per-identity tool allowlists and a read-only
  flag (enforced at call time and in `tools/list`), plus an unauthenticated
  `GET /healthz` endpoint for healthchecks.
- **Audit log**: one JSON line per tool call on the `snipeit_mcp.audit`
  logger (stderr) — identity, tool, action, outcome, duration, and a SHA-256
  digest of the arguments. Arguments themselves and any token values are
  never logged.
- `deploy/docker-compose.yml`: one-container multi-identity deployment
  example — no published ports, networks `egress` + external
  `metamcp_metamcp-internal`, healthcheck against `/healthz`.
- `.github/workflows/build.yml`: builds and pushes
  `ghcr.io/jameshgordy/snipeit-mcp:<tag>` and `:latest` (linux/amd64) on
  version tags.

### Changed
- Pinned the `snipeit-api` dependency from `@main` to the fixed commit
  `11cd643d6c961fe51ca91a5f9e1a688e5c9a4a30` (the version already in the lock
  file). Upstream main has moved past this SHA since (96 commits, including a
  breaking httpx-based client migration towards snipeit-api 0.2) — adopting
  it is a deliberate follow-up, not a silent bump.
- `SnipeITAuthConfig.from_env()` now resolves in the order OAuth →
  multi-identity → API key; configuring OAuth **and** identities fails at
  startup (mutually exclusive). Multi-identity mode requires HTTP transport,
  analogous to OAuth.

## [1.8.0] - 2026-08-24

### Added
- **Predefined Kits** (`manage_kits`): CRUD for kits plus kit content
  management — attach/detach/re-quantity models, licenses, accessories, and
  consumables. (Kit checkout has no API endpoint in Snipe-IT; it remains
  UI-only.)
- **Bulk Asset Operations** (`bulk_asset_operations`): bulk edit
  (`PATCH /hardware/bulk`) and bulk audit (`POST /hardware/audit/bulk`) across
  many assets at once — both endpoints added in Snipe-IT v8.7.
- **Maintenance lifecycle** (`asset_maintenance`): new `list`, `get`, `update`,
  `delete`, and `complete` actions alongside `create` (complete requires
  Snipe-IT v8.7+).
- **Checkout request queries** (`asset_requests`): new `list` (own pending
  requests) and `requestable` (assets the user may request) actions.
- List responses now include `total_pages` and `current_page` in their
  pagination metadata.

### Changed
- `asset_maintenance` create now uses the `/maintenances` API directly and
  sends the completion date under both `completion_date` (pre-v8.7) and
  `expected_completion_date` (v8.7 renamed the field), so it works on either
  side of the rename.

### Fixed
- `asset_requests` was calling `hardware/{id}/request` endpoints that do not
  exist in Snipe-IT v8; it now uses the correct `account/request/{id}` and
  `account/request/{id}/cancel` routes.

## [1.7.1] - 2026-08-24

### Fixed
- `status_summary` no longer calls the removed `statuslabels/assets` endpoint
  (gone in Snipe-IT v8); it now aggregates `assets_count` from the paginated
  `statuslabels` listing and returns `summary`, `status_labels`, and
  `total_assets`. Fixes #18.
- Direct API requests now raise an error when Snipe-IT returns HTTP 200 with a
  `{"status": "error", ...}` payload, so wrapped API failures are no longer
  reported as `"success": true`.

## [1.7.0] - 2026-06-08

### Changed
- Upgraded the FastMCP dependency to 3.x (`fastmcp>=3.0.0,<4.0.0`); FastMCP 2.x
  is no longer supported. The `SNIPEIT_ALLOWED_TOOLS` whitelist was reworked to
  use FastMCP 3's tool visibility controls (`enable`/`disable`) in place of the
  removed private tool registry — disabled tools stay registered but are hidden
  from clients — and behaves the same as before from a user's perspective. The
  public tool set, input schemas, and stdio transport are unchanged.

## [1.2.0] - 2025-01-21

### Added
- **Asset Lookup Enhancements**
  - Direct bytag/byserial API endpoints for reliable barcode scanning workflows
  - Filter parameters: status_id, model_id, company_id, location_id, category_id, manufacturer_id, assigned_to
  - Documented sortable columns for asset listing

- **CSV Import Management** (`manage_imports`)
  - Upload CSV files for bulk import
  - Map columns to Snipe-IT fields
  - Process imports with optional database backup
  - List, get, update, and delete import files

- **Relationship Query Endpoints**
  - `manage_locations`: Added `assets` and `users` actions to list items by location
  - `manage_status_labels`: Added `assets` action to list assets by status
  - `manage_models`: Added `assets` action to list assets by model
  - `status_summary`: New tool to get asset counts grouped by status label

- **Asset Checkout Requests** (`asset_requests`)
  - Submit checkout requests for requestable assets
  - Cancel pending checkout requests

- **User Management Enhancements**
  - `user_assets`: Added `consumables` and `eulas` options
  - `user_two_factor`: New tool to reset user 2FA (admin function)

- **Audit Tracking** (`audit_tracking`)
  - List assets due for audit
  - List overdue assets
  - Summary view with counts and sample assets

- **System Administration Tools**
  - `system_info`: Get Snipe-IT version information
  - `manage_backups`: List and download database backups
  - `ldap_operations`: LDAP sync and connection testing

- **Model File Attachments** (`model_files`)
  - Upload, list, download, and delete files attached to asset models

- **Custom Field Ordering**
  - `manage_fieldsets`: Added `reorder` action to control field display order

- **New Pydantic Models**
  - `ImportData` for import configuration
  - `AssetRequestData` for checkout request details

### Changed
- Server now provides 39 comprehensive tools (up from 29)
- Updated module docstring with complete tool listing
- Version bumped to 1.2.0

### Technical
- Added test suite with pytest
- Added test dependencies as optional extras

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

[1.9.3]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/1.9.3
[1.9.2]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/1.9.2
[1.9.1]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/1.9.1
[1.8.0]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/1.8
[1.7.1]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/1.7.1
[1.7.0]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/1.7
[1.2.0]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/v1.2.0
[0.3.0]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/v0.3.0
[0.2.0]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/v0.2.0
[0.1.0]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/v0.1.0
