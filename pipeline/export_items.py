# -*- coding: utf-8 -*-
"""模塊 #4 — 真數據生成器：NamingResult → 正式 items.json（前端可直接讀）

輸入兩種（可混合）：
  --jsonl  FILE   module3 SourceRunner 落庫前 dump 嘅 NamingResult（每行一個 JSON）
  --corpus DIR    HTML 快取目錄，按檔名分派：
                    bsp_detail_*.html  → module2 bsp 詳情
                    bsp_list_*.html    → module2 bsp 列表
                    kore_article_*.html→ module2 kore 文章
                    kore_index_*.html  → 跳過（索引層，政策禁止入 item）
                    dengeki_*.html     → 跳過（預告看板）

輸出：同 web/demo/data/items.json 同 schema，但：
  - views_7d = 0、price = null，並喺 _meta 標明 views_available/price_available = false
    （真熱度要等 item_view_daily；真價要等 price_ref，唔造假數）
  - 每筆帶 source_urls，可追溯

政策：
  - 冇 official_name → 唔入 items，只記入 skipped（對應 module2 guard_matchable）
  - 同 official_name 重複 → 合併 source_urls，只留一筆
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
DEMO = PROJ / "web" / "demo"

sys.path.insert(0, str(PROJ / "module1"))
sys.path.insert(0, str(PROJ / "module2"))

import bsp as bsp_parser          # noqa: E402
import kore as kore_parser        # noqa: E402
import pipeline as m2_pipeline    # noqa: E402
from aliases import resolve_ip, resolve_maker   # noqa: E402
from normalize import match_key   # noqa: E402

SKIP_PREFIX = ("kore_index", "dengeki")


def parse_html_file(path: Path) -> list[dict]:
    """一個 HTML 檔 → 若干 NamingResult dict（module2 pipeline 輸出格式）。"""
    name = path.name.lower()
    html = path.read_text(encoding="utf-8", errors="replace")
    url = f"file://{path.name}"

    if name.startswith(SKIP_PREFIX):
        return []
    if name.startswith("bsp") and "detail" in name:
        return [m2_pipeline.bsp_detail(html, url=url)]
    if name.startswith("bsp"):
        return [x["result"] for x in m2_pipeline.bsp_list(html)]
    if name.startswith("kore_article"):
        return [m2_pipeline.kore_article(html, url=url)]
    return []


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def guess_category(r: dict) -> str:
    branch = r.get("spec_branch")
    if branch == "plush_multi":
        return "plush"
    title = r.get("official_name") or ""
    if any(k in title for k in ("ぬいぐるみ", "マスコット", "ぬい", "plush")):
        return "plush"
    if any(k in title for k in ("加湿器", "ライト", "グラス", "アクリル", "タオル", "クッション")):
        return "goods"
    return "figure"


def guess_month(r: dict) -> str:
    rel = r.get("release_text") or ""
    if len(rel) >= 7 and rel[4] == "-":
        return rel[:7]
    m = re.search(r"(\d{4})年\s*(\d{1,2})月", rel)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    if len(rel) == 4 and rel.isdigit():
        return rel + "-01"
    return ""


def to_item(r: dict) -> dict | None:
    official = (r.get("official_name") or "").strip()
    if not official:
        return None                          # 政策：冇官方名唔入 item
    iid = "itm_" + hashlib.sha256(match_key(official).encode()).hexdigest()[:10]
    month = guess_month(r)
    size = r.get("size_cm")
    status = "on_sale" if (month and month <= date.today().strftime("%Y-%m")) else "announced"
    name = official
    maker = r.get("maker_code")
    if not maker and r.get("maker_jp"):
        m = resolve_maker(r["maker_jp"]); maker = m["code"] if m else None
    ipc = r.get("ip_code")
    if not ipc:
        i = resolve_ip(r.get("ip_title") or official); ipc = i["code"] if i else None
    return {
        "id": iid,
        "official_name": official,
        "raw_title": r.get("raw_title") or official,
        "maker": maker or "other",
        "brand": r.get("brand_line_code") or r.get("brand") or None,
        "ip": ipc,
        "characters": [c for c in [r.get("character_name")] if c],
        "channel": "ichiban_kuji" if r.get("is_kuji") else "prize",
        "category": guess_category(r),
        "release_month": month,
        "size_cm": size,
        "series_group": r.get("series_group"),
        "is_resale": False,
        "is_kuji_pool": bool(r.get("is_kuji")),
        "prize_tier": r.get("prize_tier"),
        "status": status,
        "views_7d": 0,                       # 真熱度等 item_view_daily
        "price": None,                       # 真價格等 price_ref
        "market_links": {
            "surugaya": "https://www.suruga-ya.jp/search?search_word=" + name,
            "mercari": "https://jp.mercari.com/search?keyword=" + name,
            "yahoo": "https://auctions.yahoo.co.jp/search/search?p=" + name,
        },
        "source_urls": [r["url"]] if r.get("url") else [],
        "is_real": True,
        "demo": False,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", type=Path)
    ap.add_argument("--corpus", type=Path)
    ap.add_argument("--out", type=Path, default=DEMO / "data" / "items.real.json")
    args = ap.parse_args()

    results: list[dict] = []
    if args.jsonl:
        results += load_jsonl(args.jsonl)
    if args.corpus:
        for p in sorted(args.corpus.glob("*.html")):
            results += parse_html_file(p)
    if not results:
        # 冇參數時用 module2 fixtures 做 smoke test（證明生成器行得通）
        fx = PROJ / "module2" / "fixtures"
        for p in sorted(fx.glob("*.html")):
            results += parse_html_file(p)

    items: dict[str, dict] = {}
    skipped: list[dict] = []
    for r in results:
        if r.get("is_item") is False or r.get("board") == "preview":
            skipped.append({"why": "preview_board", "raw_title": r.get("raw_title")})
            continue
        it = to_item(r)
        if it is None:
            skipped.append({"why": "no_official_name", "raw_title": r.get("raw_title"),
                            "warnings": r.get("warnings", [])})
            continue
        key = match_key(it["official_name"])
        if key in items:
            for u in it["source_urls"]:
                if u not in items[key]["source_urls"]:
                    items[key]["source_urls"].append(u)
            continue
        items[key] = it

    payload = {
        "_meta": {
            "generated_at": date.today().isoformat(),
            "generator": "pipeline/export_items.py",
            "source": "module2 解析 + module1 命名（真數據）",
            "counts": {"total": len(items), "skipped": len(skipped),
                       "real": len(items), "prize": 0, "kuji": 0},
            "views_available": False,
            "price_available": False,
            "ranking_label": "熱度數據未接（等 item_view_daily）",
            "privacy": "搜尋／瀏覽／收藏全部喺瀏覽器本地，唔上傳伺服器",
        },
        "items": list(items.values()),
        "preview": [],
        "skipped": skipped,
    }
    payload["_meta"]["counts"]["prize"] = sum(1 for i in items.values() if i["channel"] == "prize")
    payload["_meta"]["counts"]["kuji"] = sum(1 for i in items.values() if i["channel"] == "ichiban_kuji")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {args.out}")
    print("counts:", payload["_meta"]["counts"])
    print("skipped:", len(skipped))


if __name__ == "__main__":
    main()
