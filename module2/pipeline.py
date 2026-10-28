# -*- coding: utf-8 -*-
"""模塊 #2 pipeline：HTML → 原始欄位 → module1 NamingResult。

硬性政策（對應 Step 4 約束）：
  1. 全程經 module1 extract.py，official_name 係唯一去重輸入
  2. bsp 三種 spec 分支分開處理，size_text 保留原文
  3. コレトレ 一覽頁只做索引（index_only），**強制跳文章頁**先可以有 official_name
  4. 電撃PF 只做預告看板（board=preview），唔入正式 item
  5. 模塊 #2 唔做角色抽取、唔做 upsert
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "module1"))
sys.path.insert(0, str(HERE))

import bsp as bsp_parser            # noqa: E402
import kore as kore_parser          # noqa: E402
from aliases import resolve_ip      # noqa: E402
from extract import (NamingResult, extract_bsp, extract_dengeki,   # noqa: E402
                     extract_kore_tore)
from htmlutil import element_blocks, text_of   # noqa: E402

MAKER_PREFIX_RE = re.compile(
    r"^(エイコー|フリュー|タイトー|セガ\s?フェイブ|BANDAI SPIRITS|バンダイスピリッツ|"
    r"システムサービス|コナミアーケードゲームス)\s*[:：]\s*(.+)$")

POLICY = {
    "bsp-prize": {
        "list": "卡片商品名可信，但 spec 要入詳情頁",
        "detail": "官方商品名 + 三分支 spec",
        "matchable_from_list": True,
        "needs_detail_for_size": True,
    },
    "kore-tore": {
        "index": "只做索引，唔可以有 official_name，禁止 L2",
        "article": "用 spec 表「商品名」，h1 只做 raw_title",
        "matchable_from_index": False,
    },
    "dengeki-prizefair": {
        "role": "預告看板 only（board=preview）",
        "matchable": False,
    },
}


class PolicyViolation(RuntimeError):
    """當有人試圖用索引／預告資料做自動比對時拋出。"""


def _result_dict(r: NamingResult) -> dict:
    d = r.to_dict()
    d["status"] = "index_only" if not d["ready_for_matching"] else "ok"
    return d


# --------------------------------------------------------------------- bsp
def bsp_list(html: str) -> list[dict]:
    out = []
    for row in bsp_parser.parse_list(html):
        r = extract_bsp(raw_title=row["item_name"],
                        breadcrumb=None,
                        title_tag=None,
                        spec_text=None,
                        hints=None,
                        official_name_hint=row["item_name"] or None)
        rd = _result_dict(r)
        rd["release_text"] = row.get("release_text")
        rd["url"] = row.get("detail_url")
        out.append({
            "result": rd,
            "list_meta": row,
            "needs_detail": True,     # size / spec_branch 一定要入詳情頁
        })
    return out


def bsp_detail(html: str, url: str | None = None) -> dict:
    p = bsp_parser.parse_detail(html)
    hints = {}
    if p.get("ip_title"):
        ip = resolve_ip(p["ip_title"])
        if ip:
            hints["ip_code"] = ip["code"]
    r = extract_bsp(
        raw_title=p.get("product_name") or "",
        breadcrumb=p.get("breadcrumb_names") or None,
        title_tag=None,
        spec_text=p.get("spec_text"),
        body_text=p.get("body_text"),
        hints=hints or None,
        official_name_hint=p.get("product_name"),
    )
    d = _result_dict(r)
    d["spec_branch"] = p["spec_branch"]
    d["spec"] = {
        "kinds": p["spec"].get("kinds"),
        "size_cm": p["spec"].get("size_cm"),
        "size_text": p["spec"].get("size_text"),
        "release_text": p["spec"].get("release_text"),
        "price_per_play": p["spec"].get("price_per_play"),
        "raw_lines": p["spec"].get("raw_lines"),
    }
    d["release_text"] = p.get("release_text")
    d["character_name"] = p.get("character_name")
    d["breadcrumb_blocks"] = p.get("breadcrumb_blocks")
    d["has_jan"] = p.get("has_jan")
    d["product_id"] = p.get("product_id")
    d["url"] = url
    return d


# --------------------------------------------------------------------- コレトレ
def kore_index(html: str) -> list[dict]:
    """一覽頁 → 只回連結。任何欄位都唔抽，杜絕用殘缺數據跑 L2。"""
    return kore_parser.parse_index(html)


def kore_article(html: str, url: str | None = None) -> dict:
    p = kore_parser.parse_article(html)
    r = extract_kore_tore(raw_title=p["raw_title"],
                          spec_rows=p["spec_rows"],
                          body_text=p.get("body_text"))
    d = _result_dict(r)
    d["has_spec_table"] = p["has_spec_table"]
    d["release_text"] = p.get("release_text")
    d["url"] = url
    return d


# --------------------------------------------------------------------- 電撃PF
def dengeki_preview(html: str) -> list[dict]:
    """預告看板：只抽「廠商：描述」行，明確標記 is_item=False。"""
    out: list[dict] = []
    seen: set[str] = set()
    for tag in ("p", "li", "h3", "h4", "dt"):
        for blk in element_blocks(html, tag):
            t = text_of(blk)
            m = MAKER_PREFIX_RE.match(t)
            if not m or t in seen:
                continue
            seen.add(t)
            r = extract_dengeki(t)
            d = _result_dict(r)
            d["maker_text"] = m.group(1)
            d["description"] = m.group(2)
            d["board"] = "preview"
            d["is_item"] = False
            out.append(d)
    return out


# --------------------------------------------------------------------- 政策
def guard_matchable(result: dict, *, stage: str) -> None:
    """自動比對前嘅最後一道閘。"""
    if result.get("is_item") is False or result.get("board") == "preview":
        raise PolicyViolation(f"{stage}: 預告看板資料唔准入 item 比對")
    if not result.get("official_name"):
        raise PolicyViolation(f"{stage}: 冇 official_name，唔准自動合併")
    if result.get("status") == "index_only":
        raise PolicyViolation(f"{stage}: 索引層資料唔准自動合併")


def summarize(source: str, rows: list[dict]) -> dict:
    """一個源頭跑完後嘅統計，餵去 ingest_run。"""
    n = len(rows)
    matchable = sum(1 for r in rows if r.get("official_name"))
    return {
        "source": source,
        "total": n,
        "with_official_name": matchable,
        "coverage": round(matchable / n, 3) if n else 0.0,
        "warnings": sorted({w for r in rows for w in r.get("warnings", [])}),
    }
