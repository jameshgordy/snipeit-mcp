"""Tests for Snipe-IT MCP Server.

Tests cover:
- Module import and server initialization
- Pydantic model validation
- Tool function behavior with mocked API responses
- Error handling for invalid inputs
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_tool_fn(tool):
    """Extract the underlying function from a FastMCP FunctionTool."""
    if hasattr(tool, 'fn'):
        return tool.fn
    return tool


# ============================================================================
# Module Import Tests
# ============================================================================

class TestModuleImport:
    """Test that the server module loads correctly."""

    def test_server_imports_without_error(self):
        """Server module should import without raising exceptions."""
        # Import with mocked environment variables
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            import server
            assert server is not None

    def test_server_has_mcp_instance(self):
        """Server should have an MCP instance."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            import server
            assert hasattr(server, 'mcp')


# ============================================================================
# Pydantic Model Tests
# ============================================================================

class TestPydanticModels:
    """Test Pydantic model validation."""

    def test_asset_data_model_valid(self):
        """AssetData should accept valid data."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import AssetData

            asset = AssetData(
                status_id=1,
                model_id=5,
                name="Test Laptop",
                asset_tag="LAP-001",
                serial="ABC123"
            )

            assert asset.status_id == 1
            assert asset.model_id == 5
            assert asset.name == "Test Laptop"

    def test_asset_data_model_optional_fields(self):
        """AssetData should allow None for optional fields."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import AssetData

            asset = AssetData(status_id=1, model_id=5)

            assert asset.name is None
            assert asset.serial is None
            assert asset.purchase_cost is None

    def test_import_data_model_valid(self):
        """ImportData should accept valid import types."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import ImportData

            import_config = ImportData(
                import_type="asset",
                run_backup=True
            )

            assert import_config.import_type == "asset"
            assert import_config.run_backup is True

    def test_import_data_model_field_map(self):
        """ImportData should accept field mapping dictionaries."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import ImportData

            import_config = ImportData(
                import_type="asset",
                field_map={"Column A": "asset_tag", "Column B": "name"}
            )

            assert import_config.field_map == {"Column A": "asset_tag", "Column B": "name"}

    def test_asset_request_data_model(self):
        """AssetRequestData should validate correctly."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import AssetRequestData

            request = AssetRequestData(
                expected_checkout="2025-02-01",
                note="Need for project"
            )

            assert request.expected_checkout == "2025-02-01"
            assert request.note == "Need for project"

    def test_user_data_model_required_fields(self):
        """UserData should require essential fields for creation."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import UserData

            user = UserData(
                first_name="John",
                last_name="Doe",
                username="jdoe",
                password="secret123",
                password_confirmation="secret123"
            )

            assert user.first_name == "John"
            assert user.username == "jdoe"

    def test_location_data_model(self):
        """LocationData should accept location fields."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import LocationData

            location = LocationData(
                name="Main Office",
                city="New York",
                country="US"
            )

            assert location.name == "Main Office"
            assert location.city == "New York"

    def test_fieldset_data_model(self):
        """FieldsetData should accept fieldset configuration."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import FieldsetData

            fieldset = FieldsetData(name="Hardware Fields")

            assert fieldset.name == "Hardware Fields"


# ============================================================================
# Tool Function Tests with Mocked API
# ============================================================================

class TestManageAssetsTool:
    """Test manage_assets tool function."""

    @patch('server.get_snipeit_client')
    @patch('server.get_direct_api')
    def test_manage_assets_get_by_tag(self, mock_direct_api, mock_client):
        """manage_assets should use bytag endpoint for asset_tag lookup."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import manage_assets

            mock_api = MagicMock()
            mock_api._request.return_value = {
                "id": 123,
                "asset_tag": "LAP-001",
                "name": "Test Laptop"
            }
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(manage_assets)
            result = fn(action="get", asset_tag="LAP-001")

            assert result["success"] is True
            assert result["action"] == "get"
            mock_api._request.assert_called_with("GET", "hardware/bytag/LAP-001")

    @patch('server.get_snipeit_client')
    @patch('server.get_direct_api')
    def test_manage_assets_get_by_serial(self, mock_direct_api, mock_client):
        """manage_assets should use byserial endpoint for serial lookup."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import manage_assets

            mock_api = MagicMock()
            mock_api._request.return_value = {
                "rows": [{"id": 123, "serial": "ABC123", "name": "Test Laptop"}],
                "total": 1
            }
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(manage_assets)
            result = fn(action="get", serial="ABC123")

            assert result["success"] is True
            mock_api._request.assert_called_with("GET", "hardware/byserial/ABC123")

    @patch('server.get_snipeit_client')
    def test_manage_assets_list_with_filters(self, mock_client):
        """manage_assets list should pass filter parameters."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import manage_assets

            mock_assets = MagicMock()
            mock_assets.list.return_value = []
            mock_client_instance = MagicMock()
            mock_client_instance.assets = mock_assets
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            mock_client.return_value = mock_client_instance

            fn = get_tool_fn(manage_assets)
            result = fn(
                action="list",
                status_id=1,
                model_id=5,
                location_id=10
            )

            assert result["success"] is True
            # Verify filters were passed
            call_kwargs = mock_assets.list.call_args[1]
            assert call_kwargs.get("status_id") == 1
            assert call_kwargs.get("model_id") == 5
            assert call_kwargs.get("location_id") == 10

    def test_manage_assets_missing_id_for_get(self):
        """manage_assets get should fail without any identifier."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import manage_assets

            fn = get_tool_fn(manage_assets)
            result = fn(action="get")

            assert result["success"] is False
            assert "required" in result["error"].lower()


class TestManageImportsTool:
    """Test manage_imports tool function."""

    @patch('server.get_direct_api')
    def test_manage_imports_list(self, mock_direct_api):
        """manage_imports list should return import files."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import manage_imports

            mock_api = MagicMock()
            mock_api._request.return_value = {
                "rows": [
                    {"id": 1, "filename": "assets.csv"},
                    {"id": 2, "filename": "users.csv"}
                ]
            }
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(manage_imports)
            result = fn(action="list")

            assert result["success"] is True
            assert result["count"] == 2
            mock_api._request.assert_called_with("GET", "imports")

    @patch('server.get_direct_api')
    def test_manage_imports_get(self, mock_direct_api):
        """manage_imports get should fetch import details."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import manage_imports

            mock_api = MagicMock()
            mock_api._request.return_value = {
                "id": 1,
                "filename": "assets.csv",
                "field_map": {}
            }
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(manage_imports)
            result = fn(action="get", import_id=1)

            assert result["success"] is True
            mock_api._request.assert_called_with("GET", "imports/1")

    def test_manage_imports_get_missing_id(self):
        """manage_imports get should fail without import_id."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import manage_imports

            fn = get_tool_fn(manage_imports)
            result = fn(action="get")

            assert result["success"] is False
            assert "import_id" in result["error"]

    def test_manage_imports_upload_missing_path(self):
        """manage_imports upload should fail without file_path."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import manage_imports

            fn = get_tool_fn(manage_imports)
            result = fn(action="upload")

            assert result["success"] is False
            assert "file_path" in result["error"]


class TestAuditTrackingTool:
    """Test audit_tracking tool function."""

    @patch('server.get_direct_api')
    def test_audit_tracking_due(self, mock_direct_api):
        """audit_tracking due should return assets approaching audit."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import audit_tracking

            mock_api = MagicMock()
            mock_api._request.return_value = {
                "rows": [{"id": 1, "asset_tag": "LAP-001"}],
                "total": 1
            }
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(audit_tracking)
            result = fn(action="due")

            assert result["success"] is True
            assert result["action"] == "due"
            assert result["count"] == 1

    @patch('server.get_direct_api')
    def test_audit_tracking_overdue(self, mock_direct_api):
        """audit_tracking overdue should return past-due assets."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import audit_tracking

            mock_api = MagicMock()
            mock_api._request.return_value = {
                "rows": [{"id": 2, "asset_tag": "LAP-002"}],
                "total": 1
            }
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(audit_tracking)
            result = fn(action="overdue")

            assert result["success"] is True
            assert result["action"] == "overdue"

    @patch('server.get_direct_api')
    def test_audit_tracking_summary(self, mock_direct_api):
        """audit_tracking summary should return both due and overdue counts."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import audit_tracking

            mock_api = MagicMock()
            mock_api._request.side_effect = [
                {"rows": [{"id": 1}], "total": 5},  # due
                {"rows": [{"id": 2}], "total": 3},  # overdue
            ]
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(audit_tracking)
            result = fn(action="summary")

            assert result["success"] is True
            assert result["action"] == "summary"
            assert result["due_count"] == 5
            assert result["overdue_count"] == 3


class TestStatusSummaryTool:
    """Test status_summary tool function."""

    @patch('server.get_direct_api')
    def test_status_summary(self, mock_direct_api):
        """status_summary should return asset counts by status."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import status_summary

            mock_api = MagicMock()
            mock_api._request.return_value = {
                "Deployed": 50,
                "Ready to Deploy": 25,
                "Pending": 10
            }
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(status_summary)
            result = fn()

            assert result["success"] is True
            mock_api._request.assert_called_with("GET", "statuslabels/assets")


class TestAssetRequestsTool:
    """Test asset_requests tool function."""

    @patch('server.get_direct_api')
    def test_asset_requests_request(self, mock_direct_api):
        """asset_requests request should submit checkout request."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import asset_requests

            mock_api = MagicMock()
            mock_api._request.return_value = {"status": "success"}
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(asset_requests)
            result = fn(action="request", asset_id=123)

            assert result["success"] is True
            assert result["action"] == "request"
            mock_api._request.assert_called_with(
                "POST", "hardware/123/request", json=None
            )

    @patch('server.get_direct_api')
    def test_asset_requests_cancel(self, mock_direct_api):
        """asset_requests cancel should cancel pending request."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import asset_requests

            mock_api = MagicMock()
            mock_api._request.return_value = {"status": "success"}
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(asset_requests)
            result = fn(action="cancel", asset_id=123)

            assert result["success"] is True
            assert result["action"] == "cancel"


class TestUserTwoFactorTool:
    """Test user_two_factor tool function."""

    @patch('server.get_direct_api')
    def test_user_two_factor_reset(self, mock_direct_api):
        """user_two_factor reset should trigger 2FA reset."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import user_two_factor

            mock_api = MagicMock()
            mock_api._request.return_value = {"status": "success"}
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(user_two_factor)
            result = fn(action="reset", user_id=456)

            assert result["success"] is True
            assert result["action"] == "reset"
            assert result["user_id"] == 456
            mock_api._request.assert_called_with(
                "POST", "users/456/two_factor_reset"
            )


class TestSystemInfoTool:
    """Test system_info tool function."""

    @patch('server.get_direct_api')
    def test_system_info(self, mock_direct_api):
        """system_info should return version information."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import system_info

            mock_api = MagicMock()
            mock_api._request.return_value = {
                "version": "6.1.0",
                "php_version": "8.1.0"
            }
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(system_info)
            result = fn()

            assert result["success"] is True
            assert "version_info" in result
            mock_api._request.assert_called_with("GET", "version")


class TestManageFieldsetsReorder:
    """Test manage_fieldsets reorder action."""

    @patch('server.get_direct_api')
    def test_fieldsets_reorder(self, mock_direct_api):
        """manage_fieldsets reorder should update field order."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import manage_fieldsets

            mock_api = MagicMock()
            mock_api._request.return_value = {"status": "success"}
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(manage_fieldsets)
            result = fn(
                action="reorder",
                fieldset_id=1,
                field_order=[5, 3, 1, 2, 4]
            )

            assert result["success"] is True
            assert result["action"] == "reorder"
            mock_api._request.assert_called_with(
                "POST",
                "fields/fieldsets/1/order",
                json={"item": [5, 3, 1, 2, 4]}
            )

    def test_fieldsets_reorder_missing_order(self):
        """manage_fieldsets reorder should fail without field_order."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import manage_fieldsets

            fn = get_tool_fn(manage_fieldsets)
            result = fn(action="reorder", fieldset_id=1)

            assert result["success"] is False
            assert "field_order" in result["error"]


# ============================================================================
# Extended Tool Tests
# ============================================================================

class TestManageLocationsExtended:
    """Test extended manage_locations functionality."""

    @patch('server.get_snipeit_client')
    @patch('server.get_direct_api')
    def test_locations_assets_action(self, mock_direct_api, mock_client):
        """manage_locations assets should list assets at location."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import manage_locations

            # Mock client for the context manager
            mock_client_instance = MagicMock()
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            mock_client.return_value = mock_client_instance

            mock_api = MagicMock()
            mock_api._request.return_value = {
                "rows": [{"id": 1, "asset_tag": "LAP-001"}],
                "total": 1
            }
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(manage_locations)
            result = fn(action="assets", location_id=10)

            assert result["success"] is True
            assert result["action"] == "assets"

    @patch('server.get_snipeit_client')
    @patch('server.get_direct_api')
    def test_locations_users_action(self, mock_direct_api, mock_client):
        """manage_locations users should list users at location."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import manage_locations

            mock_client_instance = MagicMock()
            mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
            mock_client_instance.__exit__ = MagicMock(return_value=False)
            mock_client.return_value = mock_client_instance

            mock_api = MagicMock()
            mock_api._request.return_value = {
                "rows": [{"id": 1, "username": "jdoe"}],
                "total": 1
            }
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(manage_locations)
            result = fn(action="users", location_id=10)

            assert result["success"] is True
            assert result["action"] == "users"


class TestUserAssetsExtended:
    """Test extended user_assets functionality."""

    @patch('server.get_direct_api')
    def test_user_assets_consumables(self, mock_direct_api):
        """user_assets should fetch consumables when requested."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import user_assets

            mock_api = MagicMock()
            mock_api._request.return_value = {"rows": [{"id": 1, "name": "Toner"}]}
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(user_assets)
            result = fn(user_id=123, asset_type="consumables")

            assert result["success"] is True
            assert "consumables" in result
            mock_api._request.assert_called_with("GET", "users/123/consumables")

    @patch('server.get_direct_api')
    def test_user_assets_eulas(self, mock_direct_api):
        """user_assets should fetch EULAs when requested."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import user_assets

            mock_api = MagicMock()
            mock_api._request.return_value = {"rows": []}
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(user_assets)
            result = fn(user_id=123, asset_type="eulas")

            assert result["success"] is True
            assert "eulas" in result
            mock_api._request.assert_called_with("GET", "users/123/eulas")


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling across tools."""

    @patch('server.get_direct_api')
    def test_not_found_error_handling(self, mock_direct_api):
        """Tools should handle SnipeITNotFoundError gracefully."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import audit_tracking, SnipeITNotFoundError

            mock_api = MagicMock()
            mock_api._request.side_effect = SnipeITNotFoundError("Resource not found")
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(audit_tracking)
            result = fn(action="due")

            assert result["success"] is False
            assert "not found" in result["error"].lower()

    @patch('server.get_direct_api')
    def test_authentication_error_handling(self, mock_direct_api):
        """Tools should handle SnipeITAuthenticationError gracefully."""
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345'
        }):
            from server import system_info, SnipeITAuthenticationError

            mock_api = MagicMock()
            mock_api._request.side_effect = SnipeITAuthenticationError("Invalid token")
            mock_direct_api.return_value = mock_api

            fn = get_tool_fn(system_info)
            result = fn()

            assert result["success"] is False
            assert "authentication" in result["error"].lower()
