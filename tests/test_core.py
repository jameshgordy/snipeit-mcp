"""Tests for module import, entry point, and tool whitelist."""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestModuleImport:
    def test_server_imports(self):
        import server
        assert server is not None

    def test_mcp_instance_exists(self):
        import server
        assert hasattr(server, 'mcp')

    def test_main_function_exists(self):
        import server
        assert callable(server.main)

    def test_all_error_classes_importable(self):
        from server import (
            SnipeITException,
            SnipeITNotFoundError,
            SnipeITAuthenticationError,
            SnipeITValidationError,
        )
        assert SnipeITNotFoundError is not None

    def test_direct_api_class_exists(self):
        from server import SnipeITDirectAPI
        assert SnipeITDirectAPI is not None


class TestToolWhitelist:
    def test_no_whitelist_all_tools(self):
        """Without whitelist env var, all tools should be registered."""
        import server
        tools = server.mcp._tool_manager._tools
        # Should have all 39 tools
        assert len(tools) >= 38

    def test_whitelist_limits_tools(self):
        """Setting SNIPEIT_ALLOWED_TOOLS should limit available tools."""
        import importlib
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345',
            'SNIPEIT_ALLOWED_TOOLS': 'manage_assets,system_info',
        }):
            import server
            importlib.reload(server)
            tools = server.mcp._tool_manager._tools
            assert len(tools) == 2
            assert 'manage_assets' in tools
            assert 'system_info' in tools

        # Reload without whitelist to restore
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345',
        }, clear=False):
            os.environ.pop('SNIPEIT_ALLOWED_TOOLS', None)
            importlib.reload(server)

    def test_whitelist_nonexistent_tools(self):
        """Whitelist with nonexistent tool names should result in 0 tools."""
        import importlib
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345',
            'SNIPEIT_ALLOWED_TOOLS': 'nonexistent_tool',
        }):
            import server
            importlib.reload(server)
            tools = server.mcp._tool_manager._tools
            assert len(tools) == 0

        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345',
        }, clear=False):
            os.environ.pop('SNIPEIT_ALLOWED_TOOLS', None)
            importlib.reload(server)

    def test_whitelist_whitespace_handling(self):
        """Whitespace in whitelist should be trimmed."""
        import importlib
        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345',
            'SNIPEIT_ALLOWED_TOOLS': ' manage_assets , system_info ',
        }):
            import server
            importlib.reload(server)
            tools = server.mcp._tool_manager._tools
            assert len(tools) == 2

        with patch.dict(os.environ, {
            'SNIPEIT_URL': 'https://test.snipeit.com',
            'SNIPEIT_TOKEN': 'test-token-12345',
        }, clear=False):
            os.environ.pop('SNIPEIT_ALLOWED_TOOLS', None)
            importlib.reload(server)
