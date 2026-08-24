"""Tests for predefined kit tools: manage_kits."""

def get_tool_fn(tool):
    return tool.fn if hasattr(tool, "fn") else tool


class TestManageKitsCrud:
    def test_create(self, mock_direct_api):
        from snipeit_mcp import manage_kits, KitData
        mock_direct_api.create.return_value = {"status": "success", "payload": {"id": 1, "name": "Dev laptop"}}
        result = get_tool_fn(manage_kits)(action="create", kit_data=KitData(name="Dev laptop"))
        assert result["success"] is True
        mock_direct_api.create.assert_called_with("kits", {"name": "Dev laptop"})

    def test_create_missing_data(self, mock_direct_api):
        from snipeit_mcp import manage_kits
        result = get_tool_fn(manage_kits)(action="create")
        assert result["success"] is False

    def test_create_missing_name(self, mock_direct_api):
        from snipeit_mcp import manage_kits, KitData
        result = get_tool_fn(manage_kits)(action="create", kit_data=KitData())
        assert result["success"] is False

    def test_get(self, mock_direct_api):
        from snipeit_mcp import manage_kits
        mock_direct_api.get.return_value = {"id": 1, "name": "Dev laptop"}
        result = get_tool_fn(manage_kits)(action="get", kit_id=1)
        assert result["success"] is True
        assert result["kit"]["name"] == "Dev laptop"
        mock_direct_api.get.assert_called_with("kits", 1)

    def test_get_missing_id(self, mock_direct_api):
        from snipeit_mcp import manage_kits
        result = get_tool_fn(manage_kits)(action="get")
        assert result["success"] is False

    def test_list(self, mock_direct_api):
        from snipeit_mcp import manage_kits
        mock_direct_api.list_page.return_value = ([{"id": 1}, {"id": 2}], 2)
        result = get_tool_fn(manage_kits)(action="list")
        assert result["success"] is True
        assert result["count"] == 2
        assert result["total"] == 2

    def test_update(self, mock_direct_api):
        from snipeit_mcp import manage_kits, KitData
        mock_direct_api.update.return_value = {"status": "success"}
        result = get_tool_fn(manage_kits)(action="update", kit_id=1, kit_data=KitData(name="New name"))
        assert result["success"] is True
        mock_direct_api.update.assert_called_with("kits", 1, {"name": "New name"})

    def test_delete(self, mock_direct_api):
        from snipeit_mcp import manage_kits
        result = get_tool_fn(manage_kits)(action="delete", kit_id=1)
        assert result["success"] is True
        mock_direct_api.delete.assert_called_with("kits", 1)

    def test_delete_missing_id(self, mock_direct_api):
        from snipeit_mcp import manage_kits
        result = get_tool_fn(manage_kits)(action="delete")
        assert result["success"] is False


class TestManageKitsItems:
    def test_list_items(self, mock_direct_api):
        from snipeit_mcp import manage_kits
        mock_direct_api._request.return_value = {"rows": [{"id": 10, "quantity": 2}], "total": 1}
        result = get_tool_fn(manage_kits)(action="list_items", kit_id=1, item_type="models")
        assert result["success"] is True
        assert result["count"] == 1
        mock_direct_api._request.assert_called_with("GET", "kits/1/models")

    def test_list_items_missing_type(self, mock_direct_api):
        from snipeit_mcp import manage_kits
        result = get_tool_fn(manage_kits)(action="list_items", kit_id=1)
        assert result["success"] is False

    def test_list_items_missing_kit_id(self, mock_direct_api):
        from snipeit_mcp import manage_kits
        result = get_tool_fn(manage_kits)(action="list_items", item_type="models")
        assert result["success"] is False

    def test_add_model(self, mock_direct_api):
        from snipeit_mcp import manage_kits
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(manage_kits)(
            action="add_item", kit_id=1, item_type="models", item_id=10, quantity=2)
        assert result["success"] is True
        # payload key is the singular item name, per PredefinedKitsController
        mock_direct_api._request.assert_called_with(
            "POST", "kits/1/models", json={"model": 10, "quantity": 2})

    def test_add_license(self, mock_direct_api):
        from snipeit_mcp import manage_kits
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(manage_kits)(
            action="add_item", kit_id=1, item_type="licenses", item_id=4)
        assert result["success"] is True
        mock_direct_api._request.assert_called_with(
            "POST", "kits/1/licenses", json={"license": 4, "quantity": 1})

    def test_add_accessory(self, mock_direct_api):
        from snipeit_mcp import manage_kits
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(manage_kits)(
            action="add_item", kit_id=1, item_type="accessories", item_id=7)
        assert result["success"] is True
        mock_direct_api._request.assert_called_with(
            "POST", "kits/1/accessories", json={"accessory": 7, "quantity": 1})

    def test_add_consumable(self, mock_direct_api):
        from snipeit_mcp import manage_kits
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(manage_kits)(
            action="add_item", kit_id=1, item_type="consumables", item_id=3)
        assert result["success"] is True
        mock_direct_api._request.assert_called_with(
            "POST", "kits/1/consumables", json={"consumable": 3, "quantity": 1})

    def test_add_item_missing_item_id(self, mock_direct_api):
        from snipeit_mcp import manage_kits
        result = get_tool_fn(manage_kits)(action="add_item", kit_id=1, item_type="models")
        assert result["success"] is False

    def test_update_item(self, mock_direct_api):
        from snipeit_mcp import manage_kits
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(manage_kits)(
            action="update_item", kit_id=1, item_type="models", item_id=10, quantity=5)
        assert result["success"] is True
        mock_direct_api._request.assert_called_with(
            "PUT", "kits/1/models/10", json={"quantity": 5})

    def test_remove_item(self, mock_direct_api):
        from snipeit_mcp import manage_kits
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(manage_kits)(
            action="remove_item", kit_id=1, item_type="accessories", item_id=7)
        assert result["success"] is True
        mock_direct_api._request.assert_called_with("DELETE", "kits/1/accessories/7")


class TestManageKitsErrors:
    def test_not_found(self, mock_direct_api):
        from snipeit_mcp import manage_kits, SnipeITNotFoundError
        mock_direct_api.get.side_effect = SnipeITNotFoundError("Kit not found")
        result = get_tool_fn(manage_kits)(action="get", kit_id=999)
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_api_error_payload(self, mock_direct_api):
        from snipeit_mcp import manage_kits, SnipeITException
        mock_direct_api._request.side_effect = SnipeITException("Kit item already attached")
        result = get_tool_fn(manage_kits)(
            action="add_item", kit_id=1, item_type="models", item_id=10)
        assert result["success"] is False
        assert "already attached" in result["error"]
