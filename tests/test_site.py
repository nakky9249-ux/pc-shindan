import json
import math
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
        scripts = re.findall(r"<script\b[^>]*>([\s\S]*?)</script\s*>", self.html, re.IGNORECASE)
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
            self.assertEqual(0, result.returncode, f"Inline script {index + 1} has a syntax error:\n{result.stderr}")

    def test_recommendation_catalog_has_eleven_unique_presets(self):
        preset_ids = re.findall(r"\{id:'([^']+)'", self.html)
        self.assertEqual(11, len(preset_ids), f"Expected 11 PC presets, found {len(preset_ids)}.")
        self.assertEqual(len(preset_ids), len(set(preset_ids)), "Recommendation preset IDs must be unique.")
        self.assertIn("window.pcShindanApplyBuild", self.html)
        self.assertIn("news.json", self.html)


    def test_all_presets_have_compatible_catalog_parts(self):
        parts_match = re.search(r"const parts\\s*=\\s*(\\{[\\s\\S]*?\\n\\s*\\});", self.html)
        builds_match = re.search(r"const recommendedBuilds\\s*=\\s*(\\[[\\s\\S]*?\\n\\s*\\]);", self.html)
        self.assertIsNotNone(parts_match, "Could not locate the part catalog.")
        self.assertIsNotNone(builds_match, "Could not locate the recommendation catalog.")
        js = (
            "const parts=" + parts_match.group(1) + ";"
            "const recommendedBuilds=" + builds_match.group(1) + ";"
            "console.log(JSON.stringify({parts,recommendedBuilds}));"
        )
        result = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, f"Could not inspect catalogs: {result.stderr}")
        data = json.loads(result.stdout)
        parts = data["parts"]
        fields = {
            "cpu": parts["cpu"],
            "gpu": parts["gpu"],
            "board": parts["board"],
            "ram": parts["ram4"] + parts["ram5"],
            "ssd": parts["ssd"],
            "psu": parts["psu"],
            "pcCase": parts["pcCase"],
            "cooler": parts["cooler"],
            "hdd": parts["hdd"],
            "fans": parts["fans"],
            "os": parts["os"],
        }
        for build in data["recommendedBuilds"]:
            with self.subTest(preset=build["id"]):
                chosen = {}
                for field, catalog in fields.items():
                    item = next((item for item in catalog if item["n"] == build[field]), None)
                    self.assertIsNotNone(item, f"{build['id']}: {field} '{build[field]}' is missing from catalog.")
                    chosen[field] = item
                cpu = chosen["cpu"]
                board = chosen["board"]
                self.assertEqual(cpu["s"], board["s"], f"{build['id']}: CPU and motherboard socket mismatch.")
                self.assertEqual(cpu["r"], board["r"], f"{build['id']}: CPU and motherboard memory type mismatch.")
                self.assertIn(cpu["r"], chosen["ram"]["n"], f"{build['id']}: RAM type mismatch.")
                required_watts = math.ceil((cpu["t"] + chosen["gpu"]["w"] + 150) * 1.2 / 50) * 50
                self.assertGreaterEqual(chosen["psu"]["w"], required_watts,
                                        f"{build['id']}: PSU below the site's estimated {required_watts}W target.")
                self.assertGreaterEqual(chosen["cooler"]["t"], cpu["t"],
                                        f"{build['id']}: cooler rating is below the CPU TDP estimate.")


if __name__ == "__main__":
    unittest.main()
