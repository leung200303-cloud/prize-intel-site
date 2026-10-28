# -*- coding: utf-8 -*-
"""コレトレ（kore-tore.com）解析器。

實測 selector（2026-10-28）：
  文章頁  h1 = 文章標題（**唔係**官方商品名）
          div.post_content > table（無 class）
            <tr><th>作品名</th><td>鬼滅の刃</td></tr>
            <tr><th>商品名</th><td>アニメ「鬼滅の刃」 MAXIMATIC GIYU TOMIOKAⅡ</td></tr>
            <tr><th>種類</th><td>全1種</td></tr>
            <tr><th>サイズ</th><td>約19cm</td></tr>
            <tr><th>メーカー</th><td>バンプレスト</td></tr>
          ⚠️ 只可用 spec 表「商品名」，唔可以用 h1。

  月別一覽  prize-latest-figure/ 等頁面只有文章標題，**冇 spec 表**
            → 呢層只做索引（index_only），強制跳轉入文章頁先抽 official_name。
"""
from __future__ import annotations

import re

from htmlutil import element_blocks, tables_with, text_of

ARTICLE_HREF_RE = re.compile(r"^https?://kore-tore\.com/[a-z0-9\-]+/$")
NON_ARTICLE = {
    "/", "/about-our-site/", "/prize-help-guide/", "/privacy-policy/",
    "/inquiry/", "/feed/", "/prize-latest/", "/prize-latest-figure/",
    "/prize-latest-plush/", "/prize-latest-goods/",
}


def parse_index(html: str) -> list[dict]:
    """月別一覽／分類頁 → 只抽文章連結，**唔抽任何商品欄位**。

    回傳 [{detail_url, index_title, is_index_only: True}]
    """
    out: list[dict] = []
    seen: set[str] = set()
    for m in re.finditer(r'<a\b[^>]*href\s*=\s*"([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        href = m.group(1)
        if not ARTICLE_HREF_RE.match(href):
            continue
        if href.replace("https://kore-tore.com", "") in NON_ARTICLE:
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append({
            "detail_url": href,
            "index_title": text_of(m.group(2))[:120],
            "is_index_only": True,
        })
    return out


def parse_article(html: str) -> dict:
    """文章頁 → module1 extract_kore_tore 需要嘅 payload。

    spec 表可能有多個，揀含「商品名」嘅嗰個。
    """
    m = element_blocks(html, "h1")
    raw_title = text_of(m[0]) if m else ""
    if not raw_title:
        t = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
        raw_title = text_of(t.group(1)).split("|")[0].strip() if t else ""

    spec_rows: list[list[str]] = []
    for rows in tables_with(html, "商品名"):
        if any(r and r[0] == "商品名" for r in rows):
            spec_rows = rows
            break

    body_text = ""
    content = element_blocks(html, "div", "post_content")
    if content:
        paras = element_blocks(content[0], "p")
        body_text = " ".join(text_of(p) for p in paras[:6])

    # 發售日：文章正文有「2026年10月29日(木)より…登場予定」
    plain = text_of(html)
    m = re.search(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日", plain)
    release_text = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None

    return {
        "raw_title": raw_title,
        "spec_rows": spec_rows or None,
        "body_text": body_text,
        "release_text": release_text,
        "has_spec_table": bool(spec_rows),
    }
