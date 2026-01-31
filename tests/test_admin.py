"""Tests for admin tools: manage_imports, system_info, manage_backups, ldap_operations, model_files, activity_reports, status_summary, audit_tracking."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_tool_fn(tool):
    return tool.fn if hasattr(tool, "fn") else tool


class TestManageImports:
    def test_list(self, mock_direct_api):
        from server import manage_imports
        mock_direct_api._request.return_value = {"rows": [{"id": 1, "filename": "assets.csv"}, {"id": 2, "filename": "users.csv"}]}
        result = get_tool_fn(manage_imports)(action="list")
        assert result["success"] is True
        assert result["count"] == 2

    def test_get(self, mock_direct_api):
        from server import manage_imports
        mock_direct_api._request.return_value = {"id": 1, "filename": "assets.csv"}
        result = get_tool_fn(manage_imports)(action="get", import_id=1)
        assert result["success"] is True
        mock_direct_api._request.assert_called_with("GET", "imports/1")

    def test_get_missing_id(self):
        from server import manage_imports
        result = get_tool_fn(manage_imports)(action="get")
        assert result["success"] is False
        assert "import_id" in result["error"]

    def test_upload_missing_path(self):
        from server import manage_imports
        result = get_tool_fn(manage_imports)(action="upload")
        assert result["success"] is False
        assert "file_path" in result["error"]

    def test_update(self, mock_direct_api):
        from server import manage_imports, ImportData
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(manage_imports)(action="update", import_id=1, import_data=ImportData(import_type="asset"))
        assert result["success"] is True

    def test_update_missing_id(self):
        from server import manage_imports, ImportData
        result = get_tool_fn(manage_imports)(action="update", import_data=ImportData(import_type="asset"))
        assert result["success"] is False

    def test_delete(self, mock_direct_api):
        from server import manage_imports
        mock_direct_api._request.return_value = {}
        result = get_tool_fn(manage_imports)(action="delete", import_id=1)
        assert result["success"] is True

    def test_delete_missing_id(self):
        from server import manage_imports
        result = get_tool_fn(manage_imports)(action="delete")
        assert result["success"] is False

    def test_process(self, mock_direct_api):
        from server import manage_imports
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(manage_imports)(action="process", import_id=1)
        assert result["success"] is True

    def test_process_missing_id(self):
        from server import manage_imports
        result = get_tool_fn(manage_imports)(action="process")
        assert result["success"] is False


class TestSystemInfo:
    def test_basic(self, mock_direct_api):
        from server import system_info
        mock_direct_api._request.return_value = {"version": "6.1.0", "php_version": "8.1.0"}
        result = get_tool_fn(system_info)()
        assert result["success"] is True
        assert "version_info" in result
        mock_direct_api._request.assert_called_with("GET", "version")


class TestManageBackups:
    def test_list(self, mock_direct_api):
        from server import manage_backups
        mock_direct_api._request.return_value = {"rows": [{"filename": "backup.sql"}]}
        result = get_tool_fn(manage_backups)(action="list")
        assert result["success"] is True

    def test_download_missing_filename(self, mock_direct_api):
        from server import manage_backups
        result = get_tool_fn(manage_backups)(action="download")
        assert result["success"] is False

    def test_download_missing_save_path(self, mock_direct_api):
        from server import manage_backups
        result = get_tool_fn(manage_backups)(action="download", filename="backup.sql")
        assert result["success"] is False


class TestLdapOperations:
    def test_sync(self, mock_direct_api):
        from server import ldap_operations
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(ldap_operations)(action="sync")
        assert result["success"] is True
        assert result["action"] == "sync"

    def test_test(self, mock_direct_api):
        from server import ldap_operations
        mock_direct_api._request.return_value = {"status": "success"}
        result = get_tool_fn(ldap_operations)(action="test")
        assert result["success"] is True
        assert result["action"] == "test"


class TestModelFiles:
    def test_list(self, mock_direct_api):
        from server import model_files
        mock_direct_api._request.return_value = {"rows": []}
        result = get_tool_fn(model_files)(action="list", model_id=1)
        assert result["success"] is True

    def test_upload_missing_path(self, mock_direct_api):
        from server import model_files
        result = get_tool_fn(model_files)(action="upload", model_id=1)
        assert result["success"] is False

    def test_download_missing_file_id(self, mock_direct_api):
        from server import model_files
        result = get_tool_fn(model_files)(action="download", model_id=1)
        assert result["success"] is False

    def test_delete(self, mock_direct_api):
        from server import model_files
        mock_direct_api._request.return_value = {}
        result = get_tool_fn(model_files)(action="delete", model_id=1, file_id=5)
        assert result["success"] is True

    def test_delete_missing_file_id(self, mock_direct_api):
        from server import model_files
        result = get_tool_fn(model_files)(action="delete", model_id=1)
        assert result["success"] is False


class TestActivityReports:
    def test_list(self, mock_direct_api):
        from server import activity_reports
        mock_direct_api._request.return_value = {"rows": [{"id": 1, "action_type": "checkout"}]}
        result = get_tool_fn(activity_reports)(action="list")
        assert result["success"] is True
        assert result["count"] == 1

    def test_list_with_filters(self, mock_direct_api):
        from server import activity_reports
        mock_direct_api._request.return_value = {"rows": []}
        result = get_tool_fn(activity_reports)(action="list", target_type="asset", action_type="checkout")
        assert result["success"] is True

    def test_item_activity(self, mock_direct_api):
        from server import activity_reports
        mock_direct_api._request.return_value = {"rows": [{"id": 1}]}
        result = get_tool_fn(activity_reports)(action="item_activity", item_type="asset", item_id=1)
        assert result["success"] is True
        assert result["action"] == "item_activity"

    def test_item_activity_missing_params(self, mock_direct_api):
        from server import activity_reports
        result = get_tool_fn(activity_reports)(action="item_activity")
        assert result["success"] is False

    def test_item_activity_invalid_type(self, mock_direct_api):
        from server import activity_reports
        result = get_tool_fn(activity_reports)(action="item_activity", item_type="invalid", item_id=1)
        assert result["success"] is False


class TestStatusSummary:
    def test_basic(self, mock_direct_api):
        from server import status_summary
        mock_direct_api._request.return_value = {"Deployed": 50, "Pending": 10}
        result = get_tool_fn(status_summary)()
        assert result["success"] is True
        mock_direct_api._request.assert_called_with("GET", "statuslabels/assets")


class TestAuditTracking:
    def test_due(self, mock_direct_api):
        from server import audit_tracking
        mock_direct_api._request.return_value = {"rows": [{"id": 1}], "total": 1}
        result = get_tool_fn(audit_tracking)(action="due")
        assert result["success"] is True
        assert result["action"] == "due"
        assert result["count"] == 1

    def test_overdue(self, mock_direct_api):
        from server import audit_tracking
        mock_direct_api._request.return_value = {"rows": [{"id": 2}], "total": 1}
        result = get_tool_fn(audit_tracking)(action="overdue")
        assert result["success"] is True
        assert result["action"] == "overdue"

    def test_summary(self, mock_direct_api):
        from server import audit_tracking
        mock_direct_api._request.side_effect = [
            {"rows": [{"id": 1}], "total": 5},
            {"rows": [{"id": 2}], "total": 3},
        ]
        result = get_tool_fn(audit_tracking)(action="summary")
        assert result["success"] is True
        assert result["due_count"] == 5
        assert result["overdue_count"] == 3
