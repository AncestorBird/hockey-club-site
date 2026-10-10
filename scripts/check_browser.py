#!/usr/bin/env python3
"""Optional real-browser checks. Requires Playwright and a local Chromium."""
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from urllib.request import urlopen

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"


def run():
    subprocess.run([sys.executable, str(ROOT / "scripts/build.py")], check=True)
    ARTIFACTS.mkdir(exist_ok=True)

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(ROOT / "dist")))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    errors = []
    checks = 0

    def check(condition, description):
        nonlocal checks
        if not condition:
            raise AssertionError(description)
        checks += 1

    try:
        with sync_playwright() as p:
            executable = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
            browser = p.chromium.launch(executable_path=executable, headless=True, args=["--no-sandbox"])
            context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("response", lambda response: errors.append(f"HTTP {response.status}: {response.url}") if response.status >= 400 else None)
            page.goto(base + "/index.html", wait_until="networkidle")
            expect(page.locator("h1")).to_contain_text("氷上の青春になる")
            check(page.locator('#contact a[href="mailto:toyama.univ.icehockey@gmail.com"]').count() == 1, "Email contact is present")
            page.screenshot(path=str(ARTIFACTS / "home-desktop.png"), full_page=True)
            page.locator('.hero a[href="#recruit"]').click()
            check(page.url.endswith("#recruit"), "Hero button reaches recruitment")
            page.locator("summary").first.click()
            expect(page.locator("details").first).to_have_attribute("open", "")
            checks += 1
            page.locator('.main-nav a[href="blog.html"]').click()
            expect(page.locator("#result-count")).to_have_text("3件の記事")
            page.screenshot(path=str(ARTIFACTS / "blog-desktop.png"), full_page=True)
            page.locator("#post-search").fill("パック")
            expect(page.locator("#result-count")).to_have_text("1件の記事")
            check(page.locator(".post-card:visible").count() == 1, "Search includes article body")
            page.reload(wait_until="networkidle")
            expect(page.locator("#post-search")).to_have_value("パック")
            expect(page.locator("#result-count")).to_have_text("1件の記事")
            checks += 1
            page.get_by_role("button", name="部員日記", exact=True).click()
            expect(page.locator("#empty-state")).to_be_visible()
            expect(page.locator("#result-count")).to_have_text("0件の記事")
            checks += 1
            page.get_by_role("button", name="条件をリセット").click()
            expect(page.locator("#result-count")).to_have_text("3件の記事")
            check("?" not in page.url, "Reset removes filter query")
            page.locator("#post-search").fill('<img src=x onerror="window.hacked=true">')
            expect(page.locator("#empty-state")).to_be_visible()
            check(page.evaluate("window.hacked === undefined"), "Search treats markup as text")
            page.get_by_role("button", name="条件をリセット").click()
            page.get_by_role("button", name="ホッケー入門", exact=True).click()
            expect(page.locator(".post-card:visible")).to_have_count(1)
            page.locator(".post-card:visible .card-link").click()
            expect(page.locator(".article-body")).to_contain_text("選手交代")
            page.screenshot(path=str(ARTIFACTS / "article-desktop.png"), full_page=True)
            checks += 1
            page.get_by_role("link", name="記事一覧へ戻る").click()
            expect(page.locator("#result-count")).to_have_text("3件の記事")
            page.locator('[id="2026-04-20-sample-practice"] .card-link').click()
            expect(page.locator(".sample-notice")).to_contain_text("実際の活動報告ではありません")
            checks += 1
            # Responsive layouts: inspect every public page at narrow, tablet, and desktop widths.
            paths = ["index.html", "blog.html"] + [str(path.relative_to(ROOT / "dist")) for path in (ROOT / "dist/posts").glob("*.html")]
            for width in (320, 390, 768, 1024, 1440, 1920):
                page.set_viewport_size({"width": width, "height": 900})
                for path in paths:
                    page.goto(base + "/" + path, wait_until="networkidle")
                    check(page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"No horizontal overflow: {width}px {path}")
                    check(page.locator("h1").count() == 1, f"Single page heading: {path}")
            page.set_viewport_size({"width": 390, "height": 844})
            page.goto(base + "/index.html", wait_until="networkidle")
            page.screenshot(path=str(ARTIFACTS / "home-mobile.png"), full_page=True)
            toggle = page.locator(".menu-toggle")
            toggle.click()
            expect(toggle).to_have_attribute("aria-expanded", "true")
            page.keyboard.press("Escape")
            expect(toggle).to_have_attribute("aria-expanded", "false")
            expect(toggle).to_be_focused()
            checks += 1
            toggle.click()
            page.locator('.main-nav a[href="index.html#contact"]').click()
            expect(toggle).to_have_attribute("aria-expanded", "false")
            check(page.url.endswith("#contact"), "Mobile menu reaches contact and closes")
            toggle.click()
            page.keyboard.press("Tab")
            expect(page.locator('.main-nav a').first).to_be_focused()
            checks += 1
            page.goto(base + "/blog.html", wait_until="networkidle")
            page.screenshot(path=str(ARTIFACTS / "blog-mobile.png"), full_page=True)
            page.locator("#post-search").fill("存在しない記事")
            expect(page.locator("#empty-state")).to_be_visible()
            page.screenshot(path=str(ARTIFACTS / "blog-empty-mobile.png"), full_page=True)
            page.goto(base + "/posts/2026-10-10-hockey-guide.html", wait_until="networkidle")
            page.screenshot(path=str(ARTIFACTS / "article-mobile.png"), full_page=True)
            nojs = browser.new_context(java_script_enabled=False, viewport={"width": 390, "height": 844})
            plain = nojs.new_page()
            plain.goto(base + "/blog.html")
            check(plain.locator(".post-card").count() == 3, "Articles available without JavaScript")
            check(plain.locator(".main-nav").is_visible(), "Navigation available without JavaScript")
            plain.locator(".card-link").first.click()
            expect(plain.locator(".article-body")).to_be_visible()
            checks += 1
            for path in ("/.git/config", "/.env", "/posts.json", "/scripts/build.py", "/README.md"):
                try:
                    urlopen(base + path)
                    check(False, f"Private source exposed: {path}")
                except Exception as error:
                    check(getattr(error, "code", None) == 404, f"Private source excluded: {path}")
            nojs.close()
            context.close()
            browser.close()
        check(not errors, f"Browser errors: {errors}")
        print(f"PASS: {checks} browser/HTTP checks; desktop and mobile screenshots saved to artifacts/.")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    run()
