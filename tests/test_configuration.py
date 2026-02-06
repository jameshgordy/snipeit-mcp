"""Tests for configuration tools: manage_categories, manage_manufacturers, manage_models, manage_status_labels, manage_locations, manage_suppliers, manage_depreciations."""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_tool_fn(tool):
    return tool.fn if hasattr(tool, "fn") else tool


class TestManageCategories:
    def test_create(self, mock_client):
        from server import manage_categories, CategoryData
        cat = MagicMock(); cat.id = 1; cat.name = "Laptops"; cat.category_type = "asset"
        mock_client.categories.create.return_value = cat
        result = get_tool_fn(manage_categories)(action="create", category_data=CategoryData(name="Laptops", category_type="asset"))
        assert result["success"] is True

    def test_create_missing_data(self, mock_client):
        from server import manage_categories
        result = get_tool_fn(manage_categories)(action="create")
        assert result["success"] is False

    def test_get(self, mock_client):
        from server import manage_categories
        cat = MagicMock(); cat.id = 1
        mock_client.categories.get.return_value = cat
        result = get_tool_fn(manage_categories)(action="get", category_id=1)
        assert result["success"] is True

    def test_list(self, mock_client):
        from server import manage_categories
        mock_client.categories.list.return_value = []
        result = get_tool_fn(manage_categories)(action="list")
        assert result["success"] is True

    def test_delete(self, mock_client):
        from server import manage_categories
        result = get_tool_fn(manage_categories)(action="delete", category_id=1)
        assert result["success"] is True


class TestManageManufacturers:
    def test_create(self, mock_client):
        from server import manage_manufacturers, ManufacturerData
        mfr = MagicMock(); mfr.id = 1; mfr.name = "Dell"
        mock_client.manufacturers.create.return_value = mfr
        result = get_tool_fn(manage_manufacturers)(action="create", manufacturer_data=ManufacturerData(name="Dell"))
        assert result["success"] is True

    def test_create_missing_name(self, mock_client):
        from server import manage_manufacturers, ManufacturerData
        result = get_tool_fn(manage_manufacturers)(action="create", manufacturer_data=ManufacturerData())
        assert result["success"] is False

    def test_get(self, mock_client):
        from server import manage_manufacturers
        mfr = MagicMock(); mfr.id = 1
        mock_client.manufacturers.get.return_value = mfr
        result = get_tool_fn(manage_manufacturers)(action="get", manufacturer_id=1)
        assert result["success"] is True

    def test_list(self, mock_client):
        from server import manage_manufacturers
        mock_client.manufacturers.list.return_value = []
        result = get_tool_fn(manage_manufacturers)(action="list")
        assert result["success"] is True

    def test_delete(self, mock_client):
        from server import manage_manufacturers
        result = get_tool_fn(manage_manufacturers)(action="delete", manufacturer_id=1)
        assert result["success"] is True


class TestManageModels:
    def test_create(self, mock_client):
        from server import manage_models, AssetModelData
        model = MagicMock(); model.id = 1; model.name = "XPS 15"
        mock_client.models.create.return_value = model
        result = get_tool_fn(manage_models)(action="create", model_data=AssetModelData(name="XPS 15", category_id=1))
        assert result["success"] is True

    def test_create_missing_required(self, mock_client):
        from server import manage_models, AssetModelData
        result = get_tool_fn(manage_models)(action="create", model_data=AssetModelData())
        assert result["success"] is False

    def test_get(self, mock_client):
        from server import manage_models
        model = MagicMock(); model.id = 1
        mock_client.models.get.return_value = model
        result = get_tool_fn(manage_models)(action="get", model_id=1)
        assert result["success"] is True

    def test_list(self, mock_client):
        from server import manage_models
        mock_client.models.list.return_value = []
        result = get_tool_fn(manage_models)(action="list")
        assert result["success"] is True

    def test_update(self, mock_client):
        from server import manage_models, AssetModelData
        model = MagicMock(); model.id = 1
        mock_client.models.patch.return_value = model
        result = get_tool_fn(manage_models)(action="update", model_id=1, model_data=AssetModelData(name="Updated"))
        assert result["success"] is True

    def test_delete(self, mock_client):
        from server import manage_models
        result = get_tool_fn(manage_models)(action="delete", model_id=1)
        assert result["success"] is True

    def test_assets(self, mock_direct_api, mock_client):
        from server import manage_models
        mock_direct_api._request.return_value = {"rows": [{"id": 1}], "total": 1}
        result = get_tool_fn(manage_models)(action="assets", model_id=1)
        assert result["success"] is True
        assert result["action"] == "assets"


class TestManageStatusLabels:
    def test_create(self, mock_direct_api):
        from server import manage_status_labels, StatusLabelData
        mock_direct_api.create.return_value = {"payload": {"id": 1, "name": "Deployed", "type": "deployable"}}
        result = get_tool_fn(manage_status_labels)(action="create", status_label_data=StatusLabelData(name="Deployed", type="deployable"))
        assert result["success"] is True

    def test_create_missing_required(self, mock_direct_api):
        from server import manage_status_labels, StatusLabelData
        result = get_tool_fn(manage_status_labels)(action="create", status_label_data=StatusLabelData())
        assert result["success"] is False

    def test_get(self, mock_direct_api):
        from server import manage_status_labels
        mock_direct_api.get.return_value = {"id": 1, "name": "Deployed"}
        result = get_tool_fn(manage_status_labels)(action="get", status_label_id=1)
        assert result["success"] is True

    def test_list(self, mock_direct_api):
        from server import manage_status_labels
        mock_direct_api.list.return_value = []
        result = get_tool_fn(manage_status_labels)(action="list")
        assert result["success"] is True

    def test_update(self, mock_direct_api):
        from server import manage_status_labels, StatusLabelData
        mock_direct_api.update.return_value = {"payload": {"id": 1, "name": "Updated"}}
        result = get_tool_fn(manage_status_labels)(action="update", status_label_id=1, status_label_data=StatusLabelData(name="Updated"))
        assert result["success"] is True

    def test_delete(self, mock_direct_api):
        from server import manage_status_labels
        mock_direct_api.delete.return_value = {}
        result = get_tool_fn(manage_status_labels)(action="delete", status_label_id=1)
        assert result["success"] is True

    def test_assets(self, mock_direct_api):
        from server import manage_status_labels
        mock_direct_api._request.return_value = {"rows": [{"id": 1}], "total": 1}
        result = get_tool_fn(manage_status_labels)(action="assets", status_label_id=1)
        assert result["success"] is True
        assert result["action"] == "assets"


class TestManageLocations:
    def test_create(self, mock_client):
        from server import manage_locations, LocationData
        loc = MagicMock(); loc.id = 1; loc.name = "Office"
        mock_client.locations.create.return_value = loc
        result = get_tool_fn(manage_locations)(action="create", location_data=LocationData(name="Office"))
        assert result["success"] is True

    def test_create_missing_name(self, mock_client):
        from server import manage_locations, LocationData
        result = get_tool_fn(manage_locations)(action="create", location_data=LocationData())
        assert result["success"] is False

    def test_get(self, mock_client):
        from server import manage_locations
        loc = MagicMock(); loc.id = 1
        mock_client.locations.get.return_value = loc
        result = get_tool_fn(manage_locations)(action="get", location_id=1)
        assert result["success"] is True

    def test_list(self, mock_client):
        from server import manage_locations
        mock_client.locations.list.return_value = []
        result = get_tool_fn(manage_locations)(action="list")
        assert result["success"] is True

    def test_delete(self, mock_client):
        from server import manage_locations
        result = get_tool_fn(manage_locations)(action="delete", location_id=1)
        assert result["success"] is True

    def test_assets(self, mock_direct_api, mock_client):
        from server import manage_locations
        mock_direct_api._request.return_value = {"rows": [{"id": 1}], "total": 1}
        result = get_tool_fn(manage_locations)(action="assets", location_id=10)
        assert result["success"] is True
        assert result["action"] == "assets"

    def test_users(self, mock_direct_api, mock_client):
        from server import manage_locations
        mock_direct_api._request.return_value = {"rows": [{"id": 1}], "total": 1}
        result = get_tool_fn(manage_locations)(action="users", location_id=10)
        assert result["success"] is True
        assert result["action"] == "users"


class TestManageSuppliers:
    def test_create(self, mock_direct_api):
        from server import manage_suppliers, SupplierData
        mock_direct_api.create.return_value = {"payload": {"id": 1, "name": "Acme"}}
        result = get_tool_fn(manage_suppliers)(action="create", supplier_data=SupplierData(name="Acme"))
        assert result["success"] is True

    def test_create_missing_name(self, mock_direct_api):
        from server import manage_suppliers, SupplierData
        result = get_tool_fn(manage_suppliers)(action="create", supplier_data=SupplierData())
        assert result["success"] is False

    def test_get(self, mock_direct_api):
        from server import manage_suppliers
        mock_direct_api.get.return_value = {"id": 1, "name": "Acme"}
        result = get_tool_fn(manage_suppliers)(action="get", supplier_id=1)
        assert result["success"] is True

    def test_list(self, mock_direct_api):
        from server import manage_suppliers
        mock_direct_api.list.return_value = []
        result = get_tool_fn(manage_suppliers)(action="list")
        assert result["success"] is True

    def test_delete(self, mock_direct_api):
        from server import manage_suppliers
        mock_direct_api.delete.return_value = {}
        result = get_tool_fn(manage_suppliers)(action="delete", supplier_id=1)
        assert result["success"] is True


class TestManageDepreciations:
    def test_create(self, mock_direct_api):
        from server import manage_depreciations, DepreciationData
        mock_direct_api.create.return_value = {"payload": {"id": 1, "name": "3 Year"}}
        result = get_tool_fn(manage_depreciations)(action="create", depreciation_data=DepreciationData(name="3 Year", months=36))
        assert result["success"] is True

    def test_get(self, mock_direct_api):
        from server import manage_depreciations
        mock_direct_api.get.return_value = {"id": 1, "name": "3 Year"}
        result = get_tool_fn(manage_depreciations)(action="get", depreciation_id=1)
        assert result["success"] is True

    def test_list(self, mock_direct_api):
        from server import manage_depreciations
        mock_direct_api.list.return_value = []
        result = get_tool_fn(manage_depreciations)(action="list")
        assert result["success"] is True

    def test_update(self, mock_direct_api):
        from server import manage_depreciations, DepreciationData
        mock_direct_api.update.return_value = {"payload": {"id": 1}}
        result = get_tool_fn(manage_depreciations)(action="update", depreciation_id=1, depreciation_data=DepreciationData(name="Updated"))
        assert result["success"] is True

    def test_delete(self, mock_direct_api):
        from server import manage_depreciations
        mock_direct_api.delete.return_value = {}
        result = get_tool_fn(manage_depreciations)(action="delete", depreciation_id=1)
        assert result["success"] is True
