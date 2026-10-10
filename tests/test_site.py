import json
import math
import re
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
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


    def test_page_has_accessible_main_landmark_and_skip_link(self):
        self.assertIn('<main id="main-content">', self.html)
        self.assertIn('<a class="skip-link" href="#main-content">本文へスキップ</a>', self.html)
        self.assertIn('<nav aria-label="メインナビゲーション">', self.html)
        self.assertIn('name="description"', self.html)

    def test_recommendation_catalog_has_eleven_unique_presets(self):
        preset_ids = re.findall(r"\{id:'([^']+)'", self.html)
        self.assertEqual(11, len(preset_ids), f"Expected 11 PC presets, found {len(preset_ids)}.")
        self.assertEqual(len(preset_ids), len(set(preset_ids)), "Recommendation preset IDs must be unique.")
        self.assertIn("window.pcShindanApplyBuild", self.html)
        self.assertIn("news.json", self.html)


    def test_all_presets_have_compatible_catalog_parts(self):
        parts_match = re.search(r"const parts\s*=\s*(\{.*?\n\s*\});", self.html, re.DOTALL)
        builds_match = re.search(r"const recommendedBuilds\s*=\s*(\[.*?\n\s*\]);", self.html, re.DOTALL)
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

    def test_search_engine_files_and_custom_404_page(self):
        robots = ROOT / "robots.txt"
        sitemap = ROOT / "sitemap.xml"
        not_found = ROOT / "404.html"
        self.assertTrue(robots.is_file(), "Missing robots.txt.")
        self.assertTrue(sitemap.is_file(), "Missing sitemap.xml.")
        self.assertTrue(not_found.is_file(), "Missing branded 404 page.")
        robots_text = robots.read_text(encoding="utf-8")
        self.assertIn("User-agent: *", robots_text)
        self.assertIn("Sitemap: https://nakky9249-ux.github.io/pc-shindan/sitemap.xml", robots_text)
        root = ET.parse(sitemap).getroot()
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        urls = {node.text for node in root.findall("sm:url/sm:loc", namespace)}
        for page in ["", "about.html", "privacy.html", "affiliate.html", "contact.html"]:
            expected = "https://nakky9249-ux.github.io/pc-shindan/" + page
            with self.subTest(page=page or "index.html"):
                self.assertIn(expected, urls)
        error_page = not_found.read_text(encoding="utf-8")
        self.assertIn("lang=\"ja\"", error_page)
        self.assertIn("noindex,follow", error_page)
        self.assertIn('href="./"', error_page)

    def test_site_information_pages_exist(self):
        required_pages = ["about.html", "privacy.html", "affiliate.html", "contact.html"]
        for page in required_pages:
            with self.subTest(page=page):
                path = ROOT / page
                self.assertTrue(path.is_file(), f"Missing site information page: {page}")
                html = path.read_text(encoding="utf-8")
                self.assertIn('lang="ja"', html)
                self.assertIn('<meta name="viewport"', html)
                self.assertIn('href="./info.css"', html)
                self.assertRegex(html, r"<title>[^<]+</title>")
                self.assertIn('href="./privacy.html"', html)
                self.assertIn('href="./affiliate.html"', html)

    def test_affiliate_disclosure_matches_current_links(self):
        self.assertIn("通常の公式サイトへのリンク", self.html)
        self.assertIn("アフィリエイト提携済みリンクではありません", self.html)
        affiliate_page = (ROOT / "affiliate.html").read_text(encoding="utf-8")
        self.assertIn("通常の公式サイトへのリンク", affiliate_page)
        self.assertNotIn("提携済みの広告リンクです", affiliate_page)

    def test_recommendation_cards_have_original_visuals(self):
        self.assertIn("const buildVisualSvg", self.html)
        self.assertIn("className='build-visual'", self.html)
        self.assertIn("card.append(visual,badge,title,price,desc,list,breakdown,button)", self.html)
        self.assertIn("商品写真・メーカー公式ロゴではなく", self.html)

    def test_bto_shop_cards_have_site_favicons_with_fallbacks(self):
        self.assertEqual(6, self.html.count('class="shop-favicon"'))
        self.assertEqual(6, self.html.count('class="shop-fallback'))
        for domain in ["www.dospara.co.jp", "www.mouse-jp.co.jp", "www.frontier-direct.jp",
                       "www.tsukumo.co.jp", "www.pc-koubou.jp", "www.sycom.co.jp"]:
            with self.subTest(domain=domain):
                self.assertIn("https://" + domain + "/favicon.ico", self.html)
        self.assertIn("showFallback", self.html)

    def test_news_cards_support_feed_images_and_fallback(self):
        self.assertIn("article.image", self.html)
        self.assertIn("className = 'news-thumb'", self.html)
        self.assertIn("news-thumb-fallback", self.html)
        self.assertIn("image.addEventListener('error'", self.html)

    def test_recommendation_search_is_available_and_accessible(self):
        self.assertIn('id="recommendation-search"', self.html)
        self.assertIn('id="recommendation-results-status"', self.html)
        self.assertIn("toLocaleLowerCase('ja')", self.html)
        self.assertIn("条件に合う構成がありません", self.html)

    def test_news_dates_and_summaries_are_formatted(self):
        self.assertIn("Intl.DateTimeFormat('ja-JP'", self.html)
        self.assertIn("formatNewsDate(article.date)", self.html)
        self.assertIn("className = 'news-summary'", self.html)
        self.assertIn("最終更新：", self.html)

    def test_news_search_is_accessible_and_filters_titles_sources_and_summaries(self):
        self.assertIn('id="news-search"', self.html)
        self.assertIn('id="auto-news-count"', self.html)
        self.assertIn('aria-describedby="auto-news-count"', self.html)
        self.assertIn("const renderNews = () =>", self.html)
        self.assertIn("search?.addEventListener('input', renderNews)", self.html)
        self.assertIn("article.title, article.source, article.summary", self.html)
        self.assertIn("一致する記事がありません", self.html)

    def test_pricing_copy_does_not_claim_live_prices(self):
        self.assertIn("価格表示について", self.html)
        self.assertIn("参考価格", self.html)
        self.assertIn("各ショップの公式サイトで実売価格を比較します", self.html)

    def test_local_page_links_resolve(self):
        pages = [ROOT / "index.html"] + [ROOT / name for name in ["about.html", "privacy.html", "affiliate.html", "contact.html"]]
        for path in pages:
            html = path.read_text(encoding="utf-8")
            for href in re.findall(r"""href=["']([^"']+)["']""", html):
                if href.startswith(("https://", "http://", "mailto:", "tel:", "#", "data:")):
                    continue
                target = href.split("#", 1)[0].split("?", 1)[0]
                if not target:
                    continue
                resolved = (path.parent / target).resolve()
                with self.subTest(page=path.name, href=href):
                    self.assertTrue(resolved.is_file(), f"Broken local link in {path.name}: {href}")


if __name__ == "__main__":
    unittest.main()
