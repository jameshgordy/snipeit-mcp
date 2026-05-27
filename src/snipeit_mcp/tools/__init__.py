"""Snipe-IT MCP tool modules.

Importing this package imports each submodule in turn, which causes
their ``@mcp.tool`` decorators to register tools on the shared
:data:`snipeit_mcp.mcp_server.mcp` instance.
"""

from . import assets  # noqa: F401
from . import inventory  # noqa: F401
from . import foundational  # noqa: F401
from . import licenses  # noqa: F401
from . import people  # noqa: F401
from . import custom_fields  # noqa: F401
from . import reports  # noqa: F401
from . import imports  # noqa: F401
from . import system  # noqa: F401
