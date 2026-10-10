#!/usr/bin/env python3
"""Fetch current Rakuten Ichiba listings for selected PC parts and write prices.json.

Requires RAKUTEN_APP_ID and RAKUTEN_ACCESS_KEY environment variables.
Uses Rakuten's official Ichiba Item Search API. Prices are the cheapest matching
listing returned by the API, not a guarantee of the absolute market minimum.
"""
import json
import os
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

APP_ID = os.environ.get("RAKUTEN_APP_ID", "").strip()
ACCESS_KEY = os.environ.get("RAKUTEN_ACCESS_KEY", "").strip()
OUT = Path("prices.json")

QUERIES = [
    # CPUs
    "Ryzen 5 5500", "Ryzen 5 5600", "Ryzen 7 5700X", "Ryzen 7 5700X3D",
    "Ryzen 5 7500F", "Ryzen 5 7600", "Ryzen 7 7700", "Ryzen 7 7800X3D",
    "Ryzen 7 9700X", "Ryzen 7 9800X3D", "Ryzen 9 9900X", "Ryzen 9 9950X",
    "Core i3-12100F", "Core i5-12400F", "Core i5-13400F", "Core i5-14400F",
    "Core i7-14700F", "Core Ultra 5 245K", "Core Ultra 7 265K", "Core Ultra 9 285K",
    # GPUs
    "GeForce RTX 3050 6GB", "GeForce RTX 5050 8GB", "Radeon RX 6600 8GB",
    "Radeon RX 7600 8GB", "GeForce RTX 4060 8GB", "GeForce RTX 4060 Ti 8GB",
    "GeForce RTX 4060 Ti 16GB", "GeForce RTX 5060 8GB", "GeForce RTX 5060 Ti 8GB",
    "GeForce RTX 5060 Ti 16GB", "Radeon RX 9060 XT 8GB", "Radeon RX 9060 XT 16GB",
    "GeForce RTX 5070 12GB", "Radeon RX 9070 16GB", "Radeon RX 9070 XT 16GB",
    "GeForce RTX 5070 Ti 16GB", "GeForce RTX 5080 16GB", "GeForce RTX 5090 32GB",
]

def load_existing():
    if OUT.exists():
        try:
            return json.loads(OUT.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"source": "Rakuten Ichiba Item Search API", "status": "not_configured", "items": []}

def fetch(query):
    params = {
        "applicationId": APP_ID,
        "format": "json",
        "formatVersion": "2",
        "keyword": query,
        "sort": "+itemPrice",
        "hits": "10",
        "availability": "1",
        "field": "0",
        "imageFlag": "0",
    }
    url = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"accessKey": ACCESS_KEY, "User-Agent": "pc-shindan-price-bot/1.0"})
    with urllib.request.urlopen(req, timeout=25) as response:
        data = json.loads(response.read().decode("utf-8"))
    if data.get("error"):
        raise RuntimeError(f"Rakuten API error for {query}: {data.get('error_description', data['error'])}")
    items = data.get("Items", data.get("items", []))
    # formatVersion=2 normally returns flat item records; tolerate wrapped records too.
    records = []
    for entry in items:
        item = entry.get("Item", entry.get("item", entry))
        name = str(item.get("itemName") or "")
        price = item.get("itemPrice")
        link = item.get("itemUrl") or item.get("affiliateUrl") or ""
        shop = item.get("shopName") or ""
        if isinstance(price, int) and price > 0 and name and link.startswith("https://"):
            records.append({"name": name, "price": price, "url": link, "shop": shop})
    # Keep only plausible matches on the main model identifier to reduce accessories.
    model_tokens = [t.lower() for t in re.findall(r"[A-Za-z]+|\\d+[A-Za-z]*", query) if len(t) > 1]
    def score(row):
        title = row["name"].lower()
        return sum(1 for token in model_tokens if token in title)
    records = [row for row in records if score(row) >= max(2, len(model_tokens) // 2)]
    records.sort(key=lambda row: row["price"])
    return records[0] if records else None

def main():
    existing = load_existing()
    if not APP_ID or not ACCESS_KEY:
        print("Rakuten API credentials not configured. Add repository Actions secrets RAKUTEN_APP_ID and RAKUTEN_ACCESS_KEY.")
        # Do not overwrite existing working data when secrets are missing.
        if not OUT.exists():
            OUT.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    rows = []
    errors = []
    for index, query in enumerate(QUERIES):
        try:
            result = fetch(query)
            if result:
                rows.append({"query": query, **result})
            else:
                errors.append(query)
            print(f"[{index + 1}/{len(QUERIES)}] {query}: " + (f"¥{result['price']:,}" if result else "no matching listing"))
        except Exception as exc:
            errors.append(query)
            print(f"[{index + 1}/{len(QUERIES)}] {query}: ERROR {exc}")
        time.sleep(1.1)  # avoid hammering the API
    payload = {
        "source": "Rakuten Ichiba Item Search API",
        "status": "ok" if rows else "error",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "currency": "JPY",
        "priceNote": "Cheapest matching listing among returned Rakuten results; prices and stock may change. Not a guaranteed market-wide lowest price.",
        "items": rows,
        "queriesWithoutMatch": errors,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not rows:
        raise SystemExit("No price data fetched. Check API credentials and workflow logs.")

if __name__ == "__main__":
    main()
