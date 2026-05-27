"""Tests for module import, entry point, and tool whitelist."""


class TestModuleImport:
    def test_server_imports(self):
        import snipeit_mcp as server
        assert server is not None

    def test_mcp_instance_exists(self):
        import snipeit_mcp as server
        assert hasattr(server, 'mcp')

    def test_main_function_exists(self):
        import snipeit_mcp as server
        assert callable(server.main)

    def test_all_error_classes_importable(self):
        from snipeit_mcp import (
            SnipeITAuthenticationError,
            SnipeITException,
            SnipeITNotFoundError,
            SnipeITValidationError,
        )
        assert SnipeITNotFoundError is not None
        assert SnipeITException is not None
        assert SnipeITAuthenticationError is not None
        assert SnipeITValidationError is not None

    def test_direct_api_class_exists(self):
        from snipeit_mcp import SnipeITDirectAPI
        assert SnipeITDirectAPI is not None


class TestToolWhitelist:
    """Whitelist filtering is implemented in :func:`snipeit_mcp.mcp_server.apply_tool_whitelist`.

    Tests drive the function directly rather than reloading modules — package-level
    ``importlib.reload`` does not transitively re-import submodules, so the previous
    flat-layout reload trick no longer works here.
    """

    def test_no_whitelist_all_tools(self):
        from snipeit_mcp.mcp_server import apply_tool_whitelist, mcp
        apply_tool_whitelist("")
        assert len(mcp._tool_manager._tools) >= 38

    def test_whitelist_limits_tools(self):
        from snipeit_mcp.mcp_server import apply_tool_whitelist, mcp
        try:
            apply_tool_whitelist("manage_assets,system_info")
            tools = mcp._tool_manager._tools
            assert len(tools) == 2
            assert "manage_assets" in tools
            assert "system_info" in tools
        finally:
            apply_tool_whitelist("")

    def test_whitelist_nonexistent_tools(self):
        from snipeit_mcp.mcp_server import apply_tool_whitelist, mcp
        try:
            apply_tool_whitelist("nonexistent_tool")
            assert len(mcp._tool_manager._tools) == 0
        finally:
            apply_tool_whitelist("")

    def test_whitelist_whitespace_handling(self):
        from snipeit_mcp.mcp_server import apply_tool_whitelist, mcp
        try:
            apply_tool_whitelist(" manage_assets , system_info ")
            assert len(mcp._tool_manager._tools) == 2
        finally:
            apply_tool_whitelist("")
