#!/usr/bin/env python3
"""
Rebuilds blog/index.html and keeps the blog URLs in sitemap.xml up to date.

Run from the repository root:  python scripts/build_blog.py

Every blog/*.html file (except index.html and files marked noindex) becomes a
card on the blog page. The script reads, from each article:
  - <title>                          -> card title (trailing " | Brand" removed)
  - <meta name="description">        -> card text (falls back to og:description)
  - "datePublished" in the JSON-LD   -> date + sort order (newest first)
  - "dateModified"  in the JSON-LD   -> sitemap <lastmod>
  - "N minute read" in the byline    -> reading time (optional)

Sitemap: only /blog/ URLs are touched. Other pages are never modified.
"""
import html
import re
import subprocess
import sys
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "blog"
SITEMAP = ROOT / "sitemap.xml"
BASE = "https://questmart.online"

# Only simple, URL-safe file names are allowed (no spaces, colons, etc.)
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.html$")


def warn(msg):
    # "::warning::" shows up as a yellow warning in the GitHub Actions log
    print(f"::warning::{msg}", file=sys.stderr)


def first(pattern, text, flags=re.S | re.I):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else ""


def clean(s):
    return " ".join(html.unescape(s).split())


class HeadParser(HTMLParser):
    """Reads <html lang>, <title> and all <meta> tags, in any attribute order."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metas = []
        self.title = ""
        self.lang = ""
        self._in_title = False
        self._title_done = False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            self.metas.append(a)
        elif tag == "title" and not self._title_done:
            self._in_title = True
        elif tag == "html" and not self.lang:
            self.lang = a.get("lang", "")

    def handle_endtag(self, tag):
        if tag == "title" and self._in_title:
            self._in_title = False
            self._title_done = True

    def handle_data(self, data):
        if self._in_title:
            self.title += data

    def meta(self, key, attr="name"):
        for m in self.metas:
            if m.get(attr, "").lower() == key:
                return m.get("content", "").strip()
        return ""


def git_date(path):
    """Fallback date: the day the file was last committed, else today."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(path)],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.strip()
        if out:
            return datetime.strptime(out, "%Y-%m-%d").date()
    except Exception:
        pass
    return date.today()


def parse_day(s):
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def first_paragraph(text, limit=160):
    """Fallback card text: the first real paragraph of the article, trimmed."""
    body = re.sub(r"<(script|style)\b.*?</\1>", " ", text, flags=re.S | re.I)
    for raw in re.findall(r"<p\b[^>]*>(.*?)</p>", body, flags=re.S | re.I):
        s = clean(re.sub(r"<[^>]+>", " ", raw))
        if len(s) >= 60:
            if len(s) > limit:
                s = s[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
            return s
    return ""


def read_post(path):
    if not SAFE_NAME.match(path.name):
        warn(f"'{path.name}' has an unsafe file name (spaces, colon or other "
             f"special characters). SKIPPED. Rename it, e.g. 'my-article.html'.")
        return None
    text = path.read_text(encoding="utf-8")
    parser = HeadParser()
    parser.feed(text)

    if "noindex" in parser.meta("robots").lower():
        return None

    title = clean(parser.title)
    # remove a trailing " | Brand" (any brand name)
    shorter = re.sub(r"\s+\|\s+[^|]+$", "", title)
    title = shorter or title
    if not title:
        warn(f"{path.name} has no <title>, skipped")
        return None

    desc = clean(parser.meta("description") or parser.meta("og:description", "property"))
    if not desc:
        desc = first_paragraph(text)
        warn(f"{path.name} has no meta description: used the first paragraph for the "
             f"card. Add <meta name=\"description\"> for better Google snippets.")

    published = parse_day(first(r'"datePublished"\s*:\s*"([^"]+)"', text)
                          or parser.meta("article:published_time", "property"))
    modified = parse_day(first(r'"dateModified"\s*:\s*"([^"]+)"', text)
                         or parser.meta("article:modified_time", "property"))
    fallback = git_date(path)
    d = published or fallback
    dm = max(modified or fallback, d)

    minutes = first(r"(\d+)\s*(?:minute|min)\s*read", text)
    lang = parser.lang or "en"
    return {
        "file": path.name, "title": title, "desc": desc, "date": d,
        "modified": dm, "minutes": minutes, "lang": lang,
    }


def fmt_date(d):
    return f"{d:%B} {d.day}, {d.year}"


CARD = """    <li class="post">
      <h2><a href="{url}" lang="{lang}" dir="auto">{title}</a></h2>
      <p lang="{lang}" dir="auto">{desc}</p>
      <span class="meta">{meta}</span>
    </li>"""


def render_card(p):
    meta = fmt_date(p["date"])
    if p["minutes"]:
        meta += f" · {p['minutes']} minute read"
    return CARD.format(
        url=f"{BASE}/blog/{p['file']}",
        lang=html.escape(p["lang"], quote=True),
        title=html.escape(p["title"], quote=False),
        desc=html.escape(p["desc"], quote=False),
        meta=meta,
    )


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blog | QuestMart</title>
<meta name="description" content="Practical guides on invoicing, freelancing and getting paid, including in crypto.">
<link rel="canonical" href="https://questmart.online/blog/">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:type" content="website">
<meta property="og:title" content="Blog | QuestMart">
<meta property="og:description" content="Practical guides on invoicing, freelancing and getting paid, including in crypto.">
<meta property="og:url" content="https://questmart.online/blog/">
<meta property="og:site_name" content="QuestMart">
<meta property="og:image" content="https://questmart.online/blog/images/invoice-studio-og.jpg">
<meta name="twitter:card" content="summary_large_image">
<style>
:root{
  --ink:#1b1f23; --muted:#5b6470; --line:#e6e8eb; --bg:#ffffff; --panel:#f7f8f9;
  --accent:#0f6b52; --accent-ink:#ffffff; --radius:10px; --maxw:760px;
}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.65;font-size:17px;}
a{color:var(--accent);text-decoration:none;}
a:hover{text-decoration:underline;}
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 20px;}
header.site{border-bottom:1px solid var(--line);padding:16px 0;}
header.site .wrap{display:flex;align-items:center;justify-content:space-between;}
.brand{font-weight:700;font-size:18px;color:var(--ink);}
.nav a{margin-left:18px;color:var(--muted);font-size:14.5px;}
.crumb{font-size:13.5px;color:var(--muted);margin:28px 0 6px;}
.crumb a{color:var(--muted);}
h1{font-size:clamp(28px,4vw,38px);line-height:1.18;margin:6px 0 14px;}
.lede{font-size:19px;color:var(--muted);margin-bottom:30px;}
.post-list{list-style:none;margin:0;padding:0;}
.post{border-top:1px solid var(--line);padding:24px 0;}
.post:last-child{border-bottom:1px solid var(--line);}
.post h2{font-size:22px;line-height:1.3;margin:0 0 8px;}
.post h2 a{color:var(--ink);}
.post h2 a:hover{color:var(--accent);text-decoration:none;}
.post p{margin:0 0 8px;color:var(--muted);font-size:16px;}
.meta{font-size:13.5px;color:var(--muted);}
.final-cta{text-align:center;border:1px solid var(--line);border-radius:var(--radius);padding:36px 26px;margin:44px 0 30px;}
.final-cta h2{margin-top:0;font-size:22px;}
.btn{display:inline-block;padding:12px 20px;border-radius:8px;font-size:15px;font-weight:600;}
.btn-primary{background:var(--accent);color:var(--accent-ink)!important;}
.btn-primary:hover{opacity:.92;text-decoration:none;}
footer.site{border-top:1px solid var(--line);padding:24px 0;margin-top:40px;font-size:13.5px;color:var(--muted);text-align:center;}
footer.site a{color:var(--muted);}
a:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:3px;}
</style>
</head>
<body>
<header class="site">
  <div class="wrap">
    <a class="brand" href="https://questmart.online/">QuestMart</a>
    <nav class="nav">
      <a href="https://questmart.online/">Home</a>
      <a href="https://questmart.online/blog/">Blog</a>
      <a href="https://questmart.online/contact.html">Contact</a>
    </nav>
  </div>
</header>

<main class="wrap">
  <p class="crumb"><a href="https://questmart.online/">Home</a> / Blog</p>
  <h1>Guides on invoicing, freelancing and getting paid</h1>
  <p class="lede">Practical guides on invoicing, freelancing and getting paid, including in crypto.</p>

  <ul class="post-list">
{cards}
  </ul>

  <div class="final-cta">
    <h2>One file. One payment. Every invoice you will ever send.</h2>
    <p>Invoice Studio: 150+ currencies including crypto, 7 languages, 4 templates, offline and private. Pay once, $70.</p>
    <a class="btn btn-primary" href="https://questmart.online/products/invoice-studio-pro.html">See Invoice Studio Pro</a>
  </div>
</main>

<footer class="site">
  © 2026 QuestMart. <a href="https://questmart.online/">Home</a> · <a href="https://questmart.online/blog/">Blog</a>
</footer>
</body>
</html>
"""


URL_BLOCK = re.compile(r"[ \t]*<url>.*?</url>[ \t]*\n?", re.S)
LASTMOD = re.compile(r"<lastmod>\s*([^<]*?)\s*</lastmod>")


def update_sitemap(posts):
    """Touches ONLY URLs under /blog/. Everything else is left exactly as is."""
    if SITEMAP.exists():
        xml = SITEMAP.read_text(encoding="utf-8")
    else:
        xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n</urlset>\n')
    if "</urlset>" not in xml:
        warn("sitemap.xml has no </urlset>, left unchanged")
        return

    prefix = f"{BASE}/blog/"
    index_mod = max((p["modified"] for p in posts), default=date.today())
    target = {p["file"]: p["modified"] for p in posts}
    target[""] = index_mod
    target["index.html"] = index_mod
    stats = {"removed": 0, "updated": 0, "added": 0}

    def fix(m):
        block = m.group(0)
        loc = first(r"<loc>\s*(.*?)\s*</loc>", block)
        if not loc.startswith(prefix):
            return block                      # not a blog URL: untouched
        name = loc[len(prefix):]
        if name not in target:
            # a /blog/ page URL that no longer exists (renamed/deleted/noindex/bad name)
            if name.endswith(".html") or not SAFE_NAME.match(name or "x.html"):
                stats["removed"] += 1
                print(f"sitemap.xml: removed stale URL {loc}")
                return ""
            return block
        want = target[name]
        old = LASTMOD.search(block)
        old_day = parse_day(old.group(1)) if old else None
        if old_day and old_day >= want:
            return block                      # already up to date
        stats["updated"] += 1
        if old:
            return block[:old.start()] + f"<lastmod>{want.isoformat()}</lastmod>" + block[old.end():]
        return block.replace("</url>", f"  <lastmod>{want.isoformat()}</lastmod>\n  </url>")

    new_xml = URL_BLOCK.sub(fix, xml)

    existing = set(re.findall(r"<loc>\s*([^<]+?)\s*</loc>", new_xml))
    wanted = [(prefix, index_mod)] + [(prefix + p["file"], p["modified"]) for p in posts]
    add = ""
    for loc, lastmod in wanted:
        if loc not in existing and loc + "index.html" not in existing:
            add += f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lastmod.isoformat()}</lastmod>\n  </url>\n"
            stats["added"] += 1
    if add:
        new_xml = new_xml.replace("</urlset>", add + "</urlset>")

    if new_xml != xml:
        SITEMAP.write_text(new_xml, encoding="utf-8")
    print(f"sitemap.xml: added {stats['added']}, updated {stats['updated']}, "
          f"removed {stats['removed']}")


def main():
    posts = []
    for path in sorted(BLOG.glob("*.html")):
        if path.name == "index.html":
            continue
        p = read_post(path)
        if p:
            posts.append(p)
    if not posts:
        print("ERROR: no articles found, refusing to overwrite blog/index.html", file=sys.stderr)
        sys.exit(1)
    posts.sort(key=lambda p: (p["date"], p["modified"], p["file"]), reverse=True)
    out = PAGE.replace("{cards}", "\n\n".join(render_card(p) for p in posts))
    (BLOG / "index.html").write_text(out, encoding="utf-8")
    print(f"blog/index.html: {len(posts)} article(s)")
    update_sitemap(posts)


if __name__ == "__main__":
    main()
