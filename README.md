# QuantPlace MCP Server

A lightweight [Model Context Protocol](https://modelcontextprotocol.io) server that lets AI agents search, inspect, and preview trading datasets from [QuantPlace](https://quantplace.org) without leaving the IDE.

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
**Authenticated tools** require a QuantPlace API key (generate one at [quantplace.org/mcp](https://quantplace.org/mcp) → API Key Management).

There are two ways to supply the key:

- **Recommended:** set the `QUANTPLACE_API_KEY` environment variable in your IDE config. The tools will use it automatically with no argument needed.
- **Per-call:** pass `api_key="your_key"` directly when calling the tool. Useful when an agent already has the key in context.

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
        "QUANTPLACE_API_KEY": "your_key_here"
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
        "QUANTPLACE_API_KEY": "your_key_here"
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
        "QUANTPLACE_API_KEY": "your_key_here"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add quantplace -e QUANTPLACE_API_KEY=your_key_here -- python /absolute/path/to/server.py
```

Leave out `-e QUANTPLACE_API_KEY=...` if you only need the public tools.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `QUANTPLACE_API_KEY` | *(none)* | Your QuantPlace API key. Required for authenticated tools. |
| `QUANTPLACE_API_URL` | `https://api.quantplace.org/api/v1` | Override to point at a local dev server. |

## Example agent workflows

### Discovery (no auth required)

```
User: Find a BTC order book dataset under $50

Agent:
1. search_datasets(query="BTC", category="orderbook_l2", max_price=50)
   -> Returns list of matching datasets with IDs

2. get_dataset_metadata(dataset_id="<id>")
   -> Columns: `timestamp`, `bid_price`, `bid_size`, `ask_price`, `ask_size`

3. get_preview_sample(dataset_id="<id>")
   -> Renders full markdown table so the agent can analyze structure

4. get_vendor_profile(vendor_id="<vendor_id>")
   -> Rating: 4.8/5.0 (23 reviews), member since 2025-11
```

### Download a purchased dataset (requires API key)

```
User: Download the BTC dataset I bought

Agent (QUANTPLACE_API_KEY set in env):
1. get_my_purchases()
   -> Lists purchases with dataset_id, status, escrow dates

2. get_download_url(dataset_id="<id>")
   -> Returns presigned URL + curl command (valid 15 min)
```

If the key is not in the environment, the agent can ask the user for it and pass it directly:

```
Agent:
1. get_my_purchases(api_key="<user-provided-key>")
2. get_download_url(dataset_id="<id>", api_key="<user-provided-key>")
```

## Architecture

The server is a thin wrapper over QuantPlace's public REST API. It runs as a local subprocess communicating over `stdio` — the standard MCP transport used by all major IDE clients. If the server goes down or the API is unreachable, only MCP tool calls fail; the core platform is completely unaffected.

## License

MIT
