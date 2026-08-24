# Snipe-IT MCP Server

A comprehensive [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for managing [Snipe-IT](https://snipeitapp.com/) inventory systems. This server enables AI assistants to perform full CRUD operations across your entire Snipe-IT instance with **40 tools** covering all major API endpoints.

## Features

### Asset Management
- **Full CRUD Operations**: Create, read, update, delete, and search assets with enhanced filtering
- **Barcode/Serial Lookup**: Direct bytag/byserial API endpoints for reliable barcode scanning
- **Asset Operations**: Checkout, checkin, audit, and restore assets
- **Checkout Requests**: Submit and cancel checkout requests for requestable assets
- **File Attachments**: Upload, download, list, and delete asset files
- **Label Generation**: Generate printable PDF labels
- **Maintenance Tracking**: Create and manage maintenance records
- **License Associations**: View licenses assigned to assets

### Inventory Tracking
- **Consumables**: Complete management of consumable items
- **Components**: Manage components with checkout/checkin to assets
- **Accessories**: Track accessories with checkout/checkin to users, assets, or locations

### Users & Organization
- **Users**: Full user management including restore and current user endpoint
- **User Assets**: View all items checked out to a user (assets, accessories, licenses, consumables, EULAs)
- **Two-Factor Auth**: Reset user 2FA (admin function)
- **Companies**: Multi-tenant company management
- **Departments**: Organizational department management
- **Groups**: Permission group management

### System Configuration
- **Categories**: Manage categories for all item types
- **Manufacturers**: Track manufacturer information
- **Models**: Define asset models with depreciation, custom fields, and file attachments
- **Status Labels**: Configure asset statuses with asset listing
- **Locations**: Manage physical locations with hierarchy, asset/user queries
- **Suppliers**: Track supplier information
- **Depreciations**: Define depreciation schedules

### Custom Fields
- **Fields**: Create and manage custom field definitions
- **Fieldsets**: Group custom fields for assignment to models with field reordering
- **Field Association**: Associate/disassociate fields with fieldsets

### Licensing
- **License Management**: Full CRUD for software licenses
- **Seat Assignments**: Checkout/checkin license seats
- **License Files**: Manage license documentation

### Reporting & Auditing
- **Activity Logs**: Query all activity history
- **Item Activity**: Get activity for specific items
- **Status Summary**: Asset counts grouped by status label
- **Audit Tracking**: Track assets due/overdue for audit

### Import & System Administration
- **CSV Imports**: Full import workflow (upload, map columns, process)
- **System Info**: Get Snipe-IT version information
- **Backups**: List and download database backups
- **LDAP Operations**: LDAP sync and connection testing

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

The server supports two authentication modes; pick one.

#### Mode A — API key (stdio or HTTP, single shared identity)

Create a `.env` file:

```env
SNIPEIT_URL=https://your-snipeit-instance.com
SNIPEIT_TOKEN=your-api-token-here
SNIPEIT_ALLOWED_TOOLS=manage_assets,system_info  # Optional: restrict exposed tools
```

| Variable | Required | Description |
|----------|----------|-------------|
| `SNIPEIT_URL` | Yes | Your Snipe-IT instance URL |
| `SNIPEIT_TOKEN` | Yes | API token for authentication |
| `SNIPEIT_ALLOWED_TOOLS` | No | Comma-separated list of tool names to expose. If unset, all tools are available. |

**Getting an API Token:**
1. Log in to your Snipe-IT instance
2. Navigate to your user profile (top right menu)
3. Go to "Manage API Keys" or "Personal Access Tokens"
4. Generate a new token with required permissions

#### Mode B — Interactive OAuth login (HTTP only, per-user identity)

In this mode the MCP server runs as a web service and acts as an OAuth proxy in
front of Snipe-IT's built-in [Laravel Passport](https://snipe-it.readme.io/) provider.
Each user logs in to Snipe-IT (going through your normal SAML / SSO if configured)
and the MCP server uses that user's own access token for every tool call.

**One-time Snipe-IT setup** (admin):
1. Visit `https://your-snipeit-instance.com/admin/oauth`
2. Create a new OAuth client
3. Set the redirect URI to `https://your-mcp-public-url/auth/callback`
4. Note the generated client ID and secret

**Environment variables:**

```env
SNIPEIT_URL=https://your-snipeit-instance.com
SNIPEIT_OAUTH_CLIENT_ID=...                  # from /admin/oauth
SNIPEIT_OAUTH_CLIENT_SECRET=...              # from /admin/oauth
SNIPEIT_MCP_BASE_URL=https://your-mcp-public-url
MCP_TRANSPORT=http
MCP_PORT=8000
# MCP_HOST=0.0.0.0                            # defaults to 127.0.0.1
```

| Variable | Required | Description |
|----------|----------|-------------|
| `SNIPEIT_URL` | Yes | Your Snipe-IT instance URL |
| `SNIPEIT_OAUTH_CLIENT_ID` | Yes | OAuth client ID from `/admin/oauth` |
| `SNIPEIT_OAUTH_CLIENT_SECRET` | Yes | OAuth client secret from `/admin/oauth` |
| `SNIPEIT_MCP_BASE_URL` | Yes | Public URL where this MCP server is reachable (used in the OAuth callback) |
| `SNIPEIT_MCP_REDIRECT_PATH` | No | Override OAuth callback path (default `/auth/callback`) |
| `MCP_TRANSPORT` | Yes | Must be `http` for OAuth mode |
| `MCP_HOST` | No | Bind address (default `127.0.0.1`; use `0.0.0.0` behind a reverse proxy) |
| `MCP_PORT` | Yes | TCP port for the HTTP server |
| `LOG_LEVEL` | No | `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL` (default `INFO`) |

> [!NOTE]
> OAuth mode requires HTTP transport — starting with `MCP_TRANSPORT=stdio`
> while OAuth env vars are set fails at startup with a clear error.

## Production Deployment

For running the server as a long-lived HTTPS service on a Linux VM (the typical
shape for OAuth mode), the repo ships two helper scripts under `scripts/`:

| Script | Purpose |
|--------|---------|
| [`scripts/setup-snipeit-mcp.sh`](scripts/setup-snipeit-mcp.sh) | One-shot installer. Creates a `snipeit-mcp` service user, installs [uv](https://github.com/astral-sh/uv) if missing, writes `/etc/snipeit-mcp.env` (seeding `SNIPEIT_*` values from a `.env` at the repo root if present), installs and starts a hardened systemd unit, and probes the local OAuth metadata endpoint. Idempotent. |
| [`scripts/update-snipeit-mcp.sh`](scripts/update-snipeit-mcp.sh) | Routine update — `git pull`, re-`uv sync`, restart the service, re-probe. |

**Quick-start on a fresh VM** (assumes Debian/Ubuntu with systemd; needs root):

```bash
# 1. Clone the source tree
sudo git clone https://github.com/jameshgordy/snipeit-mcp.git /opt/snipeit-mcp

# 2. (Optional) Drop a .env at the repo root so setup can seed
#    SNIPEIT_URL / SNIPEIT_OAUTH_CLIENT_ID / _SECRET / SNIPEIT_MCP_BASE_URL.
#    Missing values become __FILL_ME__ placeholders in /etc/snipeit-mcp.env.
scp .env you@vm:/tmp/snipeit-seed.env
sudo mv /tmp/snipeit-seed.env /opt/snipeit-mcp/.env

# 3. Install and start
sudo bash /opt/snipeit-mcp/scripts/setup-snipeit-mcp.sh

# 4. Future updates
sudo bash /opt/snipeit-mcp/scripts/update-snipeit-mcp.sh
```

> [!NOTE]
> The scripts are committed with the executable bit set, so
> `sudo /opt/snipeit-mcp/scripts/...` works once they're checked out via
> `git clone`. The `sudo bash ...` form above is the bullet-proof alternative
> — it doesn't care about file permissions, useful if you transferred the
> scripts via `scp`/drag-and-drop and the bit didn't come along.

**What the installer configures**:

| Path | Purpose |
|------|---------|
| `/opt/snipeit-mcp/` | Source tree (owned by service user) |
| `/var/lib/snipeit-mcp/` | `FASTMCP_HOME` — DCR'd MCP client registrations persist here |
| `/etc/snipeit-mcp.env` | Secrets and deployment-specific URLs (`SNIPEIT_*` only) |
| `/etc/systemd/system/snipeit-mcp.service` | systemd unit; infra settings (`MCP_TRANSPORT`, `MCP_HOST`, `MCP_PORT`, `LOG_LEVEL`, `FASTMCP_HOME`) are baked into its `Environment=` directives |

**Configurable at install time** via environment variables on the `setup-snipeit-mcp.sh` invocation:

| Variable | Default | Notes |
|----------|---------|-------|
| `SOURCE_DIR` | `/opt/snipeit-mcp` | Source tree path |
| `STATE_DIR` | `/var/lib/snipeit-mcp` | Service-user home / FASTMCP_HOME |
| `ENV_FILE` | `/etc/snipeit-mcp.env` | Generated env file |
| `SEED_ENV_FILE` | `$SOURCE_DIR/.env` | Optional seed for `SNIPEIT_*` values |
| `MCP_TRANSPORT` | `http` | Always `http` for OAuth mode |
| `MCP_HOST` | `127.0.0.1` | Bind address. Loopback by default; set `MCP_HOST=0.0.0.0` to expose on all interfaces (e.g. a reverse proxy on a different host) |
| `MCP_PORT` | `8000` | TCP port |
| `LOG_LEVEL` | `INFO` |  |

> [!IMPORTANT]
> The scripts do **not** configure TLS — the server listens on plain HTTP on
> the chosen `MCP_PORT`. For public OAuth use, terminate TLS in front of it
> (corporate reverse proxy, Caddy, nginx, …) with a trusted certificate for
> the hostname in `SNIPEIT_MCP_BASE_URL`.

### Exposing a VPN-only Snipe-IT to web-based MCP clients (DMZ reverse proxy)

Web-based MCP clients (Claude.ai, Mistral's Le Chat, …) run their MCP transport
through the client vendor's own backend, which needs to reach
`SNIPEIT_MCP_BASE_URL` from the public internet — a VPN-only address won't
work. If your Snipe-IT instance itself is VPN-only, the typical shape is to
keep the MCP VM internal and put a **public-facing reverse proxy in a DMZ** in
front of it:

```text
Web client backend ──HTTPS──► public reverse proxy (DMZ) ──HTTP──► MCP VM (internal) ──HTTPS──► Snipe-IT (internal)
```

What the DMZ proxy needs:

- **Public hostname** matching `SNIPEIT_MCP_BASE_URL` (e.g. `snipeit.mcp.example.com`).
- **Trusted TLS certificate** for that hostname — client backends will not
  accept internal CAs.
- **Upstream**: the internal VM on `http://<vm-ip>:<MCP_PORT>`.
- **Forwarded headers**: `Host`, `X-Forwarded-Proto: https`, `X-Forwarded-Host`,
  `X-Forwarded-For`. FastMCP uses these to build correct OAuth metadata URLs.
- **Do not strip `WWW-Authenticate`** from upstream responses — MCP clients
  (Inspector, `mcp-remote`, web clients) rely on it to discover the OAuth flow.
  Header-allowlist proxies are a common culprit.
- **Do not add CORS headers** — FastMCP handles its own.

> [!NOTE]
> **VPN is still required for the initial Snipe-IT login.** The OAuth flow
> redirects the user's browser to `https://<your-snipeit>/oauth/authorize` for
> sign-in (and SSO bounce), which is VPN-only by definition. Once the user has
> signed in once, subsequent MCP tool calls and refresh-token rotation go
> client backend → DMZ → MCP VM → Snipe-IT entirely server-side, so users can
> keep using the web client from anywhere until the refresh token expires or
> is revoked, at which point a one-time VPN reconnect is needed to re-login.

## MCP Client Configuration

The right configuration depends on whether the server runs in **API-key mode** (stdio,
local, one shared identity) or **OAuth mode** (HTTP, remote, per-user identity).
See the previous section for how the server picks between them.

### Claude Desktop / Claude Code — API-key mode (stdio)

Add to your MCP configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

**Option A: Install directly from GitHub (no clone required)**

```json
{
  "mcpServers": {
    "snipeit": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/jameshgordy/snipeit-mcp",
        "snipeit-mcp"
      ],
      "env": {
        "SNIPEIT_URL": "https://your-snipeit-instance.com",
        "SNIPEIT_TOKEN": "your-api-token-here"
      }
    }
  }
}
```

**Option B: Run from a local clone**

```json
{
  "mcpServers": {
    "snipeit": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/snipeit-mcp",
        "run",
        "snipeit-mcp"
      ],
      "env": {
        "SNIPEIT_URL": "https://your-snipeit-instance.com",
        "SNIPEIT_TOKEN": "your-api-token-here"
      }
    }
  }
}
```

### Claude Desktop / Claude Code — OAuth mode (via `mcp-remote`)

When the server runs in OAuth mode it speaks HTTP, not stdio, so it cannot be
launched directly by Claude Desktop. Use [`mcp-remote`](https://www.npmjs.com/package/mcp-remote)
as a stdio bridge — it handles Dynamic Client Registration, opens the browser
for interactive login, caches the resulting tokens, and refreshes them
transparently. The server must already be running and reachable at the URL below
(e.g. on a VM, behind a reverse proxy, or on `localhost` for dev).

```json
{
  "mcpServers": {
    "snipeit": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://your-mcp-public-url/mcp"
      ]
    }
  }
}
```

> [!NOTE]
> No `SNIPEIT_*` env vars belong here — the server holds them. The first
> connection opens a browser tab for Snipe-IT login (going through your SSO if
> configured); subsequent connections reuse the cached refresh token.

### Claude.ai web (OAuth mode only)

Open https://claude.ai → Settings → **Connectors** → **Add custom connector**.
Paste the public URL of your running MCP server (e.g. `https://your-mcp-public-url/mcp`)
and follow the OAuth prompt.

> [!IMPORTANT]
> Claude.ai web requires the MCP server to be reachable from the public
> internet over HTTPS — `localhost` and unencrypted HTTP do not work here.
> Use the [`mcp-remote` bridge](#claude-desktop--claude-code--oauth-mode-via-mcp-remote)
> instead if you only have a localhost deployment.

### Cursor

Add to your Cursor MCP settings using the same JSON shape as the Claude Desktop
examples above — stdio (API-key) or `mcp-remote` bridge (OAuth) — whichever matches
your server mode.

### MCP Inspector (debugging)

```bash
npx @modelcontextprotocol/inspector
```

Then in the Inspector UI:

- **Transport Type**: `Streamable HTTP`
- **URL**: your server's `/mcp` endpoint
- **Connection Type**: must be **Via Proxy**, not **Direct**

> [!NOTE]
> **Why "Via Proxy"?** The Inspector UI is a static frontend served at
> `http://localhost:6274` and the MCP server lives at a different origin
> (e.g. `http://localhost:8000`). In **Direct** mode the browser tries to talk
> to the MCP server itself, which fails for two compounding reasons: (a)
> FastMCP doesn't emit CORS headers for the Inspector origin, so requests are
> blocked client-side, and (b) the OAuth redirect flow needs server-side state
> the browser-only client can't keep. **Via Proxy** routes traffic through
> Inspector's own backend (at `localhost:6277`), which is same-origin from
> the MCP server's perspective and handles OAuth state correctly.

<!-- separates the two adjacent GH alerts -->

> [!WARNING]
> Leave **Client ID** and **Client Secret** in the OAuth panel **empty** —
> Inspector will perform Dynamic Client Registration with the MCP server.
> Pasting your Snipe-IT (upstream) client_id and secret there is the most
> common misconfiguration; those credentials belong only in the server's
> `.env`, not in any MCP client.

## Available Tools (40 Total)

### Asset Tools (8)

| Tool | Description |
|------|-------------|
| `manage_assets` | CRUD operations with bytag/byserial lookup and advanced filtering |
| `asset_operations` | State operations (checkout, checkin, audit, restore) |
| `bulk_asset_operations` | Bulk edit and bulk audit across many assets at once (Snipe-IT v8.7+) |
| `asset_files` | File attachments (upload, list, download, delete) |
| `asset_labels` | Generate printable PDF labels |
| `asset_maintenance` | Full maintenance lifecycle (create, list, get, update, delete, complete) |
| `asset_licenses` | View licenses assigned to an asset |
| `asset_requests` | Submit/cancel checkout requests, list own requests and requestable assets |

### Inventory Tools (5)

| Tool | Description |
|------|-------------|
| `manage_consumables` | CRUD operations for consumables |
| `manage_components` | CRUD operations for components |
| `component_operations` | Checkout/checkin components to assets |
| `manage_accessories` | CRUD operations for accessories |
| `accessory_operations` | Checkout/checkin accessories to users, assets, or locations |

### Kit Tools (1)

| Tool | Description |
|------|-------------|
| `manage_kits` | CRUD for predefined kits plus kit content management (models, licenses, accessories, consumables) |

### User & Organization Tools (6)

| Tool | Description |
|------|-------------|
| `manage_users` | CRUD operations for users (+ restore, me) |
| `user_assets` | Get items checked out to a user (assets, accessories, licenses, consumables, eulas) |
| `user_two_factor` | Reset user two-factor authentication |
| `manage_companies` | CRUD operations for companies |
| `manage_departments` | CRUD operations for departments |
| `manage_groups` | CRUD operations for permission groups |

### Configuration Tools (7)

| Tool | Description |
|------|-------------|
| `manage_categories` | Manage categories for all item types |
| `manage_manufacturers` | Manage manufacturer information |
| `manage_models` | Manage asset models (+ list assets by model) |
| `manage_status_labels` | Manage status labels (+ list assets by status) |
| `manage_locations` | Manage locations (+ list assets/users by location) |
| `manage_suppliers` | Manage supplier information |
| `manage_depreciations` | Manage depreciation schedules |

### Custom Field Tools (2)

| Tool | Description |
|------|-------------|
| `manage_fields` | CRUD + associate/disassociate fields with fieldsets |
| `manage_fieldsets` | CRUD operations for fieldsets (+ field listing, reorder) |

### License Tools (3)

| Tool | Description |
|------|-------------|
| `manage_licenses` | CRUD operations for licenses |
| `license_seats` | Manage license seat assignments |
| `license_files` | Manage license file attachments |

### Reporting & Audit Tools (3)

| Tool | Description |
|------|-------------|
| `activity_reports` | Query activity logs and item history |
| `status_summary` | Get asset counts grouped by status label |
| `audit_tracking` | Track assets due/overdue for audit |

### Import Tools (1)

| Tool | Description |
|------|-------------|
| `manage_imports` | CSV import workflow (upload, map columns, process) |

### System Administration Tools (4)

| Tool | Description |
|------|-------------|
| `system_info` | Get Snipe-IT version information |
| `manage_backups` | List and download database backups |
| `ldap_operations` | LDAP sync and connection testing |
| `model_files` | Manage file attachments for asset models |

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

**Success (create):**
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

**Success (list):**

All list endpoints return pagination metadata:
```json
{
  "success": true,
  "action": "list",
  "count": 3,
  "total": 1602,
  "limit": 20,
  "offset": 0,
  "has_more": true,
  "assets": [ ... ]
}
```

| Field | Description |
|-------|-------------|
| `count` | Number of items in this page |
| `total` | Total items matching the query |
| `limit` | Page size used |
| `offset` | Starting offset |
| `has_more` | `true` if more pages remain |

**Error:**
```json
{
  "success": false,
  "error": "Asset not found: Asset with tag LAP-999 not found."
}
```

## Architecture

```
src/snipeit_mcp/
├── __init__.py        # Public API re-exports
├── __main__.py        # Entry point (snipeit-mcp script)
├── mcp_server.py      # FastMCP instance + tool whitelist
├── client.py          # SnipeIT API clients
├── schemas.py         # Pydantic input schemas
└── tools/             # 10 modules grouped by Snipe-IT domain
    ├── assets.py
    ├── inventory.py
    ├── foundational.py
    ├── licenses.py
    ├── people.py
    ├── custom_fields.py
    ├── reports.py
    ├── imports.py
    └── system.py
```

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
