"""Entry point for the Snipe-IT MCP server."""

from .mcp_server import mcp


def main() -> None:
    """Run the MCP server over stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
