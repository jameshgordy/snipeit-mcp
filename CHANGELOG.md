# Changelog

All notable changes to the Snipe-IT MCP Server will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-09-28

No breaking changes: the major version marks the new optional judgment-model
capability. Existing configurations, tools, and payloads behave exactly as in
1.9.0; the two new tools appear only when a backend is configured.

### Added
- **Data-quality tools backed by a judgment model** (optional). The tools ask
  typed questions with a probability per option and are hidden from
  `tools/list` until a backend is configured, so an unconfigured server
  presents the same 40 tools as before.
  - `find_duplicates`: pairwise duplicate detection over manufacturers, models,
    suppliers, locations, categories, companies or departments. Candidate pairs
    are chosen in code (all pairs for small tables; token/prefix blocking with a
    lexical-similarity threshold otherwise, capped by `max_pairs` and at 20 000
    comparisons), then judged on a three-level entity-alignment rubric
    (different / possibly the same / same) plus a name-variant probability.
    Returns `duplicates`, `review` and `different_count` with score, confidence,
    confidence band, both records (with item counts) and a per-type
    `resolution_hint` for merging in Snipe-IT. Categories of different types
    are never compared; models sharing a `model_number` are always compared.
  - `match_records`: resolves free-text names to existing record ids. The
    lexically closest records (default 50, max 254) are offered as options
    together with an explicit `none`; verdicts `accept` (confidence ≥ 0.9),
    `review`, `none`. A choice outside the offered options is reported as an
    error, never as a match.
  - Both tools are read-only with respect to Snipe-IT, report `backend`,
    `model`, `calibrated`, `confidence_source`, `usage` and `elapsed_seconds`,
    and stop submitting work when `JUDGMENT_TIME_BUDGET` (default 300 s) runs
    out, listing skipped items in `errors`. Users are deliberately not
    supported (personal data).
- **Pluggable judgment backends** (`snipeit_mcp.judgment`, selected with
  `JUDGMENT_BACKEND`), no new dependencies:
  - `systemone` (default): the `POST /v1/systemone` protocol of TypeSafe Jev,
    also served by self-hosted open-weight System One models (Laya, CLM,
    Rapid-MLX, openjev). Calibrated probabilities. The `TYPESAFE_API_KEY`,
    `TYPESAFE_BASE_URL`, `TYPESAFE_DEFAULT_MODEL` and `TYPESAFE_TIMEOUT`
    variables of the official SDK are accepted as aliases, so a plain
    `TYPESAFE_API_KEY` enables Jev. Wire contract verified against
    `typesafe-sdk` 0.7.2.
  - `openai`: any OpenAI-compatible `/chat/completions` server with JSON-schema
    structured outputs (Ollama, vLLM, LM Studio, llama.cpp, OpenRouter,
    OpenAI). Questions are rendered into a prompt with a strict response
    schema; the reply is validated against the question definitions and
    converted to the System One answer shapes. Confidence is the model's
    self-reported value, or vote frequency across `JUDGMENT_SAMPLES` runs; both
    are reported as `calibrated: false`.
  - Shared HTTP plumbing: pooled `requests.Session` per backend, retries on
    408/429/5xx and all transport errors (2 retries, exponential backoff,
    `Retry-After` / `retry-after-ms` honoured), readable error messages for
    401/404/422/429 with configuration hints.
- Snipe-IT list pagination for the new tools terminates on the server-reported
  total rather than on a short page, so instances with `MAX_RESULTS` below 500
  are still fully scanned. Endpoints, transformer fields and the page cap
  verified against Snipe-IT v8.7.2.
- README: "Data Quality" feature section and an "Optional — judgment backend for
  the data-quality tools" configuration section with a backend comparison
  table, per-backend examples, a data-leaves-your-network warning, cost/limit
  notes and how to read confidence bands and the `calibrated` flag.

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

[1.8.0]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/1.8
[1.7.1]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/1.7.1
[1.7.0]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/1.7
[1.2.0]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/v1.2.0
[0.3.0]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/v0.3.0
[0.2.0]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/v0.2.0
[0.1.0]: https://github.com/jameshgordy/snipeit-mcp/releases/tag/v0.1.0
