#!/usr/bin/env python3
"""Fetch public RSS/Atom feeds and publish a small, deduplicated news.json."""
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEEDS = ROOT / "feeds.txt"
OUTPUT = ROOT / "news.json"
MAX_PER_FEED = 25
MAX_TOTAL = 100
USER_AGENT = "PCShindanRSSBot/1.0 (public RSS reader)"

def clean(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()

def child_text(el, names):
    for child in list(el):
        tag = child.tag.rsplit("}", 1)[-1].lower()
        if tag in names:
            if tag == "link" and child.attrib.get("href"):
                return child.attrib["href"].strip()
            return "".join(child.itertext()).strip()
    return ""

def parse_date(value):
    if not value:
        return ""
    value = value.strip()
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""

def read_feeds():
    feeds = []
    for line in FEEDS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "|" not in line:
            continue
        name, url = (part.strip() for part in line.split("|", 1))
        if name and url.startswith(("https://", "http://")):
            feeds.append((name, url))
    return feeds

def parse_feed(name, url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read(3_000_000)
    root = ET.fromstring(payload)
    nodes = [n for n in root.iter() if n.tag.rsplit("}", 1)[-1].lower() in ("item", "entry")]
    results = []
    for node in nodes[:MAX_PER_FEED]:
        title = clean(child_text(node, {"title"}))
        link = child_text(node, {"link"})
        if not link:
            for child in list(node):
                if child.tag.rsplit("}", 1)[-1].lower() == "link" and child.attrib.get("href"):
                    link = child.attrib["href"]
                    break
        summary = clean(child_text(node, {"description", "summary", "content", "encoded"}))
        date = parse_date(child_text(node, {"pubdate", "published", "updated", "date", "issued", "modified"}))
        if title and link.startswith(("https://", "http://")):
            results.append({"title": title[:300], "url": link, "summary": summary[:500], "source": name, "date": date})
    return results

def main():
    articles, errors = [], []
    for name, url in read_feeds():
        try:
            articles.extend(parse_feed(name, url))
            print(f"OK {name}")
        except Exception as exc:
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
            print(f"WARN {errors[-1]}")
        time.sleep(0.5)
    unique, seen = [], set()
    for article in articles:
        key = article["url"].split("#", 1)[0]
        if key not in seen:
            seen.add(key)
            unique.append(article)
    unique.sort(key=lambda a: a.get("date") or "", reverse=True)
    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "articles": unique[:MAX_TOTAL],
        "feed_count": len(read_feeds()),
        "errors": errors,
    }
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(data['articles'])} articles; feed errors: {len(errors)}")
    if not data["articles"]:
        raise SystemExit("No articles fetched. Check feeds.txt and the Actions log.")

if __name__ == "__main__":
    main()
