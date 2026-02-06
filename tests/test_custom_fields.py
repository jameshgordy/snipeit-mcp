"""Tests for custom field tools: manage_fields, manage_fieldsets."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_tool_fn(tool):
    return tool.fn if hasattr(tool, "fn") else tool


class TestManageFields:
    def test_create(self, mock_direct_api):
        from server import manage_fields, FieldData
        mock_direct_api.create.return_value = {"id": 1, "name": "MAC"}
        result = get_tool_fn(manage_fields)(action="create", field_data=FieldData(name="MAC", element="text"))
        assert result["success"] is True

    def test_create_missing_data(self, mock_direct_api):
        from server import manage_fields
        result = get_tool_fn(manage_fields)(action="create")
        assert result["success"] is False

    def test_create_missing_required(self, mock_direct_api):
        from server import manage_fields, FieldData
        result = get_tool_fn(manage_fields)(action="create", field_data=FieldData())
        assert result["success"] is False

    def test_get(self, mock_direct_api):
        from server import manage_fields
        mock_direct_api.get.return_value = {"id": 1, "name": "MAC"}
        result = get_tool_fn(manage_fields)(action="get", field_id=1)
        assert result["success"] is True

    def test_get_missing_id(self, mock_direct_api):
        from server import manage_fields
        result = get_tool_fn(manage_fields)(action="get")
        assert result["success"] is False

    def test_list(self, mock_direct_api):
        from server import manage_fields
        mock_direct_api.list.return_value = []
        result = get_tool_fn(manage_fields)(action="list")
        assert result["success"] is True

    def test_update(self, mock_direct_api):
        from server import manage_fields, FieldData
        mock_direct_api.update.return_value = {"id": 1}
        result = get_tool_fn(manage_fields)(action="update", field_id=1, field_data=FieldData(name="Updated"))
        assert result["success"] is True

    def test_delete(self, mock_direct_api):
        from server import manage_fields
        mock_direct_api.delete.return_value = {}
        result = get_tool_fn(manage_fields)(action="delete", field_id=1)
        assert result["success"] is True

    def test_associate(self, mock_direct_api):
        from server import manage_fields
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(manage_fields)(action="associate", field_id=1, fieldset_id=2)
        assert result["success"] is True
        assert result["action"] == "associate"

    def test_associate_missing_ids(self, mock_direct_api):
        from server import manage_fields
        result = get_tool_fn(manage_fields)(action="associate", field_id=1)
        assert result["success"] is False

    def test_disassociate(self, mock_direct_api):
        from server import manage_fields
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(manage_fields)(action="disassociate", field_id=1, fieldset_id=2)
        assert result["success"] is True
        assert result["action"] == "disassociate"

    def test_disassociate_missing_ids(self, mock_direct_api):
        from server import manage_fields
        result = get_tool_fn(manage_fields)(action="disassociate")
        assert result["success"] is False


class TestManageFieldsets:
    def test_create(self, mock_direct_api):
        from server import manage_fieldsets, FieldsetData
        mock_direct_api.create.return_value = {"id": 1, "name": "Hardware"}
        result = get_tool_fn(manage_fieldsets)(action="create", fieldset_data=FieldsetData(name="Hardware"))
        assert result["success"] is True

    def test_create_missing_name(self, mock_direct_api):
        from server import manage_fieldsets, FieldsetData
        result = get_tool_fn(manage_fieldsets)(action="create", fieldset_data=FieldsetData())
        assert result["success"] is False

    def test_get(self, mock_direct_api):
        from server import manage_fieldsets
        mock_direct_api.get.return_value = {"id": 1, "name": "Hardware"}
        result = get_tool_fn(manage_fieldsets)(action="get", fieldset_id=1)
        assert result["success"] is True

    def test_get_missing_id(self, mock_direct_api):
        from server import manage_fieldsets
        result = get_tool_fn(manage_fieldsets)(action="get")
        assert result["success"] is False

    def test_list(self, mock_direct_api):
        from server import manage_fieldsets
        mock_direct_api.list.return_value = []
        result = get_tool_fn(manage_fieldsets)(action="list")
        assert result["success"] is True

    def test_update(self, mock_direct_api):
        from server import manage_fieldsets, FieldsetData
        mock_direct_api.update.return_value = {"id": 1}
        result = get_tool_fn(manage_fieldsets)(action="update", fieldset_id=1, fieldset_data=FieldsetData(name="Updated"))
        assert result["success"] is True

    def test_delete(self, mock_direct_api):
        from server import manage_fieldsets
        mock_direct_api.delete.return_value = {}
        result = get_tool_fn(manage_fieldsets)(action="delete", fieldset_id=1)
        assert result["success"] is True

    def test_fields(self, mock_direct_api):
        from server import manage_fieldsets
        mock_direct_api._request.return_value = {"rows": [{"id": 1, "name": "MAC"}]}
        result = get_tool_fn(manage_fieldsets)(action="fields", fieldset_id=1)
        assert result["success"] is True
        assert result["action"] == "fields"

    def test_fields_missing_id(self, mock_direct_api):
        from server import manage_fieldsets
        result = get_tool_fn(manage_fieldsets)(action="fields")
        assert result["success"] is False

    def test_reorder(self, mock_direct_api):
        from server import manage_fieldsets
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(manage_fieldsets)(action="reorder", fieldset_id=1, field_order=[5, 3, 1])
        assert result["success"] is True
        mock_direct_api._request.assert_called_with("POST", "fields/fieldsets/1/order", json={"item": [5, 3, 1]})

    def test_reorder_missing_order(self, mock_direct_api):
        from server import manage_fieldsets
        result = get_tool_fn(manage_fieldsets)(action="reorder", fieldset_id=1)
        assert result["success"] is False
