#!/usr/bin/env python3
"""Build the public static site using only Python's standard library."""
from __future__ import annotations

import html
import json
import math
import re
import shutil
import tempfile
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://ancestorbird.github.io/hockey-club-site/"
SITE_NAME = "富山大学アイスホッケー部"
EMAIL = "toyama.univ.icehockey@gmail.com"
ASSETS = ("css/style.css", "js/site.js", "contents/favicon.svg",
          "contents/journal-art.svg", "contents/photo_flyer_2026.png")


class SafeBody(HTMLParser):
    """Keep basic editorial markup; never copy arbitrary scripts or attributes."""
    allowed = {"p", "br", "strong", "em", "h2", "h3", "ul", "ol", "li", "blockquote", "a"}
    blocked = {"script", "style", "iframe", "object", "svg", "math", "template"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.result: list[str] = []
        self.stack: list[str] = []
        self.suppressed: list[str] = []

    def handle_starttag(self, tag, attrs):
        if self.suppressed:
            if tag in self.blocked:
                self.suppressed.append(tag)
            return
        if tag in self.blocked:
            self.suppressed.append(tag)
            return
        if tag not in self.allowed:
            return
        extra = ""
        if tag == "a":
            href = dict(attrs).get("href", "") or ""
            parsed = urlsplit(href)
            if (parsed.scheme in {"https", "http", "mailto"} or
                    (not parsed.scheme and not parsed.netloc and href.startswith("#"))):
                extra = f' href="{html.escape(href, quote=True)}"'
                if parsed.scheme in {"https", "http"}:
                    extra += ' rel="noopener noreferrer"'
        self.result.append(f"<{tag}{extra}>")
        if tag != "br":
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag != "br":
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.suppressed:
            if tag == self.suppressed[-1]:
                self.suppressed.pop()
            return
        if tag in self.stack:
            while self.stack:
                current = self.stack.pop()
                self.result.append(f"</{current}>")
                if current == tag:
                    break

    def handle_data(self, data):
        if not self.suppressed:
            self.result.append(html.escape(data))

    def rendered(self):
        return "".join(self.result) + "".join(f"</{tag}>" for tag in reversed(self.stack))


def safe_body(value: str) -> str:
    parser = SafeBody()
    parser.feed(value)
    parser.close()
    return parser.rendered()


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(value: str) -> str:
    parser = PlainText()
    parser.feed(value)
    return " ".join(" ".join(parser.parts).split())


def load_posts(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("posts"), list):
        raise ValueError("posts.json must contain a posts array")
    seen = set()
    posts = []
    for source in data["posts"]:
        if not isinstance(source, dict):
            raise ValueError("Each post must be an object")
        for key in ("id", "title", "author", "date", "body"):
            if not isinstance(source.get(key), str) or not source[key].strip():
                raise ValueError(f"Each post needs a nonempty {key}")
        slug = source["id"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or slug in seen:
            raise ValueError(f"Invalid or duplicate post id: {slug!r}")
        seen.add(slug)
        parsed_date = date.fromisoformat(source["date"])
        if parsed_date.isoformat() != source["date"]:
            raise ValueError("Dates must use YYYY-MM-DD")
        post = dict(source)
        if not isinstance(post.get("category", "お知らせ"), str):
            raise ValueError("category must be a string")
        if not isinstance(post.get("sample", False), bool):
            raise ValueError("sample must be a boolean")
        post["category"] = post.get("category", "お知らせ")
        post["sample"] = post.get("sample", False)
        post["body"] = safe_body(source["body"])
        post["plain"] = plain_text(post["body"])
        post["excerpt"] = post["plain"][:78] + ("…" if len(post["plain"]) > 78 else "")
        post["read_time"] = max(1, math.ceil(len(post["plain"]) / 450))
        posts.append(post)
    return sorted(posts, key=lambda post: post["date"], reverse=True)


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def render(template: str, fields: dict) -> str:
    # Single substitution pass: blog text containing {{...}} is never re-interpreted.
    return re.sub(r"\{\{([a-z_]+)\}\}", lambda match: str(fields[match[1]]), template)


def head(title: str, description: str, url: str, prefix: str = "", structured=None,
         noindex=False, og_type="website") -> str:
    schema = ""
    if structured:
        encoded = json.dumps(structured, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        schema = f'<script type="application/ld+json">{encoded}</script>'
    return f'''<meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <meta name="theme-color" content="#111d2b">
  <meta name="robots" content="{'noindex, follow' if noindex else 'index, follow'}">
  <link rel="canonical" href="{esc(url)}">
  <link rel="icon" type="image/svg+xml" href="{prefix}contents/favicon.svg">
  <link rel="stylesheet" href="{prefix}css/style.css">
  <meta property="og:type" content="{og_type}">
  <meta property="og:locale" content="ja_JP">
  <meta property="og:site_name" content="{SITE_NAME}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:url" content="{esc(url)}">
  <meta property="og:image" content="{BASE_URL}contents/social-card.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="BEYOND THE ICE. — TOYAMA UNIVERSITY ICE HOCKEY CLUB">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(title)}">
  <meta name="twitter:description" content="{esc(description)}">
  <meta name="twitter:image" content="{BASE_URL}contents/social-card.png">
  {schema}'''


def brand(prefix="") -> str:
    return f'''<a class="brand" href="{prefix}index.html" aria-label="富山大学アイスホッケー部 ホーム"><img class="brand-icon" src="{prefix}contents/favicon.svg" width="40" height="40" alt=""><span class="brand-name"><strong>TOYAMA UNIV.</strong><small>ICE HOCKEY CLUB / アイスホッケー部</small></span></a>'''


def header(prefix="", current="home") -> str:
    active = ' aria-current="page"' if current == "blog" else ""
    return f'''<a class="skip-link" href="#main">本文へスキップ</a>
  <header class="site-header"><div class="wrap header-inner">{brand(prefix)}
  <button class="menu-toggle" type="button" aria-label="メニューを開く" aria-controls="main-nav" aria-expanded="false"><span aria-hidden="true"></span></button>
  <nav class="main-nav" id="main-nav" aria-label="メインメニュー"><a href="{prefix}index.html#about">チームについて</a><a href="{prefix}index.html#activity">活動</a><a href="{prefix}blog.html"{active}>ブログ</a><a href="{prefix}index.html#contact">お問い合わせ</a><a class="nav-join" href="{prefix}index.html#recruit">見学・体験 <span aria-hidden="true">↗</span></a></nav></div></header>'''


def footer(prefix="") -> str:
    return f'''<footer class="site-footer"><div class="wrap"><div class="footer-top">{brand(prefix)}<nav class="footer-links" aria-label="フッターメニュー"><a href="{prefix}index.html#about">チームについて</a><a href="{prefix}blog.html">ブログ</a><a href="{prefix}index.html#recruit">見学・体験</a><a href="mailto:{EMAIL}">お問い合わせ</a></nav></div><div class="footer-bottom"><p>© {date.today().year} 富山大学アイスホッケー部</p><a href="#main">BACK TO TOP ↑</a></div></div></footer>'''


def artwork(post: dict):
    if post["category"] == "ホッケー入門":
        return "art-rink", '<svg viewBox="0 0 360 200"><rect x="20" y="20" width="320" height="160" rx="65"/><path d="M180 20v160M105 20v160M255 20v160"/><circle cx="180" cy="100" r="30"/><circle cx="85" cy="65" r="18"/><circle cx="85" cy="135" r="18"/><circle cx="275" cy="65" r="18"/><circle cx="275" cy="135" r="18"/><path d="M42 75v50M318 75v50"/></svg>'
    if post["category"] == "部員日記":
        return "art-practice", '<svg viewBox="0 0 360 200"><path d="M70 25l100 135q6 8 16 8h105q8 0 8-8v-13H183L93 18z"/><ellipse cx="92" cy="148" rx="28" ry="9"/><path d="M64 148v13c0 12 56 12 56 0v-13M37 95h70M230 53h85"/></svg>'
    return "art-note", '<span class="art-word">OUR TEAM.<br>OUR STORY.</span>'


def card(post: dict, prefix="", filtering=False) -> str:
    art_class, art = artwork(post)
    sample = '<span class="sample-badge">サンプル</span>' if post["sample"] else ""
    attrs = ""
    if filtering:
        search = " ".join((post["title"], post["plain"], post["author"], post["category"]))
        attrs = f' data-category="{esc(post["category"])}" data-search="{esc(search)}"'
    return f'''<article class="post-card" id="{esc(post['id'])}"{attrs}><a class="card-link" href="{prefix}posts/{post['id']}.html"><div class="card-art {art_class}" aria-hidden="true">{art}</div><div class="card-meta"><span class="card-category">{esc(post['category'])}{sample}</span><time datetime="{post['date']}">{post['date'].replace('-', '.')}</time></div><h3>{esc(post['title'])}</h3><p class="card-excerpt">{esc(post['excerpt'])}</p><div class="card-bottom"><span>{esc(post['author'])} · {post['read_time']} min read</span><span class="card-arrow" aria-hidden="true">↗</span></div></a></article>'''


def build(output: Path = ROOT / "dist") -> list[dict]:
    posts = load_posts(ROOT / "posts.json")
    templates = {name: (ROOT / "templates" / f"{name}.html").read_text(encoding="utf-8")
                 for name in ("index", "blog", "post")}
    if output.resolve() in {ROOT.resolve(), ROOT.parent.resolve()}:
        raise ValueError("Output must not be the repository or workspace root")
    # Finish rendering in staging before replacing previous generated output.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="site-build-", dir=output.parent) as temp:
        stage = Path(temp)
        for asset in ASSETS + ("contents/social-card.png",):
            target = stage / asset
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / asset, target)
        club_schema = {"@context": "https://schema.org", "@type": "SportsClub", "name": SITE_NAME,
                       "url": BASE_URL, "sport": "Ice Hockey", "email": EMAIL,
                       "sameAs": ["https://www.instagram.com/toyama_angels/"]}
        fields = {"head": head(f"{SITE_NAME} | BEYOND THE ICE.", "富山大学アイスホッケー部のチーム紹介と部員ブログ。選手・マネージャーを募集中。見学・体験の相談はメール・Instagramへ。", BASE_URL, structured=club_schema),
                  "header": header(), "footer": footer(),
                  "latest_posts": "\n".join(card(post) for post in posts if not post["sample"]) }
        (stage / "index.html").write_text(render(templates["index"], fields), encoding="utf-8")
        categories = ["すべて"] + list(dict.fromkeys(post["category"] for post in posts))
        filters = "".join(f'<button type="button" data-category="{esc(category)}" aria-pressed="{str(index == 0).lower()}">{esc(category)}</button>' for index, category in enumerate(categories))
        fields = {"head": head(f"ブログ | {SITE_NAME}", "部員の言葉でつづる日々の出来事と、ホッケーを楽しむヒント。カテゴリーやキーワードから記事を探せます。", BASE_URL + "blog.html"),
                  "header": header(current="blog"), "footer": footer(), "filters": filters,
                  "post_count": len(posts), "all_posts": "\n".join(card(post, filtering=True) for post in posts)}
        (stage / "blog.html").write_text(render(templates["blog"], fields), encoding="utf-8")
        (stage / "posts").mkdir()
        for post in posts:
            url = BASE_URL + f"posts/{post['id']}.html"
            schema = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": post["title"],
                      "datePublished": post["date"], "url": url, "inLanguage": "ja", "description": post["excerpt"],
                      "author": {"@type": "Organization", "name": SITE_NAME} if post["author"] == "編集部" else {"@type": "Person", "name": post["author"]}}
            art_class, art = artwork(post)
            fields = {"head": head(f"{post['title']} | {SITE_NAME}", post["excerpt"], url, "../", schema, post["sample"], "article"),
                      "header": header("../", "blog"), "footer": footer("../"),
                      "title": esc(post["title"]), "category": esc(post["category"]), "author": esc(post["author"]),
                      "date": post["date"], "formatted_date": post["date"].replace("-", "."),
                      "read_time": post["read_time"], "body": post["body"], "art_class": art_class, "art": art,
                      "sample_notice": '<p class="sample-notice">この記事は、既存サイトから引き継いだサンプル記事です。実際の活動報告ではありません。</p>' if post["sample"] else "",
                      "related_posts": "\n".join(card(other, "../") for other in [other for other in posts if other["id"] != post["id"] and not other["sample"]][:3])}
            (stage / "posts" / f"{post['id']}.html").write_text(render(templates["post"], fields), encoding="utf-8")
        urls = [BASE_URL, BASE_URL + "blog.html"] + [BASE_URL + f"posts/{post['id']}.html" for post in posts if not post["sample"]]
        sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(f"  <url><loc>{esc(url)}</loc></url>" for url in urls) + '\n</urlset>\n'
        (stage / "sitemap.xml").write_text(sitemap, encoding="utf-8")
        (stage / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}sitemap.xml\n", encoding="utf-8")
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(stage, output)
    return posts


if __name__ == "__main__":
    result = build()
    print(f"Built {len(result) + 2} pages ({len(result)} articles) in {ROOT / 'dist'}")
