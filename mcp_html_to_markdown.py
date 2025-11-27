#!/usr/bin/env python3
"""
MCP Server for arXiv LaTeXML-generated HTML to Markdown conversion tool.

This server exposes the html_to_markdown functionality as a tool
that AI agents can use via the Model Context Protocol (MCP).

Usage:
    python mcp_html_to_markdown.py
    
The server uses the official MCP Python SDK and communicates via stdio.
"""

import sys
from pathlib import Path

from html_to_markdown import html_file_to_markdown, html_to_markdown
from mcp.server.fastmcp import FastMCP

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


if __name__ == "__main__":
    # Run with stdio transport (default for MCP servers)
    mcp.run()
