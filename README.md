# arXiv HTML to Markdown Converter

A Python tool for converting arXiv LaTeXML-generated HTML papers to clean Markdown format. Handles document structure, mathematical equations, tables, figures, citations, and references.

## Features

- **Document Structure**: Preserves title, authors, abstract, sections, and subsections
- **Mathematical Equations**: Converts MathML to LaTeX format (inline and display math)
- **Tables**: Converts HTML tables to Markdown table format
- **Figures**: Extracts figure captions and image references
- **Citations**: Processes citation references
- **Algorithms/Listings**: Converts code listings and algorithms
- **References**: Extracts bibliography entries
- **Text Formatting**: Preserves bold, italic, and code formatting

## Installation

### Prerequisites

- Python 3.7 or higher
- pip

### Setup

1. Clone or download this repository:
   ```bash
   cd arxiv_html_to_markdown
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

   This installs:
   - `beautifulsoup4` - HTML parsing
   - `mcp[cli]` - MCP server support (optional, for AI agent integration)

## Usage

### Standalone Script

Convert an HTML file to Markdown:

```bash
python html_to_markdown.py input.html [output.md]
```

If `output.md` is not specified, the output file will be `input.md` (same name with `.md` extension).

**Example:**
```bash
python html_to_markdown.py paper.html paper.md
```

### Python API

Use the converter programmatically:

```python
from html_to_markdown import html_to_markdown, html_file_to_markdown

# Convert HTML string to Markdown
html_content = "<html>...</html>"
markdown = html_to_markdown(html_content)
print(markdown)

# Convert HTML file to Markdown file
output_path = html_file_to_markdown("input.html", "output.md")
print(f"Converted to: {output_path}")
```

### MCP Server (for AI Agents)

The tool can be used as an MCP (Model Context Protocol) server for AI agents like Cursor.

#### Setup

1. Create a virtual environment (recommended):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Configure your MCP client (e.g., Cursor) to use the server. See [MCP_SETUP.md](MCP_SETUP.md) for detailed instructions.

#### MCP Tools

The server exposes two tools:

1. **`html_to_markdown_tool`**: Converts HTML content string to Markdown
   - Parameter: `html_content` (string) - HTML content to convert
   - Returns: Markdown string

2. **`html_file_to_markdown_tool`**: Converts an HTML file to a Markdown file
   - Parameters:
     - `input_path` (string) - Path to input HTML file
     - `output_path` (string, optional) - Path to output Markdown file
   - Returns: Success message with output file path

## How It Works

The converter uses BeautifulSoup to parse the HTML and extracts:

- **Title and Metadata**: From `<title>` and author/abstract sections
- **Sections**: Recursively processes sections and subsections with proper heading levels
- **Math**: Extracts LaTeX from MathML `<annotation>` elements or `alttext` attributes
- **Tables**: Converts HTML tables to Markdown pipe-separated format
- **Figures**: Extracts captions and image references
- **Citations**: Processes citation references and formats them
- **References**: Extracts bibliography items

The output is cleaned and formatted for readability, with proper spacing and Markdown syntax.

## Example Output

Input HTML (arXiv LaTeXML format) is converted to clean Markdown:

```markdown
# Paper Title

**Authors:** Author One, Author Two

## Abstract

This is the abstract text with inline math $x = y$ and display math:

$$
E = mc^2
$$

## Introduction

The introduction text...

**Figure 1:** Caption text
![Figure](figure.png)

| Column 1 | Column 2 |
| --- | --- |
| Data 1 | Data 2 |
```

## Requirements

- Python 3.7+
- beautifulsoup4
- mcp[cli] (optional, for MCP server functionality)

## Files

- `html_to_markdown.py` - Main converter script with standalone and API functionality
- `mcp_html_to_markdown.py` - MCP server wrapper for AI agent integration
- `requirements.txt` - Python dependencies
- `MCP_SETUP.md` - Detailed MCP server setup instructions

## License

This tool is provided as-is for converting arXiv HTML papers to Markdown format.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

