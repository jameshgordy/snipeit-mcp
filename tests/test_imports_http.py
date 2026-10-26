"""End-to-end tests for manage_imports, mocking only HTTP.

Runs the real ``SnipeITDirectAPI`` against ``responses`` so the Snipe-IT v8.8.1
shapes are asserted on the wire: ``ImportController::index`` returns a bare
array, there is no show/update method, and ``process`` takes the mapping as
``column-mappings`` alongside a required ``import-type``.
"""

import json


def get_tool_fn(tool):
    return tool.fn if hasattr(tool, "fn") else tool


BASE = "https://test.snipeit.com/api/v1"

IMPORT = {
    "id": 2,
    "file_path": "1-2026-10-26-144302-probe.csv",
    "filesize": "40B",
    "name": "",
    "import_type": "",
    "created_at": "0 seconds ago",
    "header_row": ["Name", "City"],
    "first_row": ["Probe", "Testville"],
    "field_map": None,
}


class TestManageImportsHttp:
    def test_list_bare_array(self):
        """Regression: list crashed with "'list' object has no attribute 'get'"."""
        import responses
        from snipeit_mcp import manage_imports

        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, f"{BASE}/imports", json=[IMPORT])
            result = get_tool_fn(manage_imports)(action="list")

        assert result == {"success": True, "action": "list", "count": 1, "imports": [IMPORT]}

    def test_list_empty(self):
        import responses
        from snipeit_mcp import manage_imports

        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, f"{BASE}/imports", json=[])
            result = get_tool_fn(manage_imports)(action="list")

        assert result["success"] is True
        assert result["count"] == 0

    def test_get_uses_index_not_show(self):
        """GET imports/{id} is a 500 in v8.8.1 (no show()); get reads the index."""
        import responses
        from snipeit_mcp import manage_imports

        with responses.RequestsMock() as rsps:
            rsps.add(responses.GET, f"{BASE}/imports", json=[{"id": 1}, IMPORT])
            result = get_tool_fn(manage_imports)(action="get", import_id=2)
            assert [c.request.url for c in rsps.calls] == [f"{BASE}/imports"]

        assert result["success"] is True
        assert result["import"]["header_row"] == ["Name", "City"]

    def test_process_sends_type_and_mapping(self):
        import responses
        from snipeit_mcp import manage_imports, ImportData

        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, f"{BASE}/imports/process/2",
                     json={"status": "success", "messages": {"redirect_url": "x"}, "payload": None})
            result = get_tool_fn(manage_imports)(
                action="process", import_id=2,
                import_data=ImportData(import_type="location",
                                       field_map={"Name": "name", "City": "city"},
                                       preserve_blanks=True),
            )
            request = rsps.calls[0].request

        assert result["success"] is True
        assert json.loads(request.body) == {
            "import-type": "location",
            "column-mappings": {"Name": "name", "City": "city"},
            "import-preserve-blanks": True,
        }

    def test_process_validation_error_is_failure(self):
        """Missing import-type comes back as HTTP 200 {"status": "error"}."""
        import responses
        from snipeit_mcp import manage_imports, ImportData

        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, f"{BASE}/imports/process/2",
                     json={"status": "error",
                           "messages": {"import-type": ["The import-type field is required."]},
                           "payload": None})
            result = get_tool_fn(manage_imports)(
                action="process", import_id=2, import_data=ImportData(import_type="asset"))

        assert result["success"] is False
        assert "import-type field is required" in result["error"]

    def test_process_import_errors_surface_messages(self):
        """Row errors are HTTP 500 {"status": "import-errors"}; keep the messages."""
        import responses
        from snipeit_mcp import manage_imports, ImportData

        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, f"{BASE}/imports/process/2", status=500,
                     json={"status": "import-errors",
                           "messages": {"": {"Name": {"Name": ["The value for Name cannot be null."]}}},
                           "payload": {"tally": {"created": 0, "updated": 0}}})
            result = get_tool_fn(manage_imports)(
                action="process", import_id=2,
                import_data=ImportData(import_type="location", field_map={"Name": None}))

        assert result["success"] is False
        assert "cannot be null" in result["error"]
        assert result["tally"] == {"created": 0, "updated": 0}

    def test_process_500_without_json_is_failure(self):
        import responses
        from snipeit_mcp import manage_imports, ImportData

        with responses.RequestsMock() as rsps:
            rsps.add(responses.POST, f"{BASE}/imports/process/2", status=500, body="<html>oops</html>")
            result = get_tool_fn(manage_imports)(
                action="process", import_id=2, import_data=ImportData(import_type="asset"))

        assert result["success"] is False
        assert "500" in result["error"]
