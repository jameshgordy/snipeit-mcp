"""Shared fixtures for Snipe-IT MCP Server tests."""

import pytest
import os
from unittest.mock import MagicMock, patch

ENV_VARS = {
    'SNIPEIT_URL': 'https://test.snipeit.com',
    'SNIPEIT_TOKEN': 'test-token-12345',
}


@pytest.fixture(autouse=True)
def mock_env():
    with patch.dict(os.environ, ENV_VARS):
        yield


@pytest.fixture
def mock_direct_api():
    with patch('server.get_direct_api') as m:
        api = MagicMock()
        m.return_value = api
        yield api


@pytest.fixture
def mock_client():
    with patch('server.get_snipeit_client') as m:
        client = MagicMock()
        client.__enter__ = MagicMock(return_value=client)
        client.__exit__ = MagicMock(return_value=False)
        m.return_value = client
        yield client


def get_tool_fn(tool):
    """Extract the underlying function from a FastMCP FunctionTool."""
    return tool.fn if hasattr(tool, 'fn') else tool
