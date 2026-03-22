#!/usr/bin/env python3
"""
QuantPlace MCP Server

Allows AI agents (Cursor, Claude Desktop, Windsurf, Claude Code) to search,
inspect, and preview trading datasets from QuantPlace without leaving the IDE.

Tools (public):
  search_datasets       — Find datasets by title, category, tags, price
  get_dataset_metadata  — Column names, row count, stats, description
  get_preview_sample    — 50-row preview as a markdown table
  get_vendor_profile    — Seller rating, bio, active listings

Tools (require API key):
  get_my_purchases      — List purchased datasets for the authenticated user
  get_download_url      — Get a 15-min presigned download URL for a purchased dataset

Usage:
  python server.py
  QUANTPLACE_API_URL=http://localhost:8000/api/v1 python server.py
"""

import csv
import io
import os

import httpx
from fastmcp import FastMCP

API_BASE = os.getenv(
    "QUANTPLACE_API_URL", "https://api.quantplace.io/api/v1"
).rstrip("/")

mcp = FastMCP(
    "QuantPlace",
    instructions=(
        "Use this server to find, evaluate, preview, and download trading datasets on QuantPlace. "
        "Public flow (no auth): search_datasets → get_dataset_metadata → get_preview_sample → get_vendor_profile. "
        "Authenticated flow (requires API key from quantplace.io/mcp): get_my_purchases → get_download_url. "
        "All tools are read-only — no purchases are made automatically."
    ),
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get(path: str, params: dict | None = None) -> dict | list:
    clean_params = {k: v for k, v in (params or {}).items() if v is not None}
    with httpx.Client(timeout=30) as client:
        resp = client.get(f"{API_BASE}{path}", params=clean_params)
        resp.raise_for_status()
        return resp.json()


def _get_authed(path: str, api_key: str) -> dict | list:
    with httpx.Client(timeout=30) as client:
        resp = client.get(f"{API_BASE}{path}", headers={"X-API-Key": api_key})
        resp.raise_for_status()
        return resp.json()


def _fetch_text(url: str) -> str:
    with httpx.Client(timeout=30) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def _csv_to_markdown(text: str, max_rows: int = 50) -> str:
    reader = csv.reader(io.StringIO(text.strip()))
    rows = list(reader)
    if not rows:
        return "_No data_"
    headers = rows[0]
    data_rows = rows[1 : max_rows + 1]
    col_count = len(headers)
    sep = " | ".join(["---"] * col_count)
    lines = [" | ".join(headers), sep]
    for row in data_rows:
        padded = (row + [""] * col_count)[:col_count]
        lines.append(" | ".join(str(v) for v in padded))
    return "\n".join(lines)


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def search_datasets(
    query: str = "",
    category: str = "",
    tags: str = "",
    max_price: float = 0.0,
    limit: int = 20,
) -> str:
    """
    Search QuantPlace for trading datasets.

    Args:
        query:     Text to match against dataset titles (case-insensitive).
        category:  Filter by category. One of: orderbook_l2, orderbook_l3,
                   labeled_data, strategy_log, ohlcv, other.
        tags:      Comma-separated tags. Dataset must match ALL supplied tags.
                   Example: "BTC,binance,1m"
        max_price: Maximum price in USD. 0 = no limit.
        limit:     Number of results to return (1–60).

    Returns:
        A formatted list of matching datasets with key statistics.
    """
    raw: list = _get("/datasets/", {"skip": 0, "limit": min(max(1, limit), 60)})

    datasets = raw
    if query:
        q = query.lower()
        datasets = [d for d in datasets if q in d.get("title", "").lower()]
    if category:
        datasets = [d for d in datasets if d.get("category") == category]
    if tags:
        tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]
        datasets = [
            d for d in datasets
            if all(t in [x.lower() for x in (d.get("tags") or [])] for t in tag_list)
        ]
    if max_price > 0:
        datasets = [d for d in datasets if float(d.get("price", 0)) <= max_price]

    if not datasets:
        return "No datasets found matching your criteria. Try broadening your search."

    lines = [f"Found **{len(datasets)}** dataset(s) on QuantPlace:\n"]
    for d in datasets:
        price = float(d.get("price", 0))
        rating = float(d.get("avg_rating", 0))
        reviews = d.get("review_count", 0)
        sales = d.get("total_sales", 0)
        views = d.get("views", 0)
        tags_str = ", ".join(d.get("tags") or []) or "none"
        lines.append(
            f"### {d['title']}\n"
            f"- **ID:** `{d['id']}`\n"
            f"- **Category:** {d.get('category', 'unknown')}\n"
            f"- **Price:** ${price:.2f}\n"
            f"- **Rating:** {rating:.1f}/5.0 ({reviews} review{'s' if reviews != 1 else ''})\n"
            f"- **Sales:** {sales}  |  **Views:** {views}\n"
            f"- **Tags:** {tags_str}\n"
        )
    return "\n".join(lines)


@mcp.tool()
def get_dataset_metadata(dataset_id: str) -> str:
    """
    Retrieve full metadata for a dataset: title, description, category, price,
    column names (extracted from the preview CSV), row count, and vendor info.

    Args:
        dataset_id: The UUID of the dataset (from search_datasets results).

    Returns:
        Structured metadata. Use get_preview_sample to see actual data rows.
    """
    try:
        dataset = _get(f"/datasets/{dataset_id}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"Dataset `{dataset_id}` not found."
        raise

    # Extract column names from the preview CSV (public endpoint)
    columns_info = "_(preview not available)_"
    row_count_str = ""
    try:
        preview_meta = _get(f"/datasets/{dataset_id}/preview")
        preview_url = preview_meta.get("preview_url", "")
        if preview_url:
            csv_text = _fetch_text(preview_url)
            reader = csv.reader(io.StringIO(csv_text.strip()))
            headers = next(reader, [])
            data_rows = list(reader)
            columns_info = (
                ", ".join(f"`{h}`" for h in headers) if headers else "_(none found)_"
            )
            row_count_str = f"\n- **Preview rows available:** {len(data_rows)}"
    except Exception:
        pass

    price = float(dataset.get("price", 0))
    rating = float(dataset.get("avg_rating", 0))
    created = (dataset.get("created_at") or "")[:10] or "unknown"
    description = dataset.get("description") or "_No description provided._"
    tags_str = ", ".join(dataset.get("tags") or []) or "none"
    vendor_id = dataset.get("vendor_id", "")

    return "\n".join([
        f"## {dataset['title']}",
        "",
        f"**ID:** `{dataset['id']}`  ",
        f"**Category:** {dataset.get('category', 'unknown')}  ",
        f"**Price:** ${price:.2f} (one-time purchase, lifetime access)  ",
        f"**Rating:** {rating:.1f}/5.0 ({dataset.get('review_count', 0)} reviews)  ",
        f"**Total sales:** {dataset.get('total_sales', 0)}  ",
        f"**Views:** {dataset.get('views', 0)}  ",
        f"**Listed:** {created}  ",
        f"**Tags:** {tags_str}",
        "",
        "### Description",
        description,
        "",
        "### Data Schema",
        f"- **Columns:** {columns_info}{row_count_str}",
        "",
        "### Vendor",
        (
            f"Vendor ID: `{vendor_id}`  \n"
            "Use `get_vendor_profile` with this ID to see seller rating, bio, and listings."
        ),
    ])


@mcp.tool()
def get_preview_sample(dataset_id: str) -> str:
    """
    Fetch the 50-row preview sample for a dataset and return it as a markdown table.

    Use this to inspect real data structure and values before recommending a purchase.
    The preview is auto-generated from the validated dataset file.

    Args:
        dataset_id: The UUID of the dataset (from search_datasets results).

    Returns:
        A markdown table containing up to 50 rows of sample data.
    """
    try:
        preview_meta = _get(f"/datasets/{dataset_id}/preview")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return "Preview not available for this dataset."
        raise

    preview_url = preview_meta.get("preview_url", "")
    if not preview_url:
        return "Preview URL not available."

    csv_text = _fetch_text(preview_url)
    if not csv_text.strip():
        return "Preview file is empty."

    table = _csv_to_markdown(csv_text)
    expires = preview_meta.get("expires_in_seconds", 900)

    return (
        f"## Preview Sample — `{dataset_id}`\n\n"
        f"{table}\n\n"
        f"_Preview URL expires in {expires // 60} minutes. "
        f"Purchase the full dataset for complete access with buyer-specific watermarking._"
    )


@mcp.tool()
def get_vendor_profile(vendor_id: str) -> str:
    """
    Retrieve a vendor's public profile: rating, review count, bio, and active listings.

    Use this to surface trust signals when recommending a dataset. A vendor's
    rating is calculated from verified buyer reviews only.

    Args:
        vendor_id: The UUID of the vendor (available in dataset metadata).

    Returns:
        Vendor profile summary with rating, bio, and up to 6 active listings.
    """
    try:
        profile = _get(f"/users/{vendor_id}/profile")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return "Vendor profile not found."
        raise

    nickname = profile.get("nickname") or "Anonymous"
    rating = float(profile.get("vendor_rating", 0))
    reviews = profile.get("review_count", 0)
    bio = profile.get("bio") or "_No bio provided._"
    created = (profile.get("created_at") or "")[:10] or "unknown"
    sales = profile.get("total_sales_count", 0)
    active_datasets = profile.get("active_datasets", [])

    listings_lines = []
    for ds in active_datasets:
        ds_price = float(ds.get("price", 0))
        ds_rating = float(ds.get("avg_rating", 0))
        listings_lines.append(
            f"  - **{ds['title']}** — ${ds_price:.2f} "
            f"(★ {ds_rating:.1f}, {ds.get('total_sales', 0)} sales) "
            f"[`{ds['id']}`]"
        )

    listings_str = (
        "\n".join(listings_lines)
        if listings_lines
        else "  _No active listings._"
    )

    return "\n".join([
        f"## {nickname}",
        "",
        f"- **Rating:** {rating:.1f}/5.0 ({reviews} verified review{'s' if reviews != 1 else ''})",
        f"- **Total sales:** {sales}",
        f"- **Active listings:** {len(active_datasets)}",
        f"- **Member since:** {created}",
        "",
        "### Bio",
        bio,
        "",
        "### Active Datasets",
        listings_str,
    ])


@mcp.tool()
def get_my_purchases(api_key: str) -> str:
    """
    List all datasets purchased by the authenticated user.

    Requires a QuantPlace API key (generate one at /mcp → API Key Management,
    available to all registered users).

    Args:
        api_key: Your QuantPlace API key (X-API-Key).

    Returns:
        A list of your purchases with status, amount, and dataset info.
    """
    try:
        purchases: list = _get_authed("/transactions/purchases", api_key)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return "Invalid API key. Generate one at quantplace.io/mcp → API Key Management."
        raise

    if not purchases:
        return "No purchases found for this account."

    lines = [f"Found **{len(purchases)}** purchase(s):\n"]
    for p in purchases:
        status = p.get("status", "unknown")
        amount = float(p.get("amount", 0))
        escrow = p.get("escrow_release_at", "")
        escrow_str = f"  — escrow releases {escrow[:10]}" if escrow and status == "held" else ""
        lines.append(
            f"### {p.get('dataset_title', 'Unknown dataset')}\n"
            f"- **Dataset ID:** `{p.get('dataset_id')}`\n"
            f"- **Transaction ID:** `{p.get('id')}`\n"
            f"- **Amount paid:** ${amount:.2f}\n"
            f"- **Status:** {status}{escrow_str}\n"
            f"- **Has review:** {'Yes' if p.get('has_review') else 'No'}\n"
            f"- **Purchased:** {(p.get('created_at') or '')[:10]}\n"
        )
    return "\n".join(lines)


@mcp.tool()
def get_download_url(api_key: str, dataset_id: str) -> str:
    """
    Get a presigned download URL for a purchased dataset.

    The URL is valid for 15 minutes and points to your watermarked copy of the archive.
    If the watermark is still being applied (usually within minutes of purchase),
    this will return a "preparing" status — retry after 30 seconds.

    Requires a QuantPlace API key and a completed or held purchase for the dataset.

    Args:
        api_key:    Your QuantPlace API key (X-API-Key).
        dataset_id: The UUID of the dataset to download.

    Returns:
        A presigned download URL or a "preparing" status with retry guidance.
    """
    try:
        result: dict = _get_authed(f"/datasets/{dataset_id}/download", api_key)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            return "Invalid API key. Generate one at quantplace.io/mcp → API Key Management."
        if e.response.status_code == 403:
            return f"No completed purchase found for dataset `{dataset_id}`. Purchase it first at quantplace.io/datasets/{dataset_id}."
        raise

    if result.get("status") == "preparing":
        return (
            f"Your watermarked copy of dataset `{dataset_id}` is still being prepared. "
            f"Retry in {result.get('retry_after', 30)} seconds."
        )

    url = result.get("download_url", "")
    expires = result.get("expires_in_seconds", 900)
    return (
        f"## Download Ready\n\n"
        f"**Dataset:** `{dataset_id}`  \n"
        f"**URL:** {url}  \n"
        f"**Expires in:** {expires // 60} minutes\n\n"
        f"Download your file:\n"
        f"```bash\ncurl -L \"{url}\" -o dataset.zip\n```"
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
