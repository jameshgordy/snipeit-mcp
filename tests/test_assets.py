"""Tests for asset tools: manage_assets, asset_operations, asset_files, asset_labels, asset_maintenance, asset_licenses, asset_requests."""

from unittest.mock import MagicMock, call, patch

import pytest

def get_tool_fn(tool):
    return tool.fn if hasattr(tool, "fn") else tool

class TestManageAssets:
    def test_manage_assets_schema_marks_object_inputs_as_objects(self):
        import snipeit_mcp as server

        params = server.mcp._tool_manager._tools["manage_assets"].parameters["properties"]

        asset_data_schema = params["asset_data"]
        extra_fields_schema = params["extra_fields"]

        assert asset_data_schema["type"] == "object"
        assert asset_data_schema["additionalProperties"] is True
        assert any(branch.get("$ref") == "#/$defs/AssetData" for branch in asset_data_schema["anyOf"])

        assert extra_fields_schema["type"] == "object"
        assert extra_fields_schema["additionalProperties"] is True
        assert any(branch.get("type") == "object" for branch in extra_fields_schema["anyOf"])

    def test_create(self, mock_client, mock_direct_api):
        from snipeit_mcp import manage_assets, AssetData
        mock_direct_api._request.return_value = {"status": "success", "payload": {"id": 1, "asset_tag": "LAP-001", "name": "Test Laptop"}}
        result = get_tool_fn(manage_assets)(action="create", asset_data=AssetData(status_id=1, model_id=5, name="Test Laptop"))
        assert result["success"] is True
        assert result["action"] == "create"
        mock_direct_api._request.assert_called_once_with("POST", "hardware", json={"status_id": 1, "model_id": 5, "name": "Test Laptop"})

    def test_create_missing_data(self, mock_client):
        from snipeit_mcp import manage_assets
        result = get_tool_fn(manage_assets)(action="create")
        assert result["success"] is False

    def test_create_missing_required_fields(self, mock_client):
        from snipeit_mcp import manage_assets, AssetData
        result = get_tool_fn(manage_assets)(action="create", asset_data=AssetData())
        assert result["success"] is False

    def test_get_by_id(self, mock_client, mock_direct_api):
        from snipeit_mcp import manage_assets
        mock_direct_api._request.return_value = {"id": 1, "name": "Test Asset"}
        result = get_tool_fn(manage_assets)(action="get", asset_id=1)
        assert result["success"] is True
        assert result["action"] == "get"
        mock_direct_api._request.assert_called_with("GET", "hardware/1")

    def test_get_by_tag(self, mock_direct_api, mock_client):
        from snipeit_mcp import manage_assets
        mock_direct_api._request.return_value = {"id": 1, "asset_tag": "LAP-001"}
        result = get_tool_fn(manage_assets)(action="get", asset_tag="LAP-001")
        assert result["success"] is True
        mock_direct_api._request.assert_called_with("GET", "hardware/bytag/LAP-001")

    def test_get_by_serial(self, mock_direct_api, mock_client):
        from snipeit_mcp import manage_assets
        mock_direct_api._request.return_value = {"rows": [{"id": 1, "serial": "ABC"}], "total": 1}
        result = get_tool_fn(manage_assets)(action="get", serial="ABC")
        assert result["success"] is True
        mock_direct_api._request.assert_called_with("GET", "hardware/byserial/ABC")

    def test_get_missing_id(self):
        from snipeit_mcp import manage_assets
        result = get_tool_fn(manage_assets)(action="get")
        assert result["success"] is False
        assert "required" in result["error"].lower()

    def test_list(self, mock_client, mock_direct_api):
        from snipeit_mcp import manage_assets
        mock_direct_api._request.return_value = {"rows": [], "total": 0}
        result = get_tool_fn(manage_assets)(action="list")
        assert result["success"] is True
        assert result["action"] == "list"

    def test_list_default_sort(self, mock_client, mock_direct_api):
        """list() without explicit sort should default to sort=id, order=asc for stable pagination."""
        from snipeit_mcp import manage_assets
        mock_direct_api._request.return_value = {"rows": [], "total": 0}
        result = get_tool_fn(manage_assets)(action="list")
        assert result["success"] is True
        call_params = mock_direct_api._request.call_args[1]["params"]
        assert call_params["sort"] == "id", "Default sort should be 'id' for stable pagination"
        assert call_params["order"] == "asc", "Default order should be 'asc' for stable pagination"

    def test_list_with_filters(self, mock_client, mock_direct_api):
        from snipeit_mcp import manage_assets
        mock_direct_api._request.return_value = {"rows": [], "total": 0}
        result = get_tool_fn(manage_assets)(action="list", status_id=1, model_id=5, location_id=10)
        assert result["success"] is True
        call_params = mock_direct_api._request.call_args[1]["params"]
        assert call_params.get("status_id") == 1
        assert call_params.get("model_id") == 5

    def test_list_with_sort(self, mock_client, mock_direct_api):
        from snipeit_mcp import manage_assets
        mock_direct_api._request.return_value = {"rows": [], "total": 0}
        result = get_tool_fn(manage_assets)(action="list", sort="name", order="asc")
        assert result["success"] is True

    def test_update(self, mock_client, mock_direct_api):
        from snipeit_mcp import manage_assets, AssetData
        mock_direct_api._request.return_value = {"status": "success", "payload": {"id": 1, "name": "Updated"}}
        result = get_tool_fn(manage_assets)(action="update", asset_id=1, asset_data=AssetData(name="Updated"))
        assert result["success"] is True
        assert result["action"] == "update"

    @pytest.mark.asyncio
    async def test_tool_run_accepts_dict_asset_data(self, mock_client, mock_direct_api):
        import snipeit_mcp as server

        tool = server.mcp._tool_manager._tools["manage_assets"]
        mock_direct_api._request.return_value = {"status": "success", "payload": {"id": 1, "name": "Test Laptop"}}

        result = await tool.run({
            "action": "create",
            "asset_data": {"status_id": 1, "model_id": 5, "name": "Test Laptop"},
        })

        assert result.structured_content["success"] is True
        assert result.structured_content["action"] == "create"
        mock_direct_api._request.assert_called_once_with(
            "POST",
            "hardware",
            json={"status_id": 1, "model_id": 5, "name": "Test Laptop"},
        )

    @pytest.mark.asyncio
    async def test_tool_run_accepts_dict_extra_fields(self, mock_client, mock_direct_api):
        import snipeit_mcp as server

        tool = server.mcp._tool_manager._tools["manage_assets"]
        mock_direct_api._request.side_effect = [
            {"id": 1, "custom_fields": {"Hostname": {"field": "_snipeit_hostname_2"}}},
            {"status": "success", "payload": {"id": 1, "name": "Updated"}},
        ]

        result = await tool.run({
            "action": "update",
            "asset_id": 1,
            "extra_fields": {"_snipeit_hostname_2": "FL142"},
        })

        assert result.structured_content["success"] is True
        assert result.structured_content["action"] == "update"
        assert mock_direct_api._request.call_args_list == [
            call("GET", "hardware/1"),
            call("PATCH", "hardware/1", json={"_snipeit_hostname_2": "FL142"}),
        ]

    def test_update_missing_id(self, mock_client):
        from snipeit_mcp import manage_assets, AssetData
        result = get_tool_fn(manage_assets)(action="update", asset_data=AssetData(name="X"))
        assert result["success"] is False

    def test_delete(self, mock_client):
        from snipeit_mcp import manage_assets
        result = get_tool_fn(manage_assets)(action="delete", asset_id=1)
        assert result["success"] is True
        assert result["action"] == "delete"

    def test_delete_missing_id(self, mock_client):
        from snipeit_mcp import manage_assets
        result = get_tool_fn(manage_assets)(action="delete")
        assert result["success"] is False

class TestAssetOperations:
    def test_checkout(self, mock_client):
        from snipeit_mcp import asset_operations, CheckoutData
        asset = MagicMock()
        asset.id = 1
        mock_client.assets.get.return_value = asset
        updated = MagicMock()
        updated.id = 1
        asset.checkout.return_value = updated
        result = get_tool_fn(asset_operations)(
            action="checkout", asset_id=1,
            checkout_data=CheckoutData(checkout_to_type="user", assigned_to_id=10)
        )
        assert result["success"] is True
        assert result["action"] == "checkout"

    def test_checkout_missing_data(self, mock_client):
        from snipeit_mcp import asset_operations
        asset = MagicMock()
        mock_client.assets.get.return_value = asset
        result = get_tool_fn(asset_operations)(action="checkout", asset_id=1)
        assert result["success"] is False

    def test_checkin(self, mock_client):
        from snipeit_mcp import asset_operations
        asset = MagicMock()
        asset.id = 1
        mock_client.assets.get.return_value = asset
        updated = MagicMock()
        updated.id = 1
        asset.checkin.return_value = updated
        result = get_tool_fn(asset_operations)(action="checkin", asset_id=1)
        assert result["success"] is True
        assert result["action"] == "checkin"

    def test_audit(self, mock_client):
        from snipeit_mcp import asset_operations, AuditData
        asset = MagicMock()
        asset.id = 1
        mock_client.assets.get.return_value = asset
        updated = MagicMock()
        updated.id = 1
        asset.audit.return_value = updated
        result = get_tool_fn(asset_operations)(
            action="audit", asset_id=1,
            audit_data=AuditData(note="Audited")
        )
        assert result["success"] is True
        assert result["action"] == "audit"

    def test_restore(self, mock_client):
        from snipeit_mcp import asset_operations
        asset = MagicMock()
        asset.id = 1
        mock_client.assets.get.return_value = asset
        updated = MagicMock()
        updated.id = 1
        asset.restore.return_value = updated
        result = get_tool_fn(asset_operations)(action="restore", asset_id=1)
        assert result["success"] is True
        assert result["action"] == "restore"

class TestAssetFiles:
    def test_upload(self, mock_client):
        from snipeit_mcp import asset_files
        mock_client.assets.upload_files.return_value = {"status": "success"}
        result = get_tool_fn(asset_files)(action="upload", asset_id=1, file_paths=["/tmp/test.pdf"])
        assert result["success"] is True
        assert result["action"] == "upload"

    def test_upload_missing_paths(self, mock_client):
        from snipeit_mcp import asset_files
        result = get_tool_fn(asset_files)(action="upload", asset_id=1)
        assert result["success"] is False

    def test_list(self, mock_client):
        from snipeit_mcp import asset_files
        mock_client.assets.list_files.return_value = []
        result = get_tool_fn(asset_files)(action="list", asset_id=1)
        assert result["success"] is True

    def test_download(self, mock_client):
        from snipeit_mcp import asset_files
        mock_client.assets.download_file.return_value = "/tmp/file.pdf"
        result = get_tool_fn(asset_files)(action="download", asset_id=1, file_id=5, save_path="/tmp/file.pdf")
        assert result["success"] is True

    def test_download_missing_file_id(self, mock_client):
        from snipeit_mcp import asset_files
        result = get_tool_fn(asset_files)(action="download", asset_id=1)
        assert result["success"] is False

    def test_delete(self, mock_client):
        from snipeit_mcp import asset_files
        result = get_tool_fn(asset_files)(action="delete", asset_id=1, file_id=5)
        assert result["success"] is True

    def test_delete_missing_file_id(self, mock_client):
        from snipeit_mcp import asset_files
        result = get_tool_fn(asset_files)(action="delete", asset_id=1)
        assert result["success"] is False

class TestAssetLabels:
    def test_by_ids(self, mock_client):
        from snipeit_mcp import asset_labels
        mock_client.assets.generate_labels.return_value = "/tmp/labels.pdf"
        result = get_tool_fn(asset_labels)(asset_ids=[1, 2, 3])
        assert result["success"] is True

    def test_by_tags(self, mock_client):
        from snipeit_mcp import asset_labels
        mock_client.assets.generate_labels.return_value = "/tmp/labels.pdf"
        result = get_tool_fn(asset_labels)(asset_tags=["LAP-001", "LAP-002"])
        assert result["success"] is True

    def test_missing_both(self, mock_client):
        from snipeit_mcp import asset_labels
        result = get_tool_fn(asset_labels)()
        assert result["success"] is False

class TestAssetMaintenance:
    def test_create(self, mock_client):
        from snipeit_mcp import asset_maintenance, MaintenanceData
        mock_client.assets.create_maintenance.return_value = {"id": 1}
        result = get_tool_fn(asset_maintenance)(
            action="create", asset_id=1,
            maintenance_data=MaintenanceData(asset_improvement="Upgrade", supplier_id=1, title="RAM")
        )
        assert result["success"] is True

    def test_create_with_optional_fields(self, mock_client):
        from snipeit_mcp import asset_maintenance, MaintenanceData
        mock_client.assets.create_maintenance.return_value = {"id": 2}
        result = get_tool_fn(asset_maintenance)(
            action="create", asset_id=1,
            maintenance_data=MaintenanceData(asset_improvement="Repair", supplier_id=2, title="Screen fix", cost=150.0)
        )
        assert result["success"] is True

class TestAssetLicenses:
    def test_list(self, mock_client):
        from snipeit_mcp import asset_licenses
        mock_client.assets.get_licenses.return_value = []
        result = get_tool_fn(asset_licenses)(asset_id=1)
        assert result["success"] is True
        assert result["asset_id"] == 1

class TestAssetRequests:
    def test_request(self, mock_direct_api):
        from snipeit_mcp import asset_requests
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(asset_requests)(action="request", asset_id=123)
        assert result["success"] is True
        assert result["action"] == "request"
        mock_direct_api._request.assert_called_with("POST", "hardware/123/request", json=None)

    def test_request_with_data(self, mock_direct_api):
        from snipeit_mcp import asset_requests, AssetRequestData
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(asset_requests)(
            action="request", asset_id=123,
            request_data=AssetRequestData(note="Need it")
        )
        assert result["success"] is True

    def test_cancel(self, mock_direct_api):
        from snipeit_mcp import asset_requests
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(asset_requests)(action="cancel", asset_id=123)
        assert result["success"] is True
        assert result["action"] == "cancel"
