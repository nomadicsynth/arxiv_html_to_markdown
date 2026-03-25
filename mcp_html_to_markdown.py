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
import re
import os
import json
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from html_to_markdown import html_file_to_markdown, html_to_markdown
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# arXiv HTML base URL; only this domain/path is allowed for fetching
ARXIV_HTML_BASE = "https://arxiv.org/html"
# arXiv ID: YYMM.NNNNN or YYMM.NNNNNvN
ARXIV_ID_PATTERN = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
FETCH_TIMEOUT_SECONDS = 60
USER_AGENT = "nomadicsynth-arXiv-html-to-markdown-tool/1.0 (+https://github.com/nomadicsynth/arxiv_html_to_markdown)"

ARXIV_EXPORT_API_BASE = "https://export.arxiv.org/api/query"


@dataclass(frozen=True)
class _ArxivRequest:
    base_id: str
    version: int | None  # None => "latest"

    @property
    def id_for_fetch(self) -> str:
        return self.base_id if self.version is None else f"{self.base_id}v{self.version}"


def _cache_dir() -> Path:
    override = os.environ.get("ARXIV_MCP_CACHE_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME", "").strip()
    if xdg:
        return Path(xdg).expanduser() / "arxiv_html_to_markdown"
    return Path.home() / ".cache" / "arxiv_html_to_markdown"


def _cache_key(req: _ArxivRequest) -> str:
    return f"{req.base_id}__latest" if req.version is None else f"{req.base_id}v{req.version}"


def _cache_paths(req: _ArxivRequest) -> tuple[Path, Path]:
    d = _cache_dir()
    key = _cache_key(req)
    return d / f"{key}.json", d / f"{key}.md"


def _cache_read(req: _ArxivRequest) -> tuple[dict, str] | None:
    meta_path, md_path = _cache_paths(req)
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        md = md_path.read_text(encoding="utf-8")
        return meta, md
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _cache_write(req: _ArxivRequest, meta: dict, markdown: str) -> None:
    meta_path, md_path = _cache_paths(req)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(markdown, encoding="utf-8")
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_arxiv_request(arxiv_id_or_url: str) -> _ArxivRequest:
    s = arxiv_id_or_url.strip()
    if not s:
        raise ValueError("Empty arXiv ID or URL")

    parsed = urlparse(s)
    if parsed.scheme and parsed.netloc:
        netloc = parsed.netloc.lower().lstrip("www.")
        if netloc != "arxiv.org":
            raise ValueError("Only arXiv URLs are allowed (arxiv.org)")
        if parsed.path.startswith("/html/"):
            id_part = parsed.path[6:].strip("/").split("/")[0]
        elif parsed.path.startswith("/abs/"):
            id_part = parsed.path[5:].strip("/").split("/")[0]
        elif parsed.path.startswith("/pdf/"):
            id_part = parsed.path[5:].strip("/").split("/")[0]
        else:
            raise ValueError(
                "Only arXiv HTML, abstract or pdf URLs are allowed (/html/... or /abs/... or /pdf/...)"
            )
    else:
        id_part = s

    m = re.match(r"^(?P<base>\d{4}\.\d{4,5})(?:v(?P<v>\d+))?$", id_part)
    if not m:
        raise ValueError(
            "Invalid arXiv ID format (expected e.g. 2512.05397 or 2512.05397v2)"
        )
    base = m.group("base")
    v = m.group("v")
    return _ArxivRequest(base_id=base, version=int(v) if v is not None else None)


def _fetch_arxiv_export_atom_for_id(base_id: str) -> str:
    url = f"{ARXIV_EXPORT_API_BASE}?id_list={base_id}&max_results=1"
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        raise ValueError(f"arXiv export API returned HTTP {e.code}: {e.reason}") from e
    except URLError as e:
        raise ValueError(f"Failed to fetch arXiv export API: {e.reason}") from e


def _latest_version_info(base_id: str) -> tuple[int, str | None]:
    atom_xml = _fetch_arxiv_export_atom_for_id(base_id)
    try:
        root = ElementTree.fromstring(atom_xml)
    except ElementTree.ParseError as e:
        raise ValueError("Failed to parse arXiv export API response") from e

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", ns)
    if entry is None:
        raise ValueError("No entry found in arXiv export API response")

    updated_el = entry.find("atom:updated", ns)
    updated = updated_el.text.strip() if (updated_el is not None and updated_el.text) else None

    version: int | None = None
    for link in entry.findall("atom:link", ns):
        if link.attrib.get("rel") != "alternate":
            continue
        href = link.attrib.get("href", "")
        m = re.search(r"/abs/(?P<id>\d{4}\.\d{4,5})v(?P<v>\d+)$", href)
        if m and m.group("id") == base_id:
            version = int(m.group("v"))
            break

    if version is None:
        summary_el = entry.find("atom:summary", ns)
        summary = summary_el.text or ""
        m = re.search(rf"\barXiv:{re.escape(base_id)}v(?P<v>\d+)\b", summary)
        if m:
            version = int(m.group("v"))

    if version is None:
        version = 1

    return version, updated


def _normalize_arxiv_html_url(arxiv_id_or_url: str) -> str:
    """Return canonical arXiv HTML URL from an ID or an arxiv.org URL.

    Accepts:
    - Bare ID: 2512.05397, 2512.05397v2
    - HTML URL: https://arxiv.org/html/2512.05397v2
    - Abstract URL: https://arxiv.org/abs/2512.05397 (normalized to HTML URL)
    - PDF URL: https://arxiv.org/pdf/2512.05397v2.pdf (normalized to HTML URL)

    Only arxiv.org is allowed. /abs/ and /pdf/ URLs are normalized to /html/.
    """
    s = arxiv_id_or_url.strip()
    if not s:
        raise ValueError("Empty arXiv ID or URL")
    parsed = urlparse(s)
    if parsed.scheme and parsed.netloc:
        netloc = parsed.netloc.lower().lstrip("www.")
        if netloc != "arxiv.org":
            raise ValueError("Only arXiv URLs are allowed (arxiv.org)")
        if parsed.path.startswith("/html/"):
            id_part = parsed.path[6:].strip("/").split("/")[0]
        elif parsed.path.startswith("/abs/"):
            id_part = parsed.path[5:].strip("/").split("/")[0]
        elif parsed.path.startswith("/pdf/"):
            id_part = parsed.path[5:].strip("/").split("/")[0]
        else:
            raise ValueError(
                "Only arXiv HTML or abstract or pdf URLs are allowed (/html/... or /abs/... or /pdf/...)"
            )
        if not id_part or not ARXIV_ID_PATTERN.match(id_part):
            raise ValueError("Invalid arXiv ID in URL path")
        return f"{ARXIV_HTML_BASE}/{id_part}"
    if not ARXIV_ID_PATTERN.match(s):
        raise ValueError(
            "Invalid arXiv ID format (expected e.g. 2512.05397 or 2512.05397v2)"
        )
    return f"{ARXIV_HTML_BASE}/{s}"


def _fetch_arxiv_html(url: str) -> str:
    """Download HTML from a validated arXiv URL. Raises on error."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=FETCH_TIMEOUT_SECONDS) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        raise ValueError(f"arXiv returned HTTP {e.code}: {e.reason}") from e
    except URLError as e:
        raise ValueError(f"Failed to fetch arXiv URL: {e.reason}") from e


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


@mcp.tool()
def arxiv_html_to_markdown(arxiv_id_or_url: str) -> str:
    """Fetch an arXiv paper from its ID or URL and convert the HTML version to Markdown.
    Use whenever you are given an arXiv paper URL to retrieve the paper and convert it to Markdown.

    Accepts either an arXiv paper ID or a full arXiv URL. Then converts
    the LaTeXML-generated HTML to Markdown.

    Args:
        arxiv_id_or_url: arXiv paper ID (e.g. 2512.05397v2) or full URL, e.g.:
            - https://arxiv.org/html/2512.05397v2
            - https://arxiv.org/abs/2512.05397 (will fetch HTML version)
            - https://arxiv.org/pdf/2512.05397v2.pdf (will fetch HTML version)

    Returns:
        The converted Markdown content

    Raises:
        ValueError: If the input is not a valid arXiv ID/URL or fetch fails.
    """
    req = _parse_arxiv_request(arxiv_id_or_url)

    validate_latest = os.environ.get("ARXIV_MCP_CACHE_VALIDATE_LATEST", "1").strip().lower() not in (
        "",
        "0",
        "false",
        "no",
    )

    # Explicit versions are immutable: if present in cache, return without any network calls.
    if req.version is not None:
        cached = _cache_read(req)
        if cached is not None:
            _meta, md = cached
            return md

        url = _normalize_arxiv_html_url(req.id_for_fetch)
        html_content = _fetch_arxiv_html(url)
        md = html_to_markdown(html_content)
        _cache_write(
            req,
            meta={
                "base_id": req.base_id,
                "version": req.version,
                "requested": arxiv_id_or_url,
                "fetched_at_unix": int(time.time()),
            },
            markdown=md,
        )
        return md

    # Latest-version requests: validate against export API to see if a newer version exists.
    cached_latest = _cache_read(req)
    if cached_latest is not None and validate_latest:
        meta, md = cached_latest
        try:
            latest_v, latest_updated = _latest_version_info(req.base_id)
            cached_v = meta.get("latest_version")
            cached_updated = meta.get("latest_updated")
            if isinstance(cached_v, int) and cached_v == latest_v:
                if latest_updated is None or cached_updated is None or cached_updated == latest_updated:
                    return md
        except Exception:
            # If we can't validate (network, parse, etc.), fall back to cached content.
            return md

    latest_v: int | None = None
    latest_updated: str | None = None
    if validate_latest:
        try:
            latest_v, latest_updated = _latest_version_info(req.base_id)
        except Exception:
            latest_v = None
            latest_updated = None

    fetch_id = req.base_id if latest_v is None else f"{req.base_id}v{latest_v}"
    url = _normalize_arxiv_html_url(fetch_id)
    html_content = _fetch_arxiv_html(url)
    md = html_to_markdown(html_content)
    _cache_write(
        req,
        meta={
            "base_id": req.base_id,
            "requested": arxiv_id_or_url,
            "latest_version": latest_v,
            "latest_updated": latest_updated,
            "fetched_at_unix": int(time.time()),
        },
        markdown=md,
    )
    return md


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
