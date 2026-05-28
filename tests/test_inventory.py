"""Tests for inventory tools: manage_consumables, manage_components, component_operations, manage_accessories, accessory_operations."""

from unittest.mock import MagicMock

def get_tool_fn(tool):
    return tool.fn if hasattr(tool, "fn") else tool

class TestManageConsumables:
    def test_create(self, mock_client):
        from snipeit_mcp import manage_consumables, ConsumableData
        c = MagicMock(); c.id = 1; c.name = "Toner"; c.qty = 100
        mock_client.consumables.create.return_value = c
        result = get_tool_fn(manage_consumables)(action="create", consumable_data=ConsumableData(name="Toner", qty=100, category_id=2))
        assert result["success"] is True
        assert result["action"] == "create"

    def test_create_missing_data(self, mock_client):
        from snipeit_mcp import manage_consumables
        result = get_tool_fn(manage_consumables)(action="create")
        assert result["success"] is False

    def test_create_missing_required(self, mock_client):
        from snipeit_mcp import manage_consumables, ConsumableData
        result = get_tool_fn(manage_consumables)(action="create", consumable_data=ConsumableData())
        assert result["success"] is False

    def test_get(self, mock_client):
        from snipeit_mcp import manage_consumables
        c = MagicMock(); c.id = 1
        mock_client.consumables.get.return_value = c
        result = get_tool_fn(manage_consumables)(action="get", consumable_id=1)
        assert result["success"] is True

    def test_get_missing_id(self, mock_client):
        from snipeit_mcp import manage_consumables
        result = get_tool_fn(manage_consumables)(action="get")
        assert result["success"] is False

    def test_list(self, mock_client, mock_direct_api):
        from snipeit_mcp import manage_consumables
        mock_direct_api.list_page.return_value = ([], 0)
        result = get_tool_fn(manage_consumables)(action="list")
        assert result["success"] is True
        assert result["count"] == 0

    def test_update(self, mock_client):
        from snipeit_mcp import manage_consumables, ConsumableData
        c = MagicMock(); c.id = 1
        mock_client.consumables.patch.return_value = c
        result = get_tool_fn(manage_consumables)(action="update", consumable_id=1, consumable_data=ConsumableData(name="Updated"))
        assert result["success"] is True

    def test_update_missing_id(self, mock_client):
        from snipeit_mcp import manage_consumables, ConsumableData
        result = get_tool_fn(manage_consumables)(action="update", consumable_data=ConsumableData(name="X"))
        assert result["success"] is False

    def test_delete(self, mock_client):
        from snipeit_mcp import manage_consumables
        result = get_tool_fn(manage_consumables)(action="delete", consumable_id=1)
        assert result["success"] is True

    def test_delete_missing_id(self, mock_client):
        from snipeit_mcp import manage_consumables
        result = get_tool_fn(manage_consumables)(action="delete")
        assert result["success"] is False

class TestManageComponents:
    def test_create(self, mock_direct_api):
        from snipeit_mcp import manage_components, ComponentData
        mock_direct_api.create.return_value = {"id": 1, "name": "RAM"}
        result = get_tool_fn(manage_components)(action="create", component_data=ComponentData(name="RAM", qty=10, category_id=5))
        assert result["success"] is True

    def test_create_missing_data(self, mock_direct_api):
        from snipeit_mcp import manage_components
        result = get_tool_fn(manage_components)(action="create")
        assert result["success"] is False

    def test_get(self, mock_direct_api):
        from snipeit_mcp import manage_components
        mock_direct_api.get.return_value = {"id": 1, "name": "RAM"}
        result = get_tool_fn(manage_components)(action="get", component_id=1)
        assert result["success"] is True

    def test_get_missing_id(self, mock_direct_api):
        from snipeit_mcp import manage_components
        result = get_tool_fn(manage_components)(action="get")
        assert result["success"] is False

    def test_list(self, mock_direct_api):
        from snipeit_mcp import manage_components
        mock_direct_api.list_page.return_value = ([], 0)
        result = get_tool_fn(manage_components)(action="list")
        assert result["success"] is True

    def test_update(self, mock_direct_api):
        from snipeit_mcp import manage_components, ComponentData
        mock_direct_api.update.return_value = {"id": 1}
        result = get_tool_fn(manage_components)(action="update", component_id=1, component_data=ComponentData(name="Updated"))
        assert result["success"] is True

    def test_delete(self, mock_direct_api):
        from snipeit_mcp import manage_components
        mock_direct_api.delete.return_value = {}
        result = get_tool_fn(manage_components)(action="delete", component_id=1)
        assert result["success"] is True

class TestComponentOperations:
    def test_checkout(self, mock_direct_api):
        from snipeit_mcp import component_operations, ComponentCheckout
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(component_operations)(
            action="checkout", component_id=1,
            checkout_data=ComponentCheckout(assigned_to=10)
        )
        assert result["success"] is True
        assert result["action"] == "checkout"

    def test_checkout_missing_data(self, mock_direct_api):
        from snipeit_mcp import component_operations
        result = get_tool_fn(component_operations)(action="checkout", component_id=1)
        assert result["success"] is False

    def test_checkin(self, mock_direct_api):
        from snipeit_mcp import component_operations
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(component_operations)(action="checkin", component_id=1, checkout_id=5)
        assert result["success"] is True

    def test_checkin_missing_id(self, mock_direct_api):
        from snipeit_mcp import component_operations
        result = get_tool_fn(component_operations)(action="checkin", component_id=1)
        assert result["success"] is False

    def test_list_assets(self, mock_direct_api):
        from snipeit_mcp import component_operations
        mock_direct_api._request.return_value = {"rows": [], "total": 0}
        result = get_tool_fn(component_operations)(action="list_assets", component_id=1)
        assert result["success"] is True
        assert result["action"] == "list_assets"

class TestManageAccessories:
    def test_create(self, mock_direct_api):
        from snipeit_mcp import manage_accessories, AccessoryData
        mock_direct_api.create.return_value = {"payload": {"id": 1, "name": "Mouse", "qty": 50}}
        result = get_tool_fn(manage_accessories)(action="create", accessory_data=AccessoryData(name="Mouse", qty=50, category_id=3))
        assert result["success"] is True

    def test_create_missing_data(self, mock_direct_api):
        from snipeit_mcp import manage_accessories
        result = get_tool_fn(manage_accessories)(action="create")
        assert result["success"] is False

    def test_get(self, mock_direct_api):
        from snipeit_mcp import manage_accessories
        mock_direct_api.get.return_value = {"id": 1, "name": "Mouse"}
        result = get_tool_fn(manage_accessories)(action="get", accessory_id=1)
        assert result["success"] is True

    def test_get_missing_id(self, mock_direct_api):
        from snipeit_mcp import manage_accessories
        result = get_tool_fn(manage_accessories)(action="get")
        assert result["success"] is False

    def test_list(self, mock_direct_api):
        from snipeit_mcp import manage_accessories
        mock_direct_api.list_page.return_value = ([], 0)
        result = get_tool_fn(manage_accessories)(action="list")
        assert result["success"] is True

    def test_update(self, mock_direct_api):
        from snipeit_mcp import manage_accessories, AccessoryData
        mock_direct_api.update.return_value = {"payload": {"id": 1, "name": "Updated"}}
        result = get_tool_fn(manage_accessories)(action="update", accessory_id=1, accessory_data=AccessoryData(name="Updated"))
        assert result["success"] is True

    def test_delete(self, mock_direct_api):
        from snipeit_mcp import manage_accessories
        mock_direct_api.delete.return_value = {}
        result = get_tool_fn(manage_accessories)(action="delete", accessory_id=1)
        assert result["success"] is True

class TestAccessoryOperations:
    def test_checkout_to_user(self, mock_direct_api):
        from snipeit_mcp import accessory_operations, AccessoryCheckout
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(accessory_operations)(
            action="checkout", accessory_id=1,
            checkout_data=AccessoryCheckout(checkout_to_type="user", assigned_to_id=5)
        )
        assert result["success"] is True
        # Verify wire payload uses polymorphic field name (regression guard for the
        # bug where we were sending assigned_to and the API rejected it).
        _, kwargs = mock_direct_api._request.call_args
        assert kwargs["json"] == {"assigned_user": 5}

    def test_checkout_to_asset(self, mock_direct_api):
        from snipeit_mcp import accessory_operations, AccessoryCheckout
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(accessory_operations)(
            action="checkout", accessory_id=1,
            checkout_data=AccessoryCheckout(checkout_to_type="asset", assigned_to_id=42)
        )
        assert result["success"] is True
        _, kwargs = mock_direct_api._request.call_args
        assert kwargs["json"] == {"assigned_asset": 42}

    def test_checkout_to_location_with_qty_and_note(self, mock_direct_api):
        from snipeit_mcp import accessory_operations, AccessoryCheckout
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(accessory_operations)(
            action="checkout", accessory_id=1,
            checkout_data=AccessoryCheckout(
                checkout_to_type="location", assigned_to_id=7,
                checkout_qty=3, note="batch handout",
            )
        )
        assert result["success"] is True
        _, kwargs = mock_direct_api._request.call_args
        assert kwargs["json"] == {
            "assigned_location": 7,
            "checkout_qty": 3,
            "note": "batch handout",
        }

    def test_checkout_missing_data(self, mock_direct_api):
        from snipeit_mcp import accessory_operations
        result = get_tool_fn(accessory_operations)(action="checkout", accessory_id=1)
        assert result["success"] is False

    def test_checkin(self, mock_direct_api):
        from snipeit_mcp import accessory_operations
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(accessory_operations)(action="checkin", accessory_id=1, checkout_id=5)
        assert result["success"] is True

    def test_checkin_missing_id(self, mock_direct_api):
        from snipeit_mcp import accessory_operations
        result = get_tool_fn(accessory_operations)(action="checkin", accessory_id=1)
        assert result["success"] is False

    def test_list_checkouts(self, mock_direct_api):
        from snipeit_mcp import accessory_operations
        mock_direct_api._request.return_value = {"rows": [], "total": 0}
        result = get_tool_fn(accessory_operations)(action="list_checkouts", accessory_id=1)
        assert result["success"] is True
        assert result["action"] == "list_checkouts"
