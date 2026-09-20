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
