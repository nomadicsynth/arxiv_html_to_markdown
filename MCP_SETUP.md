# MCP Server Setup for HTML to Markdown Tool

This guide explains how to set up the HTML to Markdown converter as an MCP (Model Context Protocol) server that Cursor agents can use.

## Files

- `html_to_markdown.py` - The main converter script with convenience functions
- `mcp_html_to_markdown.py` - MCP server wrapper that exposes the converter as a tool

## Prerequisites

Set up the virtual environment and install dependencies:

```bash
cd mcp-servers
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

This will install `beautifulsoup4` and the official `mcp` Python SDK in the virtual environment.

## MCP Server Usage

The MCP server uses the official [MCP Python SDK](https://pypi.org/project/mcp/) and communicates via stdio. It exposes two tools:

### 1. `html_to_markdown_tool`
Converts HTML content string to Markdown.

**Parameters:**
- `html_content` (string, required): HTML content to convert

**Returns:** Markdown string

### 2. `html_file_to_markdown_tool`
Converts an HTML file to a Markdown file.

**Parameters:**
- `input_path` (string, required): Path to input HTML file
- `output_path` (string, optional): Path to output Markdown file (defaults to input_path with .md extension)

**Returns:** Success message with output file path

## Setting Up in Cursor

The exact method to register MCP servers in Cursor may vary by version. Here are common approaches:

### Option 1: Cursor Settings

1. Open Cursor Settings
2. Look for "MCP Servers", "Tools", or "Custom Tools" section
3. Add a new server configuration (use the venv's Python interpreter):
   ```json
   {
     "name": "html-to-markdown",
     "command": "/absolute/path/to/mcp-servers/.venv/bin/python",
     "args": ["/absolute/path/to/mcp-servers/mcp_html_to_markdown.py"],
     "env": {}
   }
   ```

### Option 2: Configuration File

Create or edit a Cursor configuration file (location varies by version):
- `~/.cursor/mcp.json`
- `~/.config/cursor/mcp.json`
- Or in your workspace `.cursor/` directory

Example configuration (using the venv's Python):
```json
{
  "mcpServers": {
    "html-to-markdown": {
      "command": "/absolute/path/to/mcp-servers/.venv/bin/python",
      "args": ["/absolute/path/to/mcp-servers/mcp_html_to_markdown.py"]
    }
  }
}
```

**Note:** Replace `/absolute/path/to/mcp-servers` with the actual absolute path to the `mcp-servers` directory.

### Option 3: Direct Import (Alternative)

If MCP setup is complex, you can also use the convenience functions directly in Python code:

```python
from html_to_markdown import html_to_markdown, html_file_to_markdown

# Convert HTML string
markdown = html_to_markdown(html_string)

# Convert HTML file
output_path = html_file_to_markdown("input.html", "output.md")
```

## Testing the MCP Server

You can test the MCP server manually (activate venv first):

```bash
cd mcp-servers
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# The server uses the official MCP SDK, so it handles protocol automatically
# You can test it with the MCP Inspector or by running it directly
python mcp_html_to_markdown.py
```

For more advanced testing, you can use the MCP Inspector:
```bash
npx -y @modelcontextprotocol/inspector
```

## Implementation Details

The server uses the official [MCP Python SDK](https://pypi.org/project/mcp/) with FastMCP, which:
- Handles all MCP protocol details automatically (JSON-RPC 2.0, initialization, etc.)
- Provides a clean decorator-based API for defining tools
- Supports stdio transport (default) for Cursor integration
- Automatically generates tool schemas from Python function signatures

All communication is via JSON over stdio (stdin/stdout), following the MCP specification.

## Notes

- The server runs in stdio mode (reads from stdin, writes to stdout) - this is the default for FastMCP
- **Important:** Use the venv's Python interpreter (`/path/to/mcp-servers/.venv/bin/python`) in your Cursor configuration to ensure dependencies are available
- The server requires `beautifulsoup4` and `mcp` to be installed (both included in requirements.txt)
- For file operations, ensure the script has read/write permissions
- Make sure to use absolute paths in your Cursor configuration
- The implementation uses the official MCP SDK, so protocol compliance is guaranteed

