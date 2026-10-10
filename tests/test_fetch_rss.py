import importlib.util
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("fetch_rss", ROOT / "scripts" / "fetch_rss.py")
rss = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rss)

class FetchRssTests(unittest.TestCase):
    def test_clean_removes_html_and_decodes_entities(self):
        self.assertEqual(rss.clean("<p>PC &amp; Games</p>\n news"), "PC & Games news")

    def test_parse_iso_date_to_utc(self):
        self.assertEqual(rss.parse_date("2026-10-10T12:00:00+09:00"), "2026-10-10T03:00:00+00:00")

    def test_parse_rss_item(self):
        item = ET.fromstring("<item><title>Test &amp; News</title><link>https://example.com/a</link><description><![CDATA[<b>Summary</b> here]]></description><pubDate>Sat, 10 Oct 2026 03:00:00 GMT</pubDate></item>")
        self.assertEqual(rss.clean(rss.child_text(item, {"title"})), "Test & News")
        self.assertEqual(rss.child_text(item, {"link"}), "https://example.com/a")
        self.assertEqual(rss.clean(rss.child_text(item, {"description"})), "Summary here")
        self.assertEqual(rss.parse_date(rss.child_text(item, {"pubdate"})), "2026-10-10T03:00:00+00:00")

    def test_parse_atom_link(self):
        entry = ET.fromstring('<entry xmlns="http://www.w3.org/2005/Atom"><title>Atom item</title><link rel="self" href="https://example.com/self"/><link rel="alternate" href="https://example.com/article"/><updated>2026-10-10T03:00:00Z</updated></entry>')
        self.assertEqual(rss.child_text(entry, {"link"}), "https://example.com/article")

if __name__ == "__main__":
    unittest.main()
