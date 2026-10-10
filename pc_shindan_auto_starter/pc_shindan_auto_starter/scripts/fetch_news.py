#!/usr/bin/env python3
"""RSS feeds -> news.json. Uses only Python's standard library."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import json
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FEEDS_FILE = ROOT / "feeds.txt"
OUTPUT_FILE = ROOT / "news.json"
MAX_PER_FEED = 10
MAX_TOTAL = 30
USER_AGENT = "PCShindanRoomRSSBot/1.0 (personal project; contact: site owner)"

def text_of(element, names):
    for name in names:
        found = element.find(name)
        if found is not None and found.text:
            return found.text.strip()
    return ""

def clean_date(value):
    if not value:
        return ""
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return value[:10]

def read_feed(url, label):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as response:
        raw = response.read(2_000_000)
    root = ET.fromstring(raw)
    entries = []

    # RSS 2.0
    for item in root.findall(".//item"):
        title = text_of(item, ["title"])
        link = text_of(item, ["link"])
        date = clean_date(text_of(item, ["pubDate"]))
        if title and link.startswith(("https://", "http://")):
            entries.append({"title": title, "link": link, "date": date, "source": label})

    # Atom
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for item in root.findall(".//atom:entry", ns):
        title = text_of(item, ["{http://www.w3.org/2005/Atom}title"])
        published = text_of(item, ["{http://www.w3.org/2005/Atom}published",
                                   "{http://www.w3.org/2005/Atom}updated"])
        link = ""
        for link_el in item.findall("{http://www.w3.org/2005/Atom}link"):
            href = link_el.attrib.get("href", "")
            if href.startswith(("https://", "http://")):
                link = href
                break
        if title and link:
            entries.append({"title": title, "link": link,
                            "date": clean_date(published), "source": label})

    return entries[:MAX_PER_FEED]

def main():
    if not FEEDS_FILE.exists():
        raise SystemExit("feeds.txt がありません。ルートフォルダに作成してください。")
    feeds = []
    for line in FEEDS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" not in line:
            print(f"形式が違うためスキップ: {line}")
            continue
        label, url = [part.strip() for part in line.split("|", 1)]
        if url.startswith(("https://", "http://")):
            feeds.append((label or "PCニュース", url))
    if not feeds:
        raise SystemExit("feeds.txt にRSS/Atom URLがありません。README.mdの手順を確認してください。")

    all_items = []
    for label, url in feeds:
        try:
            items = read_feed(url, label)
            print(f"{label}: {len(items)}件")
            all_items.extend(items)
        except Exception as exc:
            print(f"取得失敗（{label}）: {exc}")

    # URLで重複を除外
    unique = {}
    for item in all_items:
        unique[item["link"]] = item
    articles = list(unique.values())
    articles.sort(key=lambda x: x.get("date", ""), reverse=True)
    articles = articles[:MAX_TOTAL]

    OUTPUT_FILE.write_text(json.dumps(articles, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(f"news.json を更新: {len(articles)}件")

if __name__ == "__main__":
    main()
