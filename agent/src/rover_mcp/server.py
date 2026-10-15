from fastmcp import FastMCP

from .tools.navigation_manipulation_tools import register_rover_tools

# Initialize the standalone Rover MCP Server
rover_mcp = FastMCP("Beacon Autonomous Rover Server")

register_rover_tools(rover_mcp)

if __name__ == "__main__":
    rover_mcp.run()