from fastmcp import FastMCP

from .tools.light_tools import register_light_tools

# Initialize the Smart Home MCP Server
mcp = FastMCP("Beacon Smart Home Server")

# Register smart home light tools
register_light_tools(mcp)

if __name__ == "__main__":
    mcp.run()
