# Snipe-IT MCP Enhancement Prompts

Claude Code prompts to enhance the snipeit-mcp server from v0.3.0 to v0.4.0.

## Execution Order

Work through these in order - earlier prompts have higher impact:

| # | File | Priority | Description |
|---|------|----------|-------------|
| 1 | `01-asset-lookup-methods.md` | **High** | Asset lookup by tag/serial, enhanced filtering |
| 2 | `02-import-management.md` | **High** | CSV import workflow (upload → map → process) |
| 3 | `03-relationship-endpoints.md` | Medium | Location/status/model → assets queries |
| 4 | `04-checkout-requests.md` | Medium | Self-service asset request workflow |
| 5 | `05-user-relationships.md` | Medium | Extended user queries, 2FA reset |
| 6 | `06-audit-tracking.md` | Medium | Due/overdue audit tracking |
| 7 | `07-settings-system.md` | Low | Version info, backups, LDAP sync |
| 8 | `08-model-files.md` | Low | File attachments for models |
| 9 | `09-field-ordering.md` | Low | Custom field display ordering |

## Usage

1. Add these files to your Claude Code project
2. Open the snipeit-mcp repository
3. Work through each prompt in order
4. Test each implementation before moving to next

## Expected Outcome

After completing all prompts, the MCP should have:

- **~35-40 tools** (up from 29)
- Full barcode/scanning workflow support
- Bulk import capability
- Relationship-based queries for dashboards
- Self-service request workflow
- Audit compliance tracking
- System administration functions

## Notes

- All prompts use the existing `SnipeITDirectAPI` class pattern
- Some endpoints are undocumented - may need testing
- LDAP and backup features require admin-level API tokens
- Checkout request approval remains web-only (API limitation)
