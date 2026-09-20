#!/usr/bin/env python3
"""
Rebuilds blog/index.html and adds missing blog URLs to sitemap.xml.

Run from the repository root:  python scripts/build_blog.py

Every blog/*.html file (except index.html and files marked noindex) becomes a
card on the blog page. The script reads, from each article:
  - <title>                          -> card title (" | QuestMart" is removed)
  - <meta name="description">        -> card text
  - "datePublished" in the JSON-LD   -> date + sort order (newest first)
  - "N minute read" in the byline    -> reading time (optional)
"""
import html
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "blog"
SITEMAP = ROOT / "sitemap.xml"
BASE = "https://questmart.online"
SITE_NAME = "QuestMart"


def first(pattern, text, flags=re.S | re.I):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else ""


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


def read_post(path):
    text = path.read_text(encoding="utf-8")
    if re.search(r'<meta[^>]+name=["\']robots["\'][^>]+noindex', text, re.I):
        return None
    title = html.unescape(first(r"<title>(.*?)</title>", text))
    title = re.sub(r"\s*\|\s*" + re.escape(SITE_NAME) + r"\s*$", "", title)
    if not title:
        print(f"WARNING: {path.name} has no <title>, skipped", file=sys.stderr)
        return None
    desc = html.unescape(first(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']', text))
    published = first(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})', text)
    modified = first(r'"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})', text)
    try:
        d = datetime.strptime(published, "%Y-%m-%d").date()
    except ValueError:
        d = git_date(path)
    try:
        dm = datetime.strptime(modified, "%Y-%m-%d").date()
    except ValueError:
        dm = d
    minutes = first(r"(\d+)\s*(?:minute|min)\s*read", text)
    lang = first(r"<html[^>]*\blang=[\"']([^\"']+)", text) or "en"
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


def update_sitemap(posts):
    if SITEMAP.exists():
        xml = SITEMAP.read_text(encoding="utf-8")
    else:
        xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n</urlset>\n')
    if "</urlset>" not in xml:
        print("WARNING: sitemap.xml has no </urlset>, left unchanged", file=sys.stderr)
        return
    existing = set(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml))
    wanted = [(f"{BASE}/blog/", max((p["modified"] for p in posts), default=date.today()))]
    wanted += [(f"{BASE}/blog/{p['file']}", p["modified"]) for p in posts]
    add = ""
    for loc, lastmod in wanted:
        if loc not in existing and loc + "index.html" not in existing:
            add += f"  <url>\n    <loc>{loc}</loc>\n    <lastmod>{lastmod.isoformat()}</lastmod>\n  </url>\n"
    if add:
        xml = xml.replace("</urlset>", add + "</urlset>")
        SITEMAP.write_text(xml, encoding="utf-8")
        print(f"sitemap.xml: added {add.count('<url>')} URL(s)")
    else:
        print("sitemap.xml: nothing to add")


def main():
    posts = []
    for path in sorted(BLOG.glob("*.html")):
        if path.name == "index.html":
            continue
        p = read_post(path)
        if p:
            posts.append(p)
    posts.sort(key=lambda p: (p["date"], p["modified"], p["file"]), reverse=True)
    out = PAGE.replace("{cards}", "\n\n".join(render_card(p) for p in posts))
    (BLOG / "index.html").write_text(out, encoding="utf-8")
    print(f"blog/index.html: {len(posts)} article(s)")
    update_sitemap(posts)


if __name__ == "__main__":
    main()
