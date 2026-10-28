# -*- coding: utf-8 -*-
"""bsp-prize 解析器：列表頁 + 商品詳情頁（三種 spec 分支）。

實測 selector（2026-10-28，Playwright 讀真 DOM）：
  列表卡  div.topProducts_item[data-new_item_id] > a[href="/item/N/"]
            p.topProducts_name  = 商品名（未加工）
            p.topProducts_note  = 發售文字（含 <br>）
  詳情    script[type=application/ld+json]  → BreadcrumbList（⚠️ くじ 頁有兩個：
            一個係作品鏈、一個係角色鏈，要揀含 /title/IP 嗰個）
          dl.productDetail_spec > dt「商品仕様」+ dd（<br> 分行）
          div.productDetail_body > p = 描述
  冇 JAN／品番（實測 4 頁全掃零命中），所以唔可能有 L1 去重。

spec 三分支（實測）：
  figure      ・全4種 / ・約10cm
  plush_multi ・全3種 / ・ピカチュウ：約15cm、ドーブル：約16cm…
  kuji        ■発売日：… / ■メーカー希望小売価格：1回10,000円（税込）
"""
from __future__ import annotations

import re

from htmlutil import (anchors, dl_pairs, element_blocks, ld_json_blocks,
                      text_of)

ITEM_ID_RE = re.compile(r"/item/(\d+)/")
DATE_RE = re.compile(
    r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日[（(]?[^）)<]{0,6}[）)]?\s*より\s*順次\s*(?:登場|発売)予定")
DATE_MONTH_RE = re.compile(r"(\d{4})年\s*(\d{1,2})月[^<]{0,12}(?:発売|発送)")


# --------------------------------------------------------------------- spec
def detect_spec_branch(spec_text: str | None) -> str:
    """分三支：figure / plush_multi / kuji / unknown。"""
    if not spec_text:
        return "unknown"
    t = spec_text.replace("|", " ")
    if ("発売日" in t and "1回" in t) or "希望小売価格" in t:
        return "kuji"
    sizes = re.findall(r"約\s*(\d+(?:\.\d+)?)\s*cm", t)
    if len(set(sizes)) >= 2:
        return "plush_multi"
    if re.search(r"全\s*\d+\s*種", t) or sizes:
        return "figure"
    return "unknown"


def split_spec_lines(spec_text: str | None) -> list[str]:
    if not spec_text:
        return []
    return [ln.strip() for ln in spec_text.split("|") if ln.strip()]


def parse_spec_branches(spec_text: str | None) -> dict:
    """按分支輸出，**唔強行統一格式**：原文一律保留喺 raw_lines / size_text。"""
    branch = detect_spec_branch(spec_text)
    lines = split_spec_lines(spec_text)
    out = {
        "spec_branch": branch,
        "raw_lines": lines,
        "kinds": None,
        "size_cm": None,
        "size_text": None,
        "release_text": None,
        "price_per_play": None,
    }
    body = " ".join(lines)

    if branch == "kuji":
        m = re.search(r"発売日\s*[:：]\s*([^|]+)", body)
        if m:
            out["release_text"] = m.group(1).strip()
        m = re.search(r"1回\s*(\d[\d,]*)\s*円", body)
        if m:
            out["price_per_play"] = int(m.group(1).replace(",", ""))
        return out

    m = re.search(r"全\s*(\d+)\s*種", body)
    if m:
        out["kinds"] = int(m.group(1))

    if branch == "plush_multi":
        # 多角色多尺寸：原文完整保留，size_cm 交 module1 取最大值
        sizes = re.findall(r"約\s*(\d+(?:\.\d+)?)\s*cm", body)
        out["size_cm"] = max(float(s) for s in sizes) if sizes else None
        out["size_text"] = "、".join(ln for ln in lines if "cm" in ln)
        return out

    sizes = re.findall(r"約\s*(\d+(?:\.\d+)?)\s*cm", body)
    if sizes:
        out["size_cm"] = float(sizes[0])
        out["size_text"] = lines[0] if lines else body
    return out


# --------------------------------------------------------------------- 列表
def parse_list(html: str) -> list[dict]:
    """解析任何含 topProducts 卡嘅 bsp 列表頁（トップ / schedule / search）。

    回傳 [{item_id, detail_url, item_name, note_text, release_text}]
    """
    items: list[dict] = []
    for block in element_blocks(html, "div", "topProducts_item"):
        m_id = re.search(r'data-new_item_id\s*=\s*"(\d+)"', block)
        m_href = ITEM_ID_RE.search(block)
        if not m_href:
            continue
        item_id = m_href.group(1)          # 用 /item/N/ 嘅 N（正式商品 ID）
        internal_id = m_id.group(1) if m_id else None   # data-new_item_id（bsp 內部序號）
        name = ""
        m = re.search(r'class="topProducts_name"[^>]*>(.*?)</p>', block, re.S)
        if m:
            name = text_of(m.group(1))
        note = ""
        m = re.search(r'class="topProducts_note"[^>]*>(.*?)</p>', block, re.S)
        if m:
            note = text_of(m.group(1))
        items.append({
            "item_id": item_id,
            "bsp_internal_id": internal_id,
            "detail_url": f"https://bsp-prize.jp/item/{item_id}/",
            "item_name": name,
            "note_text": note,
            "release_text": note.split("|")[0].strip() if note else None,
        })

    if items:
        return items

    # ---- fallback：唔同版型嘅列表頁，用 anchor + 就近文字
    seen: set[str] = set()
    for href, _text in anchors(html, "/item/"):
        m = ITEM_ID_RE.search(href)
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        items.append({
            "item_id": m.group(1),
            "detail_url": f"https://bsp-prize.jp/item/{m.group(1)}/",
            "item_name": "",
            "note_text": "",
            "release_text": None,
        })
    return items


# --------------------------------------------------------------------- 詳情
def parse_breadcrumbs(html: str) -> dict:
    """抽 breadcrumb：分開「作品鏈」同「角色鏈」（くじ 頁會有兩條）。"""
    blocks = [b for b in ld_json_blocks(html) if b.get("@type") == "BreadcrumbList"]
    ip_names: list[str] = []
    ip_title = None
    character_name = None
    product_name = None

    for b in blocks:
        elems = b.get("itemListElement") or []
        entries = []
        for e in elems:
            item = e.get("item") or {}
            entries.append({"name": item.get("name"), "id": item.get("@id", "")})
        if not entries:
            continue
        if product_name is None:
            product_name = entries[-1].get("name")
        for ent in entries:
            eid, name = ent["id"], ent["name"]
            if "/title/IP" in eid:
                ip_title = name
            elif "/character/CH" in eid:
                character_name = name
        if not ip_names:
            ip_names = [e["name"] for e in entries if e.get("name")]

    return {
        "product_name": product_name,
        "ip_title": ip_title,
        "character_name": character_name,
        "breadcrumb_names": ip_names,   # 作品鏈（唔混角色鏈）
        "block_count": len(blocks),
    }


def parse_detail(html: str) -> dict:
    crumb = parse_breadcrumbs(html)

    _, pairs = dl_pairs(html, "productDetail_spec")
    spec_text = "|".join(v for _k, v in pairs) if pairs else None
    if not spec_text:
        m = re.search(r'class="productDetail_spec"[^>]*>(.*?)</dl>', html, re.S)
        spec_text = text_of(m.group(1)) if m else None

    body_text = ""
    m = re.search(r'class="productDetail_body"[^>]*>(.*?)</div>', html, re.S)
    if m:
        body_text = text_of(m.group(1))

    plain = text_of(html)
    m = DATE_RE.search(plain)
    release_text = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None
    if not release_text:
        m2 = DATE_MONTH_RE.search(plain)
        if m2:
            release_text = f"{m2.group(1)}-{int(m2.group(2)):02d}"

    spec = parse_spec_branches(spec_text)
    m_id = ITEM_ID_RE.search(html)
    return {
        "product_id": m_id.group(1) if m_id else None,
        "product_name": crumb["product_name"],
        "ip_title": crumb["ip_title"],
        "character_name": crumb["character_name"],
        "breadcrumb_names": crumb["breadcrumb_names"],
        "breadcrumb_blocks": crumb["block_count"],
        "spec_text": spec_text,
        "spec_branch": spec["spec_branch"],
        "spec": spec,
        "body_text": body_text,
        "release_text": release_text,
        "has_jan": bool(re.search(r"JAN|gtin|品番|バーコード", plain, re.I)),
    }
