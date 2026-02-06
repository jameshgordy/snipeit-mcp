"""Tests for licensing tools: manage_licenses, license_seats, license_files."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_tool_fn(tool):
    return tool.fn if hasattr(tool, "fn") else tool


class TestManageLicenses:
    def test_create(self, mock_direct_api):
        from server import manage_licenses, LicenseData
        mock_direct_api.create.return_value = {"payload": {"id": 1, "name": "Office", "seats": 10}}
        result = get_tool_fn(manage_licenses)(action="create", license_data=LicenseData(name="Office", seats=10))
        assert result["success"] is True
        assert result["action"] == "create"

    def test_create_missing_data(self, mock_direct_api):
        from server import manage_licenses
        result = get_tool_fn(manage_licenses)(action="create")
        assert result["success"] is False

    def test_create_missing_required(self, mock_direct_api):
        from server import manage_licenses, LicenseData
        result = get_tool_fn(manage_licenses)(action="create", license_data=LicenseData())
        assert result["success"] is False

    def test_get(self, mock_direct_api):
        from server import manage_licenses
        mock_direct_api.get.return_value = {"id": 1, "name": "Office", "seats": 10}
        result = get_tool_fn(manage_licenses)(action="get", license_id=1)
        assert result["success"] is True

    def test_get_missing_id(self, mock_direct_api):
        from server import manage_licenses
        result = get_tool_fn(manage_licenses)(action="get")
        assert result["success"] is False

    def test_list(self, mock_direct_api):
        from server import manage_licenses
        mock_direct_api.list.return_value = []
        result = get_tool_fn(manage_licenses)(action="list")
        assert result["success"] is True
        assert result["count"] == 0

    def test_update(self, mock_direct_api):
        from server import manage_licenses, LicenseData
        mock_direct_api.update.return_value = {"payload": {"id": 1, "name": "Updated"}}
        result = get_tool_fn(manage_licenses)(action="update", license_id=1, license_data=LicenseData(name="Updated"))
        assert result["success"] is True

    def test_update_missing_id(self, mock_direct_api):
        from server import manage_licenses, LicenseData
        result = get_tool_fn(manage_licenses)(action="update", license_data=LicenseData(name="X"))
        assert result["success"] is False

    def test_delete(self, mock_direct_api):
        from server import manage_licenses
        mock_direct_api.delete.return_value = {}
        result = get_tool_fn(manage_licenses)(action="delete", license_id=1)
        assert result["success"] is True

    def test_delete_missing_id(self, mock_direct_api):
        from server import manage_licenses
        result = get_tool_fn(manage_licenses)(action="delete")
        assert result["success"] is False


class TestLicenseSeats:
    def test_list(self, mock_direct_api):
        from server import license_seats
        mock_direct_api._request.return_value = {"rows": [{"id": 1, "name": "Seat 1"}], "total": 1}
        result = get_tool_fn(license_seats)(action="list", license_id=1)
        assert result["success"] is True
        assert result["count"] == 1

    def test_list_missing_id(self, mock_direct_api):
        from server import license_seats
        result = get_tool_fn(license_seats)(action="list")
        assert result["success"] is False

    def test_checkout(self, mock_direct_api):
        from server import license_seats, LicenseSeatCheckout
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(license_seats)(
            action="checkout", license_id=1, seat_id=1,
            checkout_data=LicenseSeatCheckout(assigned_to=5)
        )
        assert result["success"] is True

    def test_checkout_missing_seat_id(self, mock_direct_api):
        from server import license_seats, LicenseSeatCheckout
        result = get_tool_fn(license_seats)(
            action="checkout", license_id=1,
            checkout_data=LicenseSeatCheckout(assigned_to=5)
        )
        assert result["success"] is False

    def test_checkout_missing_data(self, mock_direct_api):
        from server import license_seats
        result = get_tool_fn(license_seats)(action="checkout", license_id=1, seat_id=1)
        assert result["success"] is False

    def test_checkout_missing_assigned(self, mock_direct_api):
        from server import license_seats, LicenseSeatCheckout
        result = get_tool_fn(license_seats)(
            action="checkout", license_id=1, seat_id=1,
            checkout_data=LicenseSeatCheckout()
        )
        assert result["success"] is False

    def test_checkin(self, mock_direct_api):
        from server import license_seats
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(license_seats)(action="checkin", seat_id=1)
        assert result["success"] is True

    def test_checkin_missing_seat_id(self, mock_direct_api):
        from server import license_seats
        result = get_tool_fn(license_seats)(action="checkin")
        assert result["success"] is False


class TestLicenseFiles:
    def test_list(self, mock_direct_api):
        from server import license_files
        mock_direct_api._request.return_value = {"rows": []}
        result = get_tool_fn(license_files)(action="list", license_id=1)
        assert result["success"] is True

    def test_upload_missing_path(self, mock_direct_api):
        from server import license_files
        result = get_tool_fn(license_files)(action="upload", license_id=1)
        assert result["success"] is False

    def test_download_missing_file_id(self, mock_direct_api):
        from server import license_files
        result = get_tool_fn(license_files)(action="download", license_id=1)
        assert result["success"] is False

    def test_download_missing_save_path(self, mock_direct_api):
        from server import license_files
        result = get_tool_fn(license_files)(action="download", license_id=1, file_id=1)
        assert result["success"] is False

    def test_delete(self, mock_direct_api):
        from server import license_files
        mock_direct_api._request.return_value = {}
        result = get_tool_fn(license_files)(action="delete", license_id=1, file_id=5)
        assert result["success"] is True

    def test_delete_missing_file_id(self, mock_direct_api):
        from server import license_files
        result = get_tool_fn(license_files)(action="delete", license_id=1)
        assert result["success"] is False
