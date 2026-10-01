#!/usr/bin/env python3
"""
Publishes new blog articles automatically in THREE places, without ever
rewriting your existing templates:

  1. blog/index.html      -> a card is INSERTED for every new article
                             (existing cards/template untouched, chips counts refreshed)
  2. guides/<topic>/index.html + guides/index.html
                          -> new article is APPENDED to the matching topic list,
                             counts are fixed (nothing is removed or rewritten)
  3. sitemap.xml          -> only /blog/ URLs are touched

Run from the repository root:  python scripts/build_blog.py

Every blog/*.html file (except index.html and files marked noindex) is read:
  - <title>                          -> card title (trailing " | Brand" removed)
  - <meta name="description">        -> card text (falls back to og:description)
  - "datePublished" in the JSON-LD   -> date + sort order (newest first)
  - "dateModified"  in the JSON-LD   -> sitemap <lastmod>
  - "N minute read" in the byline    -> reading time (optional)
  - <meta name="category" content="Plants"> -> optional, forces the category
    (must be one of the names in CATEGORIES to also appear in /guides/)
"""
import html
import re
import subprocess
import sys
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote
import unicodedata

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
        "cat": categorize(path.name, title, parser.meta("category")),
    }


def fmt_date(d):
    return f"{d:%B} {d.day}, {d.year}"


CATEGORIES = [
    ("Plants", r"plant"),
    ("Food & Fridge", r"fridge|recipe|dinner|meal|grocery|breakfast|cook|food"),
    ("Invoicing & Contracts", r"invoice|contract|proposal|scope of work|scope creep|agreement|billing"),
    ("Freelancing", r"freelanc|escrow|usdt|upwork|fiverr|hire|certify"),
    ("Creators", r"creator|brand deal|sponsored|media kit|ugc|thumbnail|engagement|link-in-bio|caption|content calendar|posting|clips|platform"),
    ("Photo & AI Art", r"photo|anime|cartoon|chibi|manga|avatar|portrait|camcorder|meme|ai art|picture"),
]
DEFAULT_CAT = "More Guides"


def categorize(filename, title, override=""):
    """Category from <meta name="category"> if present, else from keywords."""
    if override.strip():
        return override.strip()
    if re.match(r"\d\d-", filename):
        return "Creators"
    hay = (filename.replace("-", " ") + " " + title).lower()
    for name, pattern in CATEGORIES:
        if re.search(pattern, hay):
            return name
    return DEFAULT_CAT


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


CARD = """<li class="card" data-cat="{cat_slug}" data-text="{search}">
      <span class="tag">{cat}</span>
      <h2><a href="{url}" lang="{lang}" dir="auto">{title}</a></h2>
      <p lang="{lang}" dir="auto">{desc}</p>
      <span class="meta">{meta}</span>
    </li>"""


def render_card(p):
    meta = fmt_date(p["date"])
    if p["minutes"]:
        meta += f" · {p['minutes']} min read"
    return CARD.format(
        url=f"{BASE}/blog/{p['file']}",
        lang=html.escape(p["lang"], quote=True),
        title=html.escape(p["title"], quote=False),
        desc=html.escape(p["desc"], quote=False),
        meta=meta,
        cat=html.escape(p["cat"], quote=False),
        cat_slug=slug(p["cat"]),
        search=html.escape((p["title"] + " " + p["desc"]).lower(), quote=True),
    )


def render_chips(posts):
    counts = {}
    for p in posts:
        counts[p["cat"]] = counts.get(p["cat"], 0) + 1
    chips = [f'<button class="chip on" data-cat="all">All <b>{len(posts)}</b></button>']
    for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        chips.append(f'<button class="chip" data-cat="{slug(name)}">'
                     f'{html.escape(name, quote=False)} <b>{n}</b></button>')
    return "\n    ".join(chips)


# Used ONLY when blog/index.html does not exist yet (first-time bootstrap).
PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Blog | QuestMart</title>
<meta name="description" content="Practical guides on AI photo styles, freelancing, invoicing, creators and everyday tools from QuestMart.">
<link rel="canonical" href="https://questmart.online/blog/">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:type" content="website">
<meta property="og:title" content="Blog | QuestMart">
<meta property="og:description" content="Practical guides on AI photo styles, freelancing, invoicing, creators and everyday tools from QuestMart.">
<meta property="og:url" content="https://questmart.online/blog/">
<meta property="og:site_name" content="QuestMart">
<meta property="og:image" content="https://questmart.online/blog/images/invoice-studio-og.jpg">
<meta name="twitter:card" content="summary_large_image">
<style>
:root{--ink:#16201d;--muted:#5d6b66;--line:#e2e9e6;--bg:#f5f8f6;--card:#fff;--accent:#0f6b52;--accent-soft:#e3f3ed;--accent-ink:#fff;--radius:16px;--maxw:1120px}
@media(prefers-color-scheme:dark){:root{--ink:#e8f0ed;--muted:#9bada6;--line:#26332f;--bg:#0f1513;--card:#161e1b;--accent:#4cc9a0;--accent-soft:#17302a;--accent-ink:#06130f}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;line-height:1.6;font-size:16.5px}
a{color:inherit;text-decoration:none}
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 20px}
header.site{background:var(--card);border-bottom:1px solid var(--line);padding:14px 0}
header.site .wrap{display:flex;align-items:center;justify-content:space-between}
.brand{font-weight:800;font-size:19px;letter-spacing:-.01em}
.nav a{margin-left:20px;color:var(--muted);font-size:14.5px}
.nav a:hover{color:var(--accent)}
.hero{padding:54px 0 26px;text-align:center}
.hero h1{font-size:clamp(30px,5vw,46px);line-height:1.12;margin:0 0 12px;letter-spacing:-.02em}
.hero p{color:var(--muted);font-size:18px;max-width:620px;margin:0 auto 24px}
.search{width:100%;max-width:460px;padding:13px 18px;border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--ink);font-size:15.5px}
.search:focus{outline:2px solid var(--accent);border-color:transparent}
.chips{display:flex;flex-wrap:wrap;gap:9px;justify-content:center;margin:22px 0 30px}
.chip{border:1px solid var(--line);background:var(--card);color:var(--ink);padding:8px 15px;border-radius:999px;font-size:14px;cursor:pointer;font-family:inherit}
.chip b{font-weight:600;color:var(--muted);margin-left:4px}
.chip:hover{border-color:var(--accent)}
.chip.on{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.chip.on b{color:inherit;opacity:.8}
.grid{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:20px}
.card{position:relative;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:24px;display:flex;flex-direction:column;gap:10px;transition:transform .15s,box-shadow .15s}
.card:hover{transform:translateY(-3px);box-shadow:0 10px 28px rgba(15,60,45,.12)}
.card.hide{display:none}
.card:first-child{grid-column:1/-1;padding:32px;background:linear-gradient(135deg,var(--accent-soft),var(--card) 70%)}
.card:first-child h2{font-size:clamp(24px,3.4vw,32px)}
.tag{align-self:flex-start;font-size:12.5px;font-weight:600;color:var(--accent);background:var(--accent-soft);padding:3px 11px;border-radius:999px}
.card h2{font-size:19.5px;line-height:1.28;margin:0;letter-spacing:-.01em}
.card h2 a::after{content:"";position:absolute;inset:0}
.card p{margin:0;color:var(--muted);font-size:15px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.card:first-child p{-webkit-line-clamp:4;font-size:16.5px}
.meta{margin-top:auto;font-size:13px;color:var(--muted)}
.empty{display:none;text-align:center;color:var(--muted);padding:40px 0}
.final-cta{text-align:center;background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:38px 26px;margin:48px 0 30px}
.final-cta h2{margin:0 0 8px;font-size:22px}
.final-cta p{color:var(--muted);margin:0 0 18px}
.btn{display:inline-block;padding:12px 22px;border-radius:10px;font-size:15px;font-weight:600;background:var(--accent);color:var(--accent-ink)}
.btn:hover{opacity:.9}
footer.site{border-top:1px solid var(--line);padding:24px 0;margin-top:30px;font-size:13.5px;color:var(--muted);text-align:center}
:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
@media(prefers-reduced-motion:reduce){.card{transition:none}}
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
  <section class="hero">
    <h1>The QuestMart Blog</h1>
    <p>Practical guides on AI photo styles, freelancing, invoicing, creators and everyday tools.</p>
    <input class="search" id="q" type="search" placeholder="Search articles..." aria-label="Search articles">
  </section>

  <div class="chips" id="chips">
    {chips}
  </div>

  <ul class="grid" id="grid">
    {cards}
  </ul>
  <p class="empty" id="empty">No articles match your search.</p>

  <div class="final-cta">
    <h2>One file. One payment. Every invoice you will ever send.</h2>
    <p>Invoice Studio: 150+ currencies including crypto, 7 languages, 4 templates, offline and private. Pay once, $70.</p>
    <a class="btn" href="https://questmart.online/products/invoice-studio-pro.html">See Invoice Studio Pro</a>
  </div>
</main>

<footer class="site">
  © 2026 QuestMart. <a href="https://questmart.online/">Home</a> · <a href="https://questmart.online/blog/">Blog</a>
</footer>
<script>
(function(){
  var cat="all",q=document.getElementById("q"),cards=[].slice.call(document.querySelectorAll("#grid .card")),
      chips=[].slice.call(document.querySelectorAll(".chip")),empty=document.getElementById("empty");
  function run(){
    var t=q.value.trim().toLowerCase(),n=0;
    cards.forEach(function(c){
      var ok=(cat==="all"||c.dataset.cat===cat)&&(!t||c.dataset.text.indexOf(t)>-1);
      c.classList.toggle("hide",!ok);if(ok)n++;
    });
    empty.style.display=n?"none":"block";
  }
  chips.forEach(function(b){b.addEventListener("click",function(){
    cat=b.dataset.cat;chips.forEach(function(x){x.classList.toggle("on",x===b)});run();
  })});
  q.addEventListener("input",run);
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# 1) blog/index.html : INSERT new cards only, never rewrite the template
# ---------------------------------------------------------------------------
GRID = re.compile(r'(<ul\b[^>]*\bid="grid"[^>]*>)(.*?)(\s*</ul>)', re.S | re.I)
CARD_BLOCK = re.compile(r"<li\b.*?</li>", re.S | re.I)
CHIPS = re.compile(r'(<div\b[^>]*\bid="chips"[^>]*>)(.*?)(</div>)', re.S | re.I)


def card_date(block):
    """Reads the date shown in an existing card ('October 1, 2026 · 5 min read')."""
    m = re.search(r'<span class="meta">\s*([^<·]*?)\s*(?:·[^<]*)?</span>', block)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1).strip(), "%B %d, %Y").date()
    except ValueError:
        return None


def chips_from_cards(blocks):
    counts, names = {}, {}
    for b in blocks:
        c = re.search(r'data-cat="([^"]*)"', b)
        t = re.search(r'<span class="tag">(.*?)</span>', b, re.S)
        if not c or not t:
            continue
        counts[c.group(1)] = counts.get(c.group(1), 0) + 1
        names[c.group(1)] = t.group(1).strip()
    chips = [f'<button class="chip on" data-cat="all">All <b>{len(blocks)}</b></button>']
    for key, n in sorted(counts.items(), key=lambda kv: (-kv[1], names[kv[0]])):
        chips.append(f'<button class="chip" data-cat="{key}">{names[key]} <b>{n}</b></button>')
    return "\n    ".join(chips)


def update_blog_index(posts):
    idx = BLOG / "index.html"

    # First-time bootstrap only: the page does not exist yet.
    if not idx.exists():
        out = (PAGE.replace("{chips}", render_chips(posts))
                   .replace("{cards}", "\n\n    ".join(render_card(p) for p in posts)))
        idx.write_text(out, encoding="utf-8")
        print(f"blog/index.html: created with {len(posts)} article(s)")
        return

    text = idx.read_text(encoding="utf-8")
    m = GRID.search(text)
    if not m:
        warn('blog/index.html: <ul id="grid"> not found, page left unchanged')
        return

    blocks = CARD_BLOCK.findall(m.group(2))
    present = set(re.findall(r"/blog/([A-Za-z0-9._-]+\.html)", m.group(2)))
    new = [p for p in posts if p["file"] not in present]

    # Warn about cards pointing to files that no longer exist (never auto-removed).
    for f in sorted(present):
        if not (BLOG / f).exists():
            warn(f"blog/index.html has a card for '{f}' but the file does not exist")

    if not new:
        print("blog/index.html: no new articles, page left unchanged")
        return

    # Insert each new card at the right place (newest first), existing cards untouched.
    for p in new:  # posts are already sorted newest first
        card = render_card(p)
        pos = len(blocks)
        for i, b in enumerate(blocks):
            d = card_date(b)
            if d is not None and d <= p["date"]:
                pos = i
                break
        blocks.insert(pos, card)

    items = "\n\n".join("    " + b.lstrip() for b in blocks)
    new_text = text[:m.start(2)] + "\n" + items + "\n  </ul>" + text[m.end(3):]

    # Refresh only the category chips (counts), built from the cards themselves.
    cm = CHIPS.search(new_text)
    if cm:
        new_text = (new_text[:cm.start(2)] + "\n    " + chips_from_cards(blocks)
                    + "\n  " + new_text[cm.end(2):])
    else:
        warn('blog/index.html: <div id="chips"> not found, chips not updated')

    idx.write_text(new_text, encoding="utf-8")
    print(f"blog/index.html: added {len(new)} new article(s), total {len(blocks)}")


# ---------------------------------------------------------------------------
# 2) sitemap.xml : only /blog/ URLs
# ---------------------------------------------------------------------------
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
            # a /blog/ article URL that no longer exists (renamed/deleted/noindex)
            if name.endswith(".html"):
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


# ---------------------------------------------------------------------------
# 3) guides/ : APPEND new articles, never remove or rewrite existing entries
# ---------------------------------------------------------------------------
GUIDES = ROOT / "guides"
GUIDE_TOPICS = {
    "Photo & AI Art": "ai-photo",
    "Food & Fridge": "fridge-chef",
    "Plants": "plant-care",
    "Freelancing": "freelance-and-crypto-payments",
    "Invoicing & Contracts": "invoicing-and-contracts",
    "Creators": "creator-tools",
}
GUIDE_LIST = re.compile(
    r'(<h2[^>]*>[^<]*?\bguides\s*\()(\d+)(\)[^<]*</h2>\s*<ul[^>]*>)(.*?)(</ul>)', re.S | re.I)


def guide_title(t):
    return re.sub(r"\s*\((?:[^)]*\b2026\b[^)]*)\)\s*$", "", t).strip()


def guide_blurb(desc, limit=120):
    s = re.split(r"(?<=[.!?])\s", desc.strip())[0] if desc else ""
    if len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    return s


def update_guides(posts):
    """Appends NEW articles to the matching /guides/<topic>/ page and fixes the counts.
    Never removes or rewrites existing entries. If a page layout is not recognized,
    it is left untouched and a warning is printed."""
    if not GUIDES.is_dir():
        return

    for p in posts:
        if p["cat"] not in GUIDE_TOPICS:
            warn(f"{p['file']}: category '{p['cat']}' has no /guides/ page, "
                 f"so it is not listed there. Add <meta name=\"category\" "
                 f"content=\"...\"> with one of: {', '.join(GUIDE_TOPICS)}")

    pages, present = {}, set()
    for topic in sorted(set(GUIDE_TOPICS.values())):
        f = GUIDES / topic / "index.html"
        if f.exists():
            text = f.read_text(encoding="utf-8")
            pages[topic] = (f, text)
            present |= set(re.findall(r"/blog/([A-Za-z0-9._-]+\.html)", text))

    counts = {}
    for topic, (f, text) in pages.items():
        new = [p for p in posts if GUIDE_TOPICS.get(p["cat"]) == topic and p["file"] not in present]
        m = GUIDE_LIST.search(text)
        if not m:
            warn(f"guides/{topic}: article list not recognized, page left unchanged")
            continue
        items = m.group(4)
        opens = re.findall(r"<li\b[^>]*>", items)
        open_tag = opens[-1] if opens else "<li>"
        add = ""
        for p in new:
            blurb = guide_blurb(p["desc"])
            add += (f'\n    {open_tag}<a href="{BASE}/blog/{p["file"]}">'
                    f'{html.escape(guide_title(p["title"]), quote=False)}</a>'
                    f'{" – " + html.escape(blurb, quote=False) if blurb else ""}</li>')
        total = len(opens) + len(new)
        counts[topic] = total
        if not new:
            continue
        new_text = (text[:m.start()] + m.group(1) + str(total) + m.group(3)
                    + items.rstrip() + add + "\n  " + m.group(5) + text[m.end():])
        if new_text != text:
            f.write_text(new_text, encoding="utf-8")
            print(f"guides/{topic}: added {len(new)} guide(s), total {total}")

    hub = GUIDES / "index.html"
    if hub.exists() and counts:
        old = hub.read_text(encoding="utf-8")
        h = old
        for topic, n in counts.items():
            h = re.sub(r'(href="[^"]*/guides/' + re.escape(topic) + r'/?"[^>]*>(?:(?!</a>).)*?)(\d+)(\s*guides)',
                       lambda m: m.group(1) + str(n) + m.group(3), h, count=1, flags=re.S)
        if h != old:
            hub.write_text(h, encoding="utf-8")
            print("guides/index.html: counts updated")


# ---------------------------------------------------------------------------
def fix_unsafe_names():
    """Auto-rename files whose names are not URL-safe (spaces, ':', '(1)', non-English)."""
    for path in sorted(BLOG.glob("*.html")):
        if path.name == "index.html" or SAFE_NAME.match(path.name):
            continue
        stem = unicodedata.normalize("NFKD", path.stem).encode("ascii", "ignore").decode()
        stem = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-") or "article"
        new, n = f"{stem}.html", 2
        while (BLOG / new).exists():
            new, n = f"{stem}-{n}.html", n + 1
        text = path.read_text(encoding="utf-8")
        for old in {path.name, quote(path.name)}:
            text = text.replace(old, new)
        (BLOG / new).write_text(text, encoding="utf-8")
        path.unlink()
        print(f"::notice::Renamed '{path.name}' to '{new}'")


def main():
    fix_unsafe_names()
    posts = []
    for path in sorted(BLOG.glob("*.html")):
        if path.name == "index.html":
            continue
        p = read_post(path)
        if p:
            posts.append(p)
    if not posts:
        print("ERROR: no articles found, refusing to touch blog/index.html", file=sys.stderr)
        sys.exit(1)
    posts.sort(key=lambda p: (p["date"], p["modified"], p["file"]), reverse=True)

    update_blog_index(posts)      # 1) /blog/
    update_sitemap(posts)         # 2) sitemap.xml (blog URLs only)
    try:
        update_guides(posts)      # 3) /guides/
    except Exception as e:  # the guides update must never break the blog build
        warn(f"guides update skipped: {e}")


if __name__ == "__main__":
    main()



