"""Tests for user and organization tools: manage_users, user_assets, user_two_factor, manage_companies, manage_departments, manage_groups."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_tool_fn(tool):
    return tool.fn if hasattr(tool, "fn") else tool


class TestManageUsers:
    def test_create(self, mock_direct_api):
        from server import manage_users, UserData
        mock_direct_api.create.return_value = {"payload": {"id": 1}}
        result = get_tool_fn(manage_users)(action="create", user_data=UserData(
            first_name="John", username="jdoe", password="pass123"
        ))
        assert result["success"] is True
        assert result["action"] == "create"

    def test_create_missing_data(self, mock_direct_api):
        from server import manage_users
        result = get_tool_fn(manage_users)(action="create")
        assert result["success"] is False

    def test_create_missing_required(self, mock_direct_api):
        from server import manage_users, UserData
        result = get_tool_fn(manage_users)(action="create", user_data=UserData())
        assert result["success"] is False

    def test_get(self, mock_direct_api):
        from server import manage_users
        mock_direct_api.get.return_value = {"id": 1, "username": "jdoe"}
        result = get_tool_fn(manage_users)(action="get", user_id=1)
        assert result["success"] is True

    def test_get_missing_id(self, mock_direct_api):
        from server import manage_users
        result = get_tool_fn(manage_users)(action="get")
        assert result["success"] is False

    def test_list(self, mock_direct_api):
        from server import manage_users
        mock_direct_api.list.return_value = []
        result = get_tool_fn(manage_users)(action="list")
        assert result["success"] is True

    def test_update(self, mock_direct_api):
        from server import manage_users, UserData
        mock_direct_api.update.return_value = {"id": 1}
        result = get_tool_fn(manage_users)(action="update", user_id=1, user_data=UserData(first_name="Jane"))
        assert result["success"] is True

    def test_update_missing_id(self, mock_direct_api):
        from server import manage_users, UserData
        result = get_tool_fn(manage_users)(action="update", user_data=UserData(first_name="X"))
        assert result["success"] is False

    def test_delete(self, mock_direct_api):
        from server import manage_users
        mock_direct_api.delete.return_value = {}
        result = get_tool_fn(manage_users)(action="delete", user_id=1)
        assert result["success"] is True

    def test_delete_missing_id(self, mock_direct_api):
        from server import manage_users
        result = get_tool_fn(manage_users)(action="delete")
        assert result["success"] is False

    def test_restore(self, mock_direct_api):
        from server import manage_users
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(manage_users)(action="restore", user_id=1)
        assert result["success"] is True

    def test_restore_missing_id(self, mock_direct_api):
        from server import manage_users
        result = get_tool_fn(manage_users)(action="restore")
        assert result["success"] is False

    def test_me(self, mock_direct_api):
        from server import manage_users
        mock_direct_api._request.return_value = {"id": 1, "username": "admin"}
        result = get_tool_fn(manage_users)(action="me")
        assert result["success"] is True
        assert result["action"] == "me"


class TestUserAssets:
    def test_all(self, mock_direct_api):
        from server import user_assets
        mock_direct_api._request.return_value = {"rows": []}
        result = get_tool_fn(user_assets)(user_id=1, asset_type="all")
        assert result["success"] is True
        assert "assets" in result

    def test_assets(self, mock_direct_api):
        from server import user_assets
        mock_direct_api._request.return_value = {"rows": [{"id": 1}]}
        result = get_tool_fn(user_assets)(user_id=1, asset_type="assets")
        assert result["success"] is True
        assert "assets" in result

    def test_accessories(self, mock_direct_api):
        from server import user_assets
        mock_direct_api._request.return_value = {"rows": []}
        result = get_tool_fn(user_assets)(user_id=1, asset_type="accessories")
        assert result["success"] is True
        assert "accessories" in result

    def test_licenses(self, mock_direct_api):
        from server import user_assets
        mock_direct_api._request.return_value = {"rows": []}
        result = get_tool_fn(user_assets)(user_id=1, asset_type="licenses")
        assert result["success"] is True
        assert "licenses" in result

    def test_consumables(self, mock_direct_api):
        from server import user_assets
        mock_direct_api._request.return_value = {"rows": []}
        result = get_tool_fn(user_assets)(user_id=1, asset_type="consumables")
        assert result["success"] is True
        assert "consumables" in result
        mock_direct_api._request.assert_called_with("GET", "users/1/consumables")

    def test_eulas(self, mock_direct_api):
        from server import user_assets
        mock_direct_api._request.return_value = {"rows": []}
        result = get_tool_fn(user_assets)(user_id=1, asset_type="eulas")
        assert result["success"] is True
        assert "eulas" in result
        mock_direct_api._request.assert_called_with("GET", "users/1/eulas")


class TestUserTwoFactor:
    def test_reset(self, mock_direct_api):
        from server import user_two_factor
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(user_two_factor)(action="reset", user_id=456)
        assert result["success"] is True
        assert result["user_id"] == 456
        mock_direct_api._request.assert_called_with("POST", "users/456/two_factor_reset")


class TestManageCompanies:
    def test_create(self, mock_direct_api):
        from server import manage_companies, CompanyData
        mock_direct_api.create.return_value = {"id": 1, "name": "Acme"}
        result = get_tool_fn(manage_companies)(action="create", company_data=CompanyData(name="Acme"))
        assert result["success"] is True

    def test_create_missing_name(self, mock_direct_api):
        from server import manage_companies, CompanyData
        result = get_tool_fn(manage_companies)(action="create", company_data=CompanyData())
        assert result["success"] is False

    def test_get(self, mock_direct_api):
        from server import manage_companies
        mock_direct_api.get.return_value = {"id": 1, "name": "Acme"}
        result = get_tool_fn(manage_companies)(action="get", company_id=1)
        assert result["success"] is True

    def test_list(self, mock_direct_api):
        from server import manage_companies
        mock_direct_api.list.return_value = []
        result = get_tool_fn(manage_companies)(action="list")
        assert result["success"] is True

    def test_delete(self, mock_direct_api):
        from server import manage_companies
        mock_direct_api.delete.return_value = {}
        result = get_tool_fn(manage_companies)(action="delete", company_id=1)
        assert result["success"] is True


class TestManageDepartments:
    def test_create(self, mock_direct_api):
        from server import manage_departments, DepartmentData
        mock_direct_api.create.return_value = {"id": 1, "name": "Engineering"}
        result = get_tool_fn(manage_departments)(action="create", department_data=DepartmentData(name="Engineering"))
        assert result["success"] is True

    def test_create_missing_name(self, mock_direct_api):
        from server import manage_departments, DepartmentData
        result = get_tool_fn(manage_departments)(action="create", department_data=DepartmentData())
        assert result["success"] is False

    def test_get(self, mock_direct_api):
        from server import manage_departments
        mock_direct_api.get.return_value = {"id": 1}
        result = get_tool_fn(manage_departments)(action="get", department_id=1)
        assert result["success"] is True

    def test_list(self, mock_direct_api):
        from server import manage_departments
        mock_direct_api.list.return_value = []
        result = get_tool_fn(manage_departments)(action="list")
        assert result["success"] is True

    def test_delete(self, mock_direct_api):
        from server import manage_departments
        mock_direct_api.delete.return_value = {}
        result = get_tool_fn(manage_departments)(action="delete", department_id=1)
        assert result["success"] is True


class TestManageGroups:
    def test_create(self, mock_direct_api):
        from server import manage_groups, GroupData
        mock_direct_api.create.return_value = {"id": 1, "name": "Admins"}
        result = get_tool_fn(manage_groups)(action="create", group_data=GroupData(name="Admins"))
        assert result["success"] is True

    def test_create_missing_name(self, mock_direct_api):
        from server import manage_groups, GroupData
        result = get_tool_fn(manage_groups)(action="create", group_data=GroupData())
        assert result["success"] is False

    def test_get(self, mock_direct_api):
        from server import manage_groups
        mock_direct_api.get.return_value = {"id": 1}
        result = get_tool_fn(manage_groups)(action="get", group_id=1)
        assert result["success"] is True

    def test_list(self, mock_direct_api):
        from server import manage_groups
        mock_direct_api.list.return_value = []
        result = get_tool_fn(manage_groups)(action="list")
        assert result["success"] is True

    def test_update_with_permissions(self, mock_direct_api):
        from server import manage_groups, GroupData
        mock_direct_api.update.return_value = {"id": 1}
        result = get_tool_fn(manage_groups)(
            action="update", group_id=1,
            group_data=GroupData(name="Admins", permissions={"admin": "1"})
        )
        assert result["success"] is True

    def test_delete(self, mock_direct_api):
        from server import manage_groups
        mock_direct_api.delete.return_value = {}
        result = get_tool_fn(manage_groups)(action="delete", group_id=1)
        assert result["success"] is True
