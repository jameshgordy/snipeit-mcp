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
# FastMCP 3.x exposes no public synchronous tool registry, so the whitelist is
# implemented with the server's enable/disable visibility controls. Disabled
# tools stay registered but are hidden from clients — they no longer appear in
# ``list_tools`` and cannot be called — which matches the previous behavior of
# dropping them from the tool set, and is freely re-applicable (e.g. from tests).


def apply_tool_whitelist(allowed_csv: str | None = None) -> None:
    """Apply the ``SNIPEIT_ALLOWED_TOOLS`` whitelist to ``mcp``.

    Pass ``None`` (the default) to read the value from the environment; pass an
    empty string to clear any active whitelist and restore the full tool set.
    """
    if allowed_csv is None:
        allowed_csv = os.getenv("SNIPEIT_ALLOWED_TOOLS", "").strip()

    if allowed_csv:
        allowed = {t.strip() for t in allowed_csv.split(",") if t.strip()}
        # Enable only the whitelisted tools, disabling every other tool.
        mcp.enable(names=allowed, components={"tool"}, only=True)
        logger.info(
            f"Tool whitelist active: only {sorted(allowed)} enabled; "
            "all other tools disabled."
        )
    else:
        # Re-enable the full tool set.
        mcp.enable(components={"tool"})
        logger.info("All tools enabled (no whitelist configured)")


apply_tool_whitelist()
