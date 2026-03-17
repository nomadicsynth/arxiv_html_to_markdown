# arXiv HTML-to-Markdown MCP server (Streamable HTTP for Open WebUI etc.)
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY html_to_markdown.py mcp_html_to_markdown.py ./

# Defaults for container: bind all interfaces, port 8000
ENV MCP_TRANSPORT=streamable-http
ENV FASTMCP_HOST=0.0.0.0
ENV FASTMCP_PORT=8000

EXPOSE 8000

# Run with streamable-http so HTTP MCP clients (e.g. Open WebUI) can connect
CMD ["python", "mcp_html_to_markdown.py", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
