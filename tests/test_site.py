import re
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "index.html"


class PageAudit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = []
        self.internal_links = []
        self.blank_links = []
        self.placeholder_links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag == "a":
            href = attrs.get("href", "")
            if href.startswith("#") and len(href) > 1:
                self.internal_links.append(href[1:])
            if href in ("", "#"):
                self.placeholder_links.append(href)
            if attrs.get("target", "").lower() == "_blank":
                self.blank_links.append((href, attrs.get("rel", "")))


class SiteSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.audit = PageAudit()
        cls.audit.feed(cls.html)
        cls.audit.close()

    def test_ids_are_unique(self):
        duplicates = sorted({value for value in self.audit.ids if self.audit.ids.count(value) > 1})
        self.assertEqual([], duplicates, f"Duplicate HTML ids: {duplicates}")

    def test_internal_links_have_targets(self):
        known_ids = set(self.audit.ids)
        missing = sorted(set(self.audit.internal_links) - known_ids)
        self.assertEqual([], missing, f"Broken in-page links: {missing}")

    def test_no_placeholder_links(self):
        self.assertEqual([], self.audit.placeholder_links, "Replace href='#' placeholder links with real destinations.")

    def test_new_tab_links_are_safe(self):
        unsafe = [(href, rel) for href, rel in self.audit.blank_links
                  if "noopener" not in rel.lower() or "noreferrer" not in rel.lower()]
        self.assertEqual([], unsafe, f"New-tab links need rel='noopener noreferrer': {unsafe}")

    def test_inline_javascript_syntax(self):
        scripts = re.findall(r"<script\\b[^>]*>([\\s\\S]*?)</script\\s*>", self.html, re.IGNORECASE)
        self.assertTrue(scripts, "No inline script found.")
        for index, script in enumerate(scripts):
            with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8") as file:
                file.write(script)
                file.flush()
                result = subprocess.run(
                    ["node", "--check", file.name],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            self.assertEqual(0, result.returncode, f"Inline script {index + 1} has a syntax error:\\n{result.stderr}")

    def test_recommendation_catalog_has_eleven_unique_presets(self):
        preset_ids = re.findall(r"\\{id:'([^']+)'", self.html)
        self.assertEqual(11, len(preset_ids), f"Expected 11 PC presets, found {len(preset_ids)}.")
        self.assertEqual(len(preset_ids), len(set(preset_ids)), "Recommendation preset IDs must be unique.")
        self.assertIn("window.pcShindanApplyBuild", self.html)
        self.assertIn("news.json", self.html)


if __name__ == "__main__":
    unittest.main()
