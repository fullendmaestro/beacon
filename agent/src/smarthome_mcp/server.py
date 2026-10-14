from fastmcp import FastMCP

from .tools import (
    register_access_tools,
    register_appliance_tools,
    register_blind_tools,
    register_climate_tools,
    register_home_tools,
    register_light_tools,
)

# Initialize the Smart Home MCP Server
mcp = FastMCP("Beacon Smart Home Server")

# Register all modular smart home domain tool suites
register_home_tools(mcp)
register_light_tools(mcp)
register_access_tools(mcp)
register_blind_tools(mcp)
register_climate_tools(mcp)
register_appliance_tools(mcp)

if __name__ == "__main__":
    mcp.run()