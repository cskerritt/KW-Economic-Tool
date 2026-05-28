"""MCP server exposing the calculation engine to Claude Code.

Uses the same shared compute path (app.compute) as the web app, so the numbers
the MCP returns match the UI exactly. Requires the optional 'mcp' dependency:
    pip install -e ".[mcp]"
Run:  python -m mcp_server.server
"""
