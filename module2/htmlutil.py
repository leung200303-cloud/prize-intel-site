# -*- coding: utf-8 -*-
"""極簡 HTML 工具（唔使第三方依賴）。

只做呢個項目實際需要嘅嘢：
  - 抽 ld+json（bsp 官方商品名／作品／角色都喺呢度）
  - 抽指定 tag 嘅平衡區塊（唔用 regex 硬食嵌套）
  - dl/dt/dd、table/tr/th/td
  - 文字化：<br> → "|"、去 tag、去 script/style
"""
from __future__ import annotations

import html as htmlmod
import json
import re

_TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?(/?)>")


def class_of(tag_html: str) -> str:
    m = re.search(r'class\s*=\s*"([^"]*)"', tag_html, re.I)
    return m.group(1) if m else ""


def text_of(fragment: str | None, br_sep: str = "|") -> str:
    """去 tag 取文字；<br> 變分隔符，方便之後按行解析。"""
    if not fragment:
        return ""
    s = re.sub(r"<script\b.*?</script>", " ", fragment, flags=re.S | re.I)
    s = re.sub(r"<style\b.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>", br_sep, s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = htmlmod.unescape(s)
    s = re.sub(r"[ \t\u3000]+", " ", s)
    s = re.sub(r"\s*\|\s*", "|", s)
    return s.strip()


def element_blocks(html: str, tag: str, cls: str | None = None) -> list[str]:
    """抽某 tag 嘅完整（平衡）區塊；cls 係 class token 精確匹配。"""
    out: list[str] = []
    for m in _TAG_RE.finditer(html):
        if m.group(1) or m.group(2).lower() != tag.lower():
            continue
        if cls and cls not in class_of(m.group(0)).split():
            continue
        depth, end, i = 0, None, m.start()
        for mm in _TAG_RE.finditer(html, i):
            closing, name, self_close = mm.group(1), mm.group(2).lower(), mm.group(3)
            if name != tag.lower():
                continue
            if closing:
                depth -= 1
            elif not self_close:
                depth += 1
            if depth == 0:
                end = mm.end()
                break
        if end:
            out.append(html[m.start():end])
    return out


def ld_json_blocks(html: str) -> list[dict]:
    """抽所有 application/ld+json，回傳已 parse 嘅 dict list（壞咗就跳過）。"""
    out: list[dict] = []
    for m in re.finditer(
            r'<script[^>]+type\s*=\s*"application/ld\+json"[^>]*>(.*?)</script>',
            html, re.S | re.I):
        raw = m.group(1).strip()
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            try:  # 有啲頁面 JSON 前後有雜物
                obj = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
            except (ValueError, json.JSONDecodeError):
                continue
        if isinstance(obj, list):
            out.extend(x for x in obj if isinstance(x, dict))
        elif isinstance(obj, dict):
            out.append(obj)
    return out


def dl_pairs(html: str, cls: str | None = None) -> tuple[str, list[tuple[str, str]]]:
    """回傳 (原文, [(dt, dd)])。"""
    blocks = element_blocks(html, "dl", cls) if cls else element_blocks(html, "dl")
    if not blocks:
        return "", []
    dts = element_blocks(blocks[0], "dt")
    dds = element_blocks(blocks[0], "dd")
    pairs = [(text_of(a, br_sep="|"), text_of(b, br_sep="|"))
             for a, b in zip(dts, dds)]
    return blocks[0], pairs


def table_rows(table_html: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in element_blocks(table_html, "tr"):
        cells = re.findall(r"<(th|td)\b[^>]*>(.*?)</\1>", tr, re.S | re.I)
        if cells:
            rows.append([text_of(c[1]).strip() for c in cells])
    return rows


def tables_with(html: str, must_have: str) -> list[list[list[str]]]:
    """回傳所有 table 嘅 rows，只保留含 must_have 嘅（例「商品名」）。"""
    out = []
    for t in element_blocks(html, "table"):
        rows = table_rows(t)
        if any(must_have in c for r in rows for c in r):
            out.append(rows)
    return out


def anchors(html: str, href_substr: str = "") -> list[tuple[str, str]]:
    """回傳 [(href, 內部文字)]。"""
    out = []
    for m in re.finditer(r'<a\b[^>]*href\s*=\s*"([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        href = m.group(1)
        if href_substr and href_substr not in href:
            continue
        out.append((href, text_of(m.group(2))))
    return out
