#!/usr/bin/env python3
"""
MCP Server for arXiv LaTeXML-generated HTML to Markdown conversion tool.

This server exposes the html_to_markdown functionality as a tool
that AI agents can use via the Model Context Protocol (MCP).

Usage:
    # Stdio (default, for local MCP clients):
    python mcp_html_to_markdown.py

    # Streamable HTTP (for Open WebUI and other HTTP MCP clients):
    python mcp_html_to_markdown.py --transport streamable-http --host 0.0.0.0 --port 8000

Environment variables (optional overrides):
    MCP_TRANSPORT         "stdio" or "streamable-http"
    FASTMCP_HOST          Bind address for HTTP (default: 0.0.0.0 when using streamable-http)
    FASTMCP_PORT          Port for HTTP (default: 8000)
    FASTMCP_ALLOWED_HOSTS Comma-separated Host header values for streamable-http when binding
                          to 0.0.0.0 (e.g. "arxiv-mcp:*,localhost:*"). Required when binding
                          to all interfaces; otherwise requests will be rejected (421).
"""

import argparse
import os

from html_to_markdown import html_file_to_markdown, html_to_markdown
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# Create an MCP server
mcp = FastMCP("html-to-markdown")


@mcp.tool()
def html_to_markdown_tool(html_content: str) -> str:
    """Convert arXiv LaTeXML-generated HTML content to Markdown format.

    Handles document structure, sections, math equations, tables, figures, 
    citations, and references.

    Args:
        html_content: arXiv LaTeXML-generated HTML content to convert to Markdown

    Returns:
        The converted Markdown content
    """
    return html_to_markdown(html_content)


@mcp.tool()
def html_file_to_markdown_tool(input_path: str, output_path: str = "") -> str:
    """Convert an arXiv LaTeXML-generated HTML file to a Markdown file.

    Reads the HTML file, converts it, and writes the result to a Markdown file.

    Args:
        input_path: Path to the input HTML file
        output_path: Optional path to the output Markdown file. 
                     If not provided, uses input_path with .md extension.

    Returns:
        Success message with the output file path
    """
    if not output_path:
        result_path = html_file_to_markdown(input_path)
    else:
        result_path = html_file_to_markdown(input_path, output_path)

    return f"Successfully converted {input_path} to {result_path}"


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Run the arXiv HTML-to-Markdown MCP server (stdio or streamable-http)."
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        help="Transport: stdio (default) or streamable-http",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("FASTMCP_HOST", "127.0.0.1"),
        help="Host for streamable-http (default: 127.0.0.1, use 0.0.0.0 for containers)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("FASTMCP_PORT", "8000")),
        help="Port for streamable-http (default: 8000)",
    )
    return parser.parse_args()


def _transport_security_for_streamable_http(host: str) -> TransportSecuritySettings | None:
    """Build transport security for streamable-http. When binding to 0.0.0.0, requires
    FASTMCP_ALLOWED_HOSTS to be set; protection is never disabled by default.
    """
    raw = os.environ.get("FASTMCP_ALLOWED_HOSTS", "").strip()
    if raw:
        allowed_hosts = [s.strip() for s in raw.split(",") if s.strip()]
        # Origins for Origin header checks: http://host or http://host:*
        allowed_origins = [f"http://{h}" for h in allowed_hosts]
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed_hosts,
            allowed_origins=allowed_origins,
        )
    if host in ("0.0.0.0", "::"):
        raise SystemExit(
            "Binding to 0.0.0.0 requires FASTMCP_ALLOWED_HOSTS to be set (e.g. "
            'FASTMCP_ALLOWED_HOSTS="arxiv-mcp:*,localhost:*"). Refusing to start without it.'
        )
    return None  # leave default (localhost-only) when binding to 127.0.0.1 etc.


if __name__ == "__main__":
    args = _parse_args()
    if args.transport == "streamable-http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        security = _transport_security_for_streamable_http(args.host)
        if security is not None:
            mcp.settings.transport_security = security
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
