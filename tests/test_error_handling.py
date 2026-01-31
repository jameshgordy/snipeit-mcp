"""Tests for cross-cutting error handling scenarios."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_tool_fn(tool):
    return tool.fn if hasattr(tool, "fn") else tool


class TestDirectApiErrors:
    def test_not_found(self, mock_direct_api):
        from server import audit_tracking, SnipeITNotFoundError
        mock_direct_api._request.side_effect = SnipeITNotFoundError("Resource not found")
        result = get_tool_fn(audit_tracking)(action="due")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_authentication_error(self, mock_direct_api):
        from server import system_info, SnipeITAuthenticationError
        mock_direct_api._request.side_effect = SnipeITAuthenticationError("Invalid token")
        result = get_tool_fn(system_info)()
        assert result["success"] is False
        assert "authentication" in result["error"].lower()

    def test_validation_error(self, mock_direct_api):
        from server import manage_status_labels, StatusLabelData, SnipeITValidationError
        mock_direct_api.create.side_effect = SnipeITValidationError("Name taken")
        result = get_tool_fn(manage_status_labels)(
            action="create",
            status_label_data=StatusLabelData(name="Deployed", type="deployable")
        )
        assert result["success"] is False
        assert "validation" in result["error"].lower()

    def test_snipeit_exception(self, mock_direct_api):
        from server import status_summary, SnipeITException
        mock_direct_api._request.side_effect = SnipeITException("Connection failed")
        result = get_tool_fn(status_summary)()
        assert result["success"] is False

    def test_generic_exception(self, mock_direct_api):
        from server import status_summary
        mock_direct_api._request.side_effect = RuntimeError("Unexpected")
        result = get_tool_fn(status_summary)()
        assert result["success"] is False
        assert "unexpected" in result["error"].lower()

    def test_manage_users_not_found(self, mock_direct_api):
        from server import manage_users, SnipeITNotFoundError
        mock_direct_api.get.side_effect = SnipeITNotFoundError("User not found")
        result = get_tool_fn(manage_users)(action="get", user_id=999)
        assert result["success"] is False


class TestClientErrors:
    def test_not_found(self, mock_client):
        from server import manage_assets, SnipeITNotFoundError
        mock_client.assets.get.side_effect = SnipeITNotFoundError("Asset not found")
        result = get_tool_fn(manage_assets)(action="get", asset_id=999)
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_authentication_error(self, mock_client):
        from server import manage_assets, SnipeITAuthenticationError
        mock_client.assets.list.side_effect = SnipeITAuthenticationError("Bad token")
        result = get_tool_fn(manage_assets)(action="list")
        assert result["success"] is False
        assert "authentication" in result["error"].lower()

    def test_validation_error(self, mock_client):
        from server import manage_categories, CategoryData, SnipeITValidationError
        mock_client.categories.create.side_effect = SnipeITValidationError("Invalid data")
        result = get_tool_fn(manage_categories)(
            action="create",
            category_data=CategoryData(name="Test", category_type="asset")
        )
        assert result["success"] is False
        assert "validation" in result["error"].lower()

    def test_snipeit_exception(self, mock_client):
        from server import manage_consumables, SnipeITException
        mock_client.consumables.list.side_effect = SnipeITException("Connection error")
        result = get_tool_fn(manage_consumables)(action="list")
        assert result["success"] is False

    def test_generic_exception(self, mock_client):
        from server import manage_assets
        mock_client.assets.list.side_effect = RuntimeError("Boom")
        result = get_tool_fn(manage_assets)(action="list")
        assert result["success"] is False
        assert "unexpected" in result["error"].lower()

    def test_asset_operations_not_found(self, mock_client):
        from server import asset_operations, SnipeITNotFoundError
        mock_client.assets.get.side_effect = SnipeITNotFoundError("Asset 999 not found")
        result = get_tool_fn(asset_operations)(action="checkin", asset_id=999)
        assert result["success"] is False
