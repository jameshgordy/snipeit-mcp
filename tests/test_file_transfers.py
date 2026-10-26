"""End-to-end tests for file upload/download paths, mocking only HTTP.

Model, license and import files go through the real ``SnipeITDirectAPI``
(``upload_files`` / ``download_file``) via ``responses``, so the exact
Snipe-IT v8.8.1 routes and multipart field names are asserted on the wire.
Backups still call ``requests`` directly and are checked with a patched module
(a missing ``import requests`` there once slipped past the suite, PR #10).
"""

from unittest.mock import MagicMock, patch


def get_tool_fn(tool):
    return tool.fn if hasattr(tool, "fn") else tool


def _stub_response(content=b"binary-payload", json_payload=None):
    resp = MagicMock()
    resp.content = content
    resp.json.return_value = json_payload or {"status": "success"}
    resp.raise_for_status = MagicMock()
    return resp


BASE = "https://test.snipeit.com/api/v1"


def _multipart_parts(request, field):
    return request.body.count(f'name="{field}"'.encode())


class TestModelFilesTransfer:
    """End-to-end through the real SnipeITDirectAPI (v8.8.1 generic file routes)."""

    def test_upload_sends_file_array(self, tmp_path):
        import responses
        from snipeit_mcp import model_files

        f = tmp_path / "manual.pdf"
        f.write_bytes(b"pdf-bytes")
        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, f"{BASE}/models/1/files",
                     json={"status": "success", "payload": {}})
            result = get_tool_fn(model_files)(action="upload", model_id=1, file_path=str(f))
            request = rsps.calls[0].request

        assert result["success"] is True
        assert request.headers["Authorization"] == "Bearer test-token-12345"
        assert request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
        assert _multipart_parts(request, "file[]") == 1
        assert b'filename="manual.pdf"' in request.body and b"pdf-bytes" in request.body

    def test_upload_status_error_is_failure(self, tmp_path):
        """Regression: a single ``file`` field got HTTP 200 status=error, reported as success."""
        import responses
        from snipeit_mcp import model_files

        f = tmp_path / "manual.pdf"
        f.write_bytes(b"x")
        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, f"{BASE}/models/1/files",
                     json={"status": "error", "messages": "No files were submitted"})
            result = get_tool_fn(model_files)(action="upload", model_id=1, file_path=str(f))

        assert result["success"] is False
        assert "No files were submitted" in result["error"]

    def test_list_maps_note(self):
        import responses
        from snipeit_mcp import model_files

        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, f"{BASE}/models/1/files", json={
                "total": 1,
                "rows": [{"id": 42, "filename": "manual.pdf", "url": "u",
                          "created_at": None, "note": "datasheet"}],
            })
            result = get_tool_fn(model_files)(action="list", model_id=1)

        assert result["success"] is True
        assert result["files"] == [{"id": 42, "filename": "manual.pdf", "url": "u",
                                    "created_at": None, "notes": "datasheet"}]

    def test_download_saves_file(self, tmp_path):
        import responses
        from snipeit_mcp import model_files

        save_path = tmp_path / "out" / "manual.pdf"
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, f"{BASE}/models/1/files/42", body=b"file-bytes",
                     content_type="application/pdf")
            result = get_tool_fn(model_files)(
                action="download", model_id=1, file_id=42, save_path=str(save_path)
            )
            request = rsps.calls[0].request

        assert result["success"] is True
        assert save_path.read_bytes() == b"file-bytes"
        assert request.headers["Authorization"] == "Bearer test-token-12345"

    def test_download_status_error_writes_nothing(self, tmp_path):
        import responses
        from snipeit_mcp import model_files

        save_path = tmp_path / "manual.pdf"
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, f"{BASE}/models/1/files/42",
                     json={"status": "error", "messages": "Invalid file ID"})
            result = get_tool_fn(model_files)(
                action="download", model_id=1, file_id=42, save_path=str(save_path)
            )

        assert result["success"] is False
        assert "Invalid file ID" in result["error"]
        assert not save_path.exists()

    def test_delete_uses_delete_suffix(self):
        import responses
        from snipeit_mcp import model_files

        with responses.RequestsMock() as rsps:
            rsps.add(responses.DELETE, f"{BASE}/models/1/files/42/delete",
                     json={"status": "success", "messages": "File deleted"})
            result = get_tool_fn(model_files)(action="delete", model_id=1, file_id=42)

        assert result["success"] is True


class TestLicenseFilesTransfer:
    """Regression: licenses used ``/upload`` and ``/uploads``, which v8.8.1 does not route."""

    def test_upload_sends_file_array(self, tmp_path):
        import responses
        from snipeit_mcp import license_files

        f = tmp_path / "license.pdf"
        f.write_bytes(b"license-bytes")
        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, f"{BASE}/licenses/5/files",
                     json={"status": "success", "payload": {}})
            result = get_tool_fn(license_files)(action="upload", license_id=5, file_path=str(f))
            request = rsps.calls[0].request

        assert result["success"] is True
        assert request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
        assert _multipart_parts(request, "file[]") == 1
        assert b'filename="license.pdf"' in request.body

    def test_list(self):
        import responses
        from snipeit_mcp import license_files

        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, f"{BASE}/licenses/5/files",
                     json={"total": 1, "rows": [{"id": 9, "filename": "license.pdf",
                                                 "note": "key"}]})
            result = get_tool_fn(license_files)(action="list", license_id=5)

        assert result["success"] is True
        assert result["count"] == 1
        assert result["files"][0]["notes"] == "key"

    def test_download_saves_file(self, tmp_path):
        import responses
        from snipeit_mcp import license_files

        save_path = tmp_path / "license.pdf"
        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, f"{BASE}/licenses/5/files/9", body=b"file-bytes",
                     content_type="application/pdf")
            result = get_tool_fn(license_files)(
                action="download", license_id=5, file_id=9, save_path=str(save_path)
            )

        assert result["success"] is True
        assert save_path.read_bytes() == b"file-bytes"

    def test_delete_uses_delete_suffix(self):
        import responses
        from snipeit_mcp import license_files

        with responses.RequestsMock() as rsps:
            rsps.add(responses.DELETE, f"{BASE}/licenses/5/files/9/delete",
                     json={"status": "success", "messages": "File deleted"})
            result = get_tool_fn(license_files)(action="delete", license_id=5, file_id=9)

        assert result["success"] is True


class TestManageImportsUpload:
    def test_upload_sends_files_array(self, tmp_path):
        """Regression: ImportController::store loops over ``files[]``; ``file`` got a 422."""
        import responses
        from snipeit_mcp import manage_imports

        f = tmp_path / "assets.csv"
        f.write_text("asset_tag,name\nA1,Laptop\n")
        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, f"{BASE}/imports", json={"files": [{"id": 12}]})
            result = get_tool_fn(manage_imports)(action="upload", file_path=str(f))
            request = rsps.calls[0].request

        assert result["success"] is True
        assert result["import"] == {"files": [{"id": 12}]}
        assert request.headers["Authorization"] == "Bearer test-token-12345"
        assert request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
        assert _multipart_parts(request, "files[]") == 1
        assert b'filename="assets.csv"' in request.body

    def test_upload_422_is_failure(self, tmp_path):
        import responses
        from snipeit_mcp import manage_imports

        f = tmp_path / "assets.csv"
        f.write_text("x")
        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, f"{BASE}/imports", status=422,
                     json={"status": "error", "messages": "No files were submitted"})
            result = get_tool_fn(manage_imports)(action="upload", file_path=str(f))

        assert result["success"] is False
        assert "No files were submitted" in result["error"]


class TestManageBackupsDownload:
    def test_download_invokes_requests_with_bearer_token(self, mock_direct_api, tmp_path):
        from snipeit_mcp import manage_backups

        mock_direct_api.base_url = "https://test.snipeit.com"
        mock_direct_api.headers = {"Authorization": "Bearer test-token-12345"}
        save_path = tmp_path / "backups" / "backup.sql"

        with patch("snipeit_mcp.tools.system.requests") as req:
            req.get.return_value = _stub_response(content=b"sql-dump")
            result = get_tool_fn(manage_backups)(
                action="download", filename="backup.sql", save_path=str(save_path)
            )

        assert result["success"] is True
        assert save_path.read_bytes() == b"sql-dump"
        req.get.assert_called_once()
        call = req.get.call_args
        assert call.args[0] == "https://test.snipeit.com/api/v1/settings/backups/download/backup.sql"
        assert call.kwargs["headers"]["Authorization"] == "Bearer test-token-12345"
