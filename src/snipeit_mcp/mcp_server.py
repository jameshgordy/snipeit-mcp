"""FastMCP server instance and tool registration for the Snipe-IT MCP server.

This module owns the singleton :class:`fastmcp.FastMCP` instance. Tool modules
under :mod:`snipeit_mcp.tools` import ``mcp`` from here and attach themselves
via ``@mcp.tool(...)`` decorators. Importing this module triggers registration
of every tool by importing :mod:`snipeit_mcp.tools` at the bottom.
"""

import logging
import os

from fastmcp import FastMCP

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

mcp = FastMCP(name="Snipe-IT MCP Server")

# Import tool modules so their @mcp.tool decorators run and register tools on `mcp`.
# Placed after `mcp` is defined so submodules can import it from this module.
from . import tools  # noqa: E402, F401

# ============================================================================
# Tool Whitelist Configuration
# ============================================================================
# Snapshot the full tool set immediately after all `tools/*.py` modules have been
# imported, so the whitelist can be re-applied repeatedly (e.g. from tests)
# without losing the tools filtered out by an earlier call.
_ALL_TOOLS: dict = dict(mcp._tool_manager._tools)


def apply_tool_whitelist(allowed_csv: str | None = None) -> None:
    """Apply the ``SNIPEIT_ALLOWED_TOOLS`` whitelist to ``mcp``.

    Pass ``None`` (the default) to read the value from the environment; pass an
    empty string to clear any active whitelist and restore the full tool set.
    """
    if allowed_csv is None:
        allowed_csv = os.getenv("SNIPEIT_ALLOWED_TOOLS", "").strip()

    if allowed_csv:
        allowed = {t.strip() for t in allowed_csv.split(",") if t.strip()}
        mcp._tool_manager._tools = {
            name: tool for name, tool in _ALL_TOOLS.items() if name in allowed
        }
        logger.info(
            f"Tool whitelist active: {len(mcp._tool_manager._tools)}/{len(_ALL_TOOLS)} "
            f"tools enabled. Allowed: {sorted(allowed)}"
        )
    else:
        mcp._tool_manager._tools = dict(_ALL_TOOLS)
        logger.info(f"All {len(mcp._tool_manager._tools)} tools enabled (no whitelist configured)")


apply_tool_whitelist()
