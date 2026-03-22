# QuantPlace MCP Server

A lightweight [Model Context Protocol](https://modelcontextprotocol.io) server that lets AI agents search, inspect, and preview trading datasets from [QuantPlace](https://quantplace.io) without leaving the IDE.

## What it does

AI agents can call six tools — four public, two authenticated:

| Tool | Auth | Description |
|---|---|---|
| `search_datasets` | — | Search by title, category, tags, and price |
| `get_dataset_metadata` | — | Column names, row count, description, vendor info |
| `get_preview_sample` | — | 50-row preview rendered as a markdown table |
| `get_vendor_profile` | — | Seller rating, bio, and active listings |
| `get_my_purchases` | API key | List all datasets you have purchased |
| `get_download_url` | API key | Get a 15-min presigned download URL for a purchased dataset |

No purchases are ever made automatically.

**Public tools** wrap QuantPlace's open REST endpoints — no account needed.
**Authenticated tools** require a QuantPlace API key (generate one at [quantplace.io/mcp](https://quantplace.io/mcp) → API Key Management). Pass it as the `api_key` argument when calling the tool.

## Installation

```bash
git clone https://github.com/KuroskeNB/quantplace-mcp
cd quantplace-mcp
pip install -r requirements.txt
```

Or with `uv`:

```bash
uv pip install fastmcp httpx
```

## Configuration

Set the API URL via environment variable (defaults to the production API):

```bash
export QUANTPLACE_API_URL=https://api.quantplace.io/api/v1
# For local development:
export QUANTPLACE_API_URL=http://localhost:8000/api/v1
```

## IDE Setup

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS)
or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "quantplace": {
      "command": "python",
      "args": ["/absolute/path/to/server.py"],
      "env": {
        "QUANTPLACE_API_URL": "https://api.quantplace.io/api/v1"
      }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json` in your project root, or `~/.cursor/mcp.json` globally:

```json
{
  "mcpServers": {
    "quantplace": {
      "command": "python",
      "args": ["/absolute/path/to/server.py"],
      "env": {
        "QUANTPLACE_API_URL": "https://api.quantplace.io/api/v1"
      }
    }
  }
}
```

### Windsurf

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "quantplace": {
      "command": "python",
      "args": ["/absolute/path/to/server.py"],
      "env": {
        "QUANTPLACE_API_URL": "https://api.quantplace.io/api/v1"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add quantplace -- python /absolute/path/to/server.py
```

Or to set the API URL:

```bash
claude mcp add quantplace -e QUANTPLACE_API_URL=https://api.quantplace.io/api/v1 -- python /absolute/path/to/server.py
```

## Example agent workflows

### Discovery (no auth required)

```
User: Find a BTC order book dataset under $50

Agent:
1. search_datasets(query="BTC", category="orderbook_l2", max_price=50)
   → Returns list of matching datasets with IDs

2. get_dataset_metadata(dataset_id="<id>")
   → Columns: `timestamp`, `bid_price`, `bid_size`, `ask_price`, `ask_size`
   → 50-row preview available

3. get_preview_sample(dataset_id="<id>")
   → Renders full markdown table so the agent can analyze structure
   → Agent generates a ready-to-use parsing script for the buyer

4. get_vendor_profile(vendor_id="<vendor_id>")
   → Rating: 4.8/5.0 (23 reviews), member since 2025-11
   → Agent surfaces trust signals alongside recommendation
```

### Download a purchased dataset (requires API key)

```
User: Download the BTC dataset I bought

Agent:
1. get_my_purchases(api_key="<your-key>")
   → Lists purchases with dataset_id, status, escrow dates

2. get_download_url(api_key="<your-key>", dataset_id="<id>")
   → Returns presigned URL + curl command (valid 15 min)
   → Claude Code can run the curl command directly via Bash
```

## Architecture

The server is a thin wrapper over QuantPlace's public REST API. It runs as a local subprocess communicating over `stdio` — the standard MCP transport used by all major IDE clients. If the server goes down or the API is unreachable, only MCP tool calls fail; the core platform is completely unaffected.

## License

MIT
