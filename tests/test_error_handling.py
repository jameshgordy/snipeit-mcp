"""Tests for cross-cutting error handling scenarios."""

def get_tool_fn(tool):
    return tool.fn if hasattr(tool, "fn") else tool

class TestDirectApiErrors:
    def test_not_found(self, mock_direct_api):
        from snipeit_mcp import audit_tracking, SnipeITNotFoundError
        mock_direct_api._request.side_effect = SnipeITNotFoundError("Resource not found")
        result = get_tool_fn(audit_tracking)(action="due")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_authentication_error(self, mock_direct_api):
        from snipeit_mcp import system_info, SnipeITAuthenticationError
        mock_direct_api._request.side_effect = SnipeITAuthenticationError("Invalid token")
        result = get_tool_fn(system_info)()
        assert result["success"] is False
        assert "authentication" in result["error"].lower()

    def test_validation_error(self, mock_direct_api):
        from snipeit_mcp import manage_status_labels, StatusLabelData, SnipeITValidationError
        mock_direct_api.create.side_effect = SnipeITValidationError("Name taken")
        result = get_tool_fn(manage_status_labels)(
            action="create",
            status_label_data=StatusLabelData(name="Deployed", type="deployable")
        )
        assert result["success"] is False
        assert "validation" in result["error"].lower()

    def test_snipeit_exception(self, mock_direct_api):
        from snipeit_mcp import status_summary, SnipeITException
        mock_direct_api._request.side_effect = SnipeITException("Connection failed")
        result = get_tool_fn(status_summary)()
        assert result["success"] is False

    def test_generic_exception(self, mock_direct_api):
        from snipeit_mcp import status_summary
        mock_direct_api._request.side_effect = RuntimeError("Unexpected")
        result = get_tool_fn(status_summary)()
        assert result["success"] is False
        assert "unexpected" in result["error"].lower()

    def test_manage_users_not_found(self, mock_direct_api):
        from snipeit_mcp import manage_users, SnipeITNotFoundError
        mock_direct_api.get.side_effect = SnipeITNotFoundError("User not found")
        result = get_tool_fn(manage_users)(action="get", user_id=999)
        assert result["success"] is False

class TestClientErrors:
    def test_not_found(self, mock_client, mock_direct_api):
        from snipeit_mcp import manage_assets, SnipeITNotFoundError
        mock_direct_api._request.side_effect = SnipeITNotFoundError("Asset not found")
        result = get_tool_fn(manage_assets)(action="get", asset_id=999)
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_authentication_error(self, mock_client, mock_direct_api):
        from snipeit_mcp import manage_assets, SnipeITAuthenticationError
        mock_direct_api._request.side_effect = SnipeITAuthenticationError("Bad token")
        result = get_tool_fn(manage_assets)(action="list")
        assert result["success"] is False
        assert "authentication" in result["error"].lower()

    def test_validation_error(self, mock_client):
        from snipeit_mcp import manage_categories, CategoryData, SnipeITValidationError
        mock_client.categories.create.side_effect = SnipeITValidationError("Invalid data")
        result = get_tool_fn(manage_categories)(
            action="create",
            category_data=CategoryData(name="Test", category_type="asset")
        )
        assert result["success"] is False
        assert "validation" in result["error"].lower()

    def test_snipeit_exception(self, mock_client):
        from snipeit_mcp import manage_consumables, SnipeITException
        mock_client.consumables.list.side_effect = SnipeITException("Connection error")
        result = get_tool_fn(manage_consumables)(action="list")
        assert result["success"] is False

    def test_generic_exception(self, mock_client):
        from snipeit_mcp import manage_assets
        mock_client.assets.list.side_effect = RuntimeError("Boom")
        result = get_tool_fn(manage_assets)(action="list")
        assert result["success"] is False
        assert "unexpected" in result["error"].lower()

    def test_asset_operations_not_found(self, mock_client):
        from snipeit_mcp import asset_operations, SnipeITNotFoundError
        mock_client.assets.get.side_effect = SnipeITNotFoundError("Asset 999 not found")
        result = get_tool_fn(asset_operations)(action="checkin", asset_id=999)
        assert result["success"] is False


class TestDirectApiRequest:
    def test_error_status_payload_raises(self):
        # Snipe-IT returns HTTP 200 with {"status": "error"} for many
        # failures; _request must raise instead of returning it as success.
        from unittest.mock import MagicMock, patch

        import pytest

        from snipeit_mcp.client import SnipeITDirectAPI, SnipeITException

        api = SnipeITDirectAPI()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "status": "error", "messages": "Statuslabel not found", "payload": None
        }
        with patch("snipeit_mcp.client.requests.request", return_value=response):
            with pytest.raises(SnipeITException, match="Statuslabel not found"):
                api._request("GET", "statuslabels/assets")

    def test_success_status_payload_passes_through(self):
        from unittest.mock import MagicMock, patch

        from snipeit_mcp.client import SnipeITDirectAPI

        api = SnipeITDirectAPI()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"status": "success", "payload": {"id": 1}}
        with patch("snipeit_mcp.client.requests.request", return_value=response):
            result = api._request("POST", "hardware", json={})
        assert result == {"status": "success", "payload": {"id": 1}}
