"""Validate public output, preserved content, and the editorial HTML boundary."""
import importlib.util
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("site_build", ROOT / "scripts/build.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        for key in ("href", "src"):
            if key in attrs:
                self.urls.append(attrs[key])


class SiteBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name) / "public"
        cls.posts = builder.build(cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_internal_links_and_assets_resolve(self):
        pages = {page: Links() for page in self.output.rglob("*.html")}
        for page, links in pages.items():
            links.feed(page.read_text())
        for page, links in pages.items():
            for value in links.urls:
                parsed = urlsplit(value)
                if parsed.scheme or parsed.netloc:
                    continue
                target = (page.parent / unquote(parsed.path)).resolve() if parsed.path else page
                self.assertTrue(target.is_relative_to(self.output.resolve()), value)
                self.assertTrue(target.is_file(), f"{page.name}: {value}")
                if parsed.fragment and target in pages:
                    self.assertIn(unquote(parsed.fragment), pages[target].ids, value)

    def test_only_public_files_are_exported(self):
        exported = {str(path.relative_to(self.output)) for path in self.output.rglob("*") if path.is_file()}
        expected = {"index.html", "blog.html", "robots.txt", "sitemap.xml", "contents/social-card.png"} | set(builder.ASSETS)
        expected |= {f"posts/{post['id']}.html" for post in self.posts}
        self.assertEqual(exported, expected)

    def test_old_post_ids_and_dates_survive(self):
        by_id = {post["id"]: post for post in self.posts}
        self.assertEqual(by_id["2026-04-29-welcome"]["date"], "2026-04-29")
        self.assertEqual(by_id["2026-04-20-sample-practice"]["date"], "2026-04-20")
        blog = (self.output / "blog.html").read_text()
        self.assertIn('id="2026-04-29-welcome"', blog)

    def test_sample_is_labeled_and_excluded_from_sitemap(self):
        sample = (self.output / "posts/2026-04-20-sample-practice.html").read_text()
        self.assertIn('content="noindex, follow"', sample)
        self.assertIn("実際の活動報告ではありません", sample)
        xml = ET.parse(self.output / "sitemap.xml")
        urls = [node.text for node in xml.findall(".//{*}loc")]
        self.assertEqual(len(urls), 4)
        self.assertFalse(any("sample-practice" in url for url in urls))

    def test_contact_and_metadata(self):
        home = (self.output / "index.html").read_text()
        self.assertIn("mailto:toyama.univ.icehockey@gmail.com", home)
        self.assertNotIn("example.com", home)
        self.assertNotIn('href="#"', home)
        for page in self.output.rglob("*.html"):
            content = page.read_text()
            self.assertIn('property="og:image"', content)
            self.assertIn('rel="canonical"', content)
            self.assertNotIn("{{head}}", content)

    def test_hostile_html_is_not_executed(self):
        result = builder.safe_body('<p onclick="evil()">safe<script>evil()</script><img src=x onerror=evil()><a href="javascript:evil()">bad</a><svg><script>evil()</script></svg><strong>good</strong></p>')
        self.assertEqual(result, '<p>safe<a>bad</a><strong>good</strong></p>')
        self.assertNotIn("evil", result)
        self.assertIn('href="https://example.org/?a=1&amp;b=2"', builder.safe_body('<a href="https://example.org/?a=1&amp;b=2" onclick="evil()">link</a>'))

    def test_invalid_post_ids_and_duplicates_fail(self):
        sample = {"id": "valid", "title": "title", "author": "author", "date": "2026-10-10", "body": "<p>body</p>"}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "posts.json"
            for entries in ([dict(sample, id="../../outside")], [sample, sample], [dict(sample, date="2026-99-99")]):
                path.write_text(json.dumps({"posts": entries}))
                with self.assertRaises(ValueError):
                    builder.load_posts(path)

    def test_rebuild_removes_stale_generated_posts(self):
        stale = self.output / "posts/stale.html"
        stale.write_text("old")
        original = (self.output / "index.html").read_bytes()
        builder.build(self.output)
        self.assertFalse(stale.exists())
        self.assertEqual(original, (self.output / "index.html").read_bytes())


if __name__ == "__main__":
    unittest.main()
