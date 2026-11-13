# snipeit-mcp

MCP server (FastMCP 3) exposing the Snipe-IT API as tools. Source in
`src/snipeit_mcp` (tools in `tools/`, HTTP client in `client.py`), tests in `tests/`.

## Testing

- Run the full suite before every commit: `python -m pytest tests/ -q`
  (locally: `.venv/bin/python -m pytest tests/ -q`).
- Verify every endpoint and payload against the Snipe-IT source at its current
  release tag (grokability/snipe-it `routes/api.php` and the Api controllers),
  not docs or memory. The API drifts between versions.
- Unit tests assert the exact endpoint and payload (`assert_called_with`), not
  just `success is True`.
- For end-to-end checks, use the `responses` library against the real
  `SnipeITDirectAPI` and tool code, mocking only HTTP. Remember that Snipe-IT
  often returns HTTP 200 with `{"status": "error"}`; `_request` raises on that.
- Known: kit checkout and requestable accessories are UI-only (no API routes).

## Releases

- One version per logical change (bugfix batch, feature batch): branch, PR,
  full test pass, merge with a merge commit (not squash), tag, GitHub release.
- Tags are `X.Y` (patch releases `X.Y.Z`); release titles are `vX.Y.Z`. Pushing
  a tag builds the Docker image (`.github/workflows/build.yml`).
- Keep the `pyproject.toml` version and `CHANGELOG.md` (Keep a Changelog) in sync.
