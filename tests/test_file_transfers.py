"""Regression tests for upload/download paths that call ``requests`` directly.

These code paths bypass the Snipe-IT SDK and the ``_client.get_direct_api()``
helper, so a missing ``import requests`` or bare ``SNIPEIT_TOKEN`` reference
in one of the tool modules would surface only at runtime. The mock-API tests
in ``test_admin.py`` / ``test_licensing.py`` exercise only the early-return
validation branches and the ``api._request(...)`` paths, which is why a prior
NameError regression slipped past the suite (PR #10 review). The tests below
drive the bare-``requests`` branches end-to-end.
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


class TestModelFilesTransfer:
    def test_upload_invokes_requests_with_bearer_token(self, mock_direct_api, tmp_path):
        from snipeit_mcp import model_files

        mock_direct_api.base_url = "https://test.snipeit.com"
        upload_path = tmp_path / "manual.pdf"
        upload_path.write_bytes(b"pdf-bytes")

        with patch("snipeit_mcp.tools.foundational.requests") as req:
            req.post.return_value = _stub_response(json_payload={"id": 7})
            result = get_tool_fn(model_files)(
                action="upload", model_id=1, file_path=str(upload_path)
            )

        assert result["success"] is True
        req.post.assert_called_once()
        call = req.post.call_args
        assert call.args[0] == "https://test.snipeit.com/api/v1/models/1/files"
        assert call.kwargs["headers"]["Authorization"] == "Bearer test-token-12345"

    def test_download_invokes_requests_with_bearer_token(self, mock_direct_api, tmp_path):
        from snipeit_mcp import model_files

        mock_direct_api.base_url = "https://test.snipeit.com"
        save_path = tmp_path / "out" / "manual.pdf"

        with patch("snipeit_mcp.tools.foundational.requests") as req:
            req.get.return_value = _stub_response(content=b"file-bytes")
            result = get_tool_fn(model_files)(
                action="download", model_id=1, file_id=42, save_path=str(save_path)
            )

        assert result["success"] is True
        assert save_path.read_bytes() == b"file-bytes"
        req.get.assert_called_once()
        call = req.get.call_args
        assert call.args[0] == "https://test.snipeit.com/api/v1/models/1/files/42"
        assert call.kwargs["headers"]["Authorization"] == "Bearer test-token-12345"


class TestLicenseFilesTransfer:
    def test_upload_invokes_requests_with_bearer_token(self, mock_direct_api, tmp_path):
        from snipeit_mcp import license_files

        mock_direct_api.base_url = "https://test.snipeit.com"
        upload_path = tmp_path / "license.pdf"
        upload_path.write_bytes(b"license-bytes")

        with patch("snipeit_mcp.tools.licenses.requests") as req:
            req.post.return_value = _stub_response(json_payload={"id": 3})
            result = get_tool_fn(license_files)(
                action="upload", license_id=5, file_path=str(upload_path)
            )

        assert result["success"] is True
        req.post.assert_called_once()
        call = req.post.call_args
        assert call.args[0] == "https://test.snipeit.com/api/v1/licenses/5/upload"
        assert call.kwargs["headers"]["Authorization"] == "Bearer test-token-12345"

    def test_download_invokes_requests_with_bearer_token(self, mock_direct_api, tmp_path):
        from snipeit_mcp import license_files

        mock_direct_api.base_url = "https://test.snipeit.com"
        save_path = tmp_path / "license.pdf"

        with patch("snipeit_mcp.tools.licenses.requests") as req:
            req.get.return_value = _stub_response(content=b"file-bytes")
            result = get_tool_fn(license_files)(
                action="download", license_id=5, file_id=9, save_path=str(save_path)
            )

        assert result["success"] is True
        assert save_path.read_bytes() == b"file-bytes"
        req.get.assert_called_once()
        call = req.get.call_args
        assert call.args[0] == "https://test.snipeit.com/api/v1/licenses/5/uploads/9"
        assert call.kwargs["headers"]["Authorization"] == "Bearer test-token-12345"


class TestManageImportsUpload:
    def test_upload_invokes_requests_with_bearer_token(self, mock_direct_api, tmp_path):
        from snipeit_mcp import manage_imports

        mock_direct_api.base_url = "https://test.snipeit.com"
        upload_path = tmp_path / "assets.csv"
        upload_path.write_text("asset_tag,name\nA1,Laptop\n")

        with patch("snipeit_mcp.tools.imports.requests") as req:
            req.post.return_value = _stub_response(json_payload={"id": 12})
            result = get_tool_fn(manage_imports)(
                action="upload", file_path=str(upload_path)
            )

        assert result["success"] is True
        req.post.assert_called_once()
        call = req.post.call_args
        assert call.args[0] == "https://test.snipeit.com/api/v1/imports"
        assert call.kwargs["headers"]["Authorization"] == "Bearer test-token-12345"


class TestManageBackupsDownload:
    def test_download_invokes_requests_with_bearer_token(self, mock_direct_api, tmp_path):
        from snipeit_mcp import manage_backups

        mock_direct_api.base_url = "https://test.snipeit.com"
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
