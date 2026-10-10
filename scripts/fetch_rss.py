#!/usr/bin/env python3
"""Fetch public RSS/Atom feeds and publish a deduplicated news.json."""
import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEEDS = ROOT / "feeds.txt"
OUTPUT = ROOT / "news.json"
MAX_PER_FEED = 30
MAX_TOTAL = 120
MAX_BYTES = 4_000_000
USER_AGENT = "PCShindanRSSBot/1.1 (+https://github.com/nakky9249-ux/pc-shindan)"

def local_name(tag):
    """Return a namespace-independent lowercase XML element name."""
    return tag.rsplit("}", 1)[-1].split(":")[-1].lower()

def clean(value):
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()

def child_text(el, names):
    """Read a direct child by local XML name; supports Atom href links."""
    names = {n.lower() for n in names}
    for child in list(el):
        tag = local_name(child.tag)
        if tag not in names:
            continue
        if tag == "link" and child.attrib.get("href"):
            rel = child.attrib.get("rel", "alternate")
            if rel not in ("alternate", ""):
                continue
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
    for line_no, line in enumerate(FEEDS.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" not in line:
            print(f"WARN feeds.txt:{line_no}: expected name|url")
            continue
        name, url = (part.strip() for part in line.split("|", 1))
        if name and url.startswith(("https://", "http://")):
            feeds.append((name, url))
        else:
            print(f"WARN feeds.txt:{line_no}: invalid feed name or URL")
    return feeds

def safe_image_url(value):
    """Return a safe public image URL, or an empty string."""
    value = (value or "").strip()
    if value.startswith("//"):
        value = "https:" + value
    if not value.lower().startswith(("https://", "http://")):
        return ""
    return value[:2000]


def child_image_url(node):
    """Extract an image URL from common RSS/Atom media fields and HTML summaries."""
    # Prefer explicit thumbnails and image enclosures/media content.
    for child in node.iter():
        if child is node:
            continue
        tag = local_name(child.tag)
        url = child.attrib.get("url") or child.attrib.get("href") or ""
        if not url:
            continue
        media_type = (child.attrib.get("type") or "").lower()
        medium = (child.attrib.get("medium") or "").lower()
        is_image = media_type.startswith("image/") or medium == "image"
        if tag == "thumbnail":
            result = safe_image_url(url)
            if result:
                return result
        elif tag == "enclosure" and is_image:
            result = safe_image_url(url)
            if result:
                return result
        elif tag == "content" and is_image:
            result = safe_image_url(url)
            if result:
                return result

    # Some feeds embed the first article image in description/content HTML.
    for child in node.iter():
        if local_name(child.tag) not in {"description", "summary", "content", "encoded"}:
            continue
        html = "".join(child.itertext())
        match = re.search(r"""<img\b[^>]*?src\s*=\s*["']([^"']+)["']""", html, re.IGNORECASE)
        if match:
            result = safe_image_url(unescape(match.group(1)))
            if result:
                return result
    return ""


def parse_feed(name, url):
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    })
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                payload = response.read(MAX_BYTES + 1)
            if len(payload) > MAX_BYTES:
                raise ValueError("feed exceeds 4 MB size limit")
            break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    else:
        raise last_error
    root = ET.fromstring(payload)
    nodes = [n for n in root.iter() if local_name(n.tag) in ("item", "entry")]
    results = []
    for node in nodes[:MAX_PER_FEED]:
        title = clean(child_text(node, {"title"}))
        link = child_text(node, {"link"})
        if not link:
            for child in list(node):
                if local_name(child.tag) == "link" and child.attrib.get("href"):
                    link = child.attrib["href"].strip()
                    break
        summary = clean(child_text(node, {"description", "summary", "content", "encoded", "subtitle"}))
        image = child_image_url(node)
        date = parse_date(child_text(node, {"pubdate", "published", "updated", "date", "issued", "modified", "created"}))
        if title and link.startswith(("https://", "http://")):
            article = {
                "title": title[:300],
                "url": link,
                "summary": summary[:600],
                "source": name[:100],
                "date": date,
            }
            if image:
                article["image"] = image
            results.append(article)
    return results

def main():
    feeds = read_feeds()
    articles, errors = [], []
    if not feeds:
        raise SystemExit("No valid RSS feeds configured in feeds.txt")
    for name, url in feeds:
        try:
            fetched = parse_feed(name, url)
            articles.extend(fetched)
            print(f"OK {name}: {len(fetched)} articles")
            if not fetched:
                errors.append(f"{name}: feed parsed but contained no usable entries")
        except Exception as exc:
            message = f"{name}: {type(exc).__name__}: {exc}"
            errors.append(message)
            print(f"WARN {message}")
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
        "feed_count": len(feeds),
        "successful_feeds": len(feeds) - len({e.split(":", 1)[0] for e in errors}),
        "errors": errors,
    }
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(data['articles'])} unique articles from {len(feeds)} feeds; {len(errors)} feed warnings")
    # Preserve diagnostic output even when one provider fails; fail only if all providers failed.
    if not data["articles"]:
        raise SystemExit("No articles fetched from any feed. Check feed URLs and the Actions log.")

if __name__ == "__main__":
    main()
