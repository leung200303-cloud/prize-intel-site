# -*- coding: utf-8 -*-
"""模塊 #2 測試：HTML 解析 + 政策閘 + 同 module1 整合。

用法：python test_module2.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "module1"))

import bsp as bsp_parser                                   # noqa: E402
import kore as kore_parser                                 # noqa: E402
import pipeline                                             # noqa: E402
from htmlutil import (dl_pairs, ld_json_blocks, table_rows,  # noqa: E402
                      tables_with)

FIX = HERE / "fixtures"
results: list[tuple[str, bool, str]] = []


def read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def check(name: str, cond, detail: str = "") -> None:
    results.append((name, bool(cond), detail))


def eq(name: str, got, want) -> None:
    check(name, got == want, f"got={got!r} want={want!r}")


# ======================================================= A. htmlutil
fig = read("bsp_detail_figure.html")
kuji = read("bsp_detail_kuji.html")
kore_art = read("kore_article.html")

eq("A01 くじ頁有兩個 BreadcrumbList", len(ld_json_blocks(kuji)), 2)
eq("A02 figure 頁有一個 BreadcrumbList", len(ld_json_blocks(fig)), 1)
_dl_raw, pairs = dl_pairs(fig, "productDetail_spec")
check("A03 dl_pairs 抽到 商品仕様", len(pairs) == 1 and "全4種" in pairs[0][1], str(pairs))
rows = tables_with(kore_art, "商品名")
eq("A04 コレトレ spec 表 row 數", len(rows[0]), 5)
eq("A05 spec 表第一行", rows[0][0], ["作品名", "鬼滅の刃"])
eq("A06 spec 表商品名行", rows[0][1], ["商品名", "アニメ「鬼滅の刃」 MAXIMATIC GIYU TOMIOKAⅡ"])

# ======================================================= B. bsp 列表
lst = bsp_parser.parse_list(read("bsp_top_list.html"))
eq("B01 列表卡數量", len(lst), 3)
eq("B02 列表 item_id 順序", [x["item_id"] for x in lst], ["2844853", "2831150", "2770580"])
eq("B03 列表商品名", lst[0]["item_name"], "DRAGON BALL SPIRITFLICKS 03")
check("B04 列表有發售文字", "2026年10月29日" in (lst[0]["release_text"] or ""), lst[0]["release_text"])
eq("B05 detail_url", lst[0]["detail_url"], "https://bsp-prize.jp/item/2844853/")

pipe_list = pipeline.bsp_list(read("bsp_top_list.html"))
eq("B06 pipeline 列表 → official_name 來自卡片",
   pipe_list[0]["result"]["official_name"], "DRAGON BALL SPIRITFLICKS 03")
eq("B07 pipeline 列表 name_source", pipe_list[0]["result"]["name_source"], "bsp_list_card")
check("B08 pipeline 列表標記 needs_detail", all(x["needs_detail"] for x in pipe_list))

# ======================================================= C. bsp figure
fig_p = bsp_parser.parse_detail(fig)
eq("C01 figure spec_branch", fig_p["spec_branch"], "figure")
eq("C02 figure 商品名", fig_p["product_name"], "DRAGON BALL SPIRITFLICKS 03")
eq("C03 figure 作品（breadcrumb）", fig_p["ip_title"], "ドラゴンボール シリーズ")
eq("C04 figure 發售日 regex", fig_p["release_text"], "2026-10-29")
eq("C05 figure 冇 JAN", fig_p["has_jan"], False)
eq("C06 figure 種數", fig_p["spec"]["kinds"], 4)
eq("C07 figure 尺寸", fig_p["spec"]["size_cm"], 10.0)

fig_r = pipeline.bsp_detail(fig)
eq("C08 pipeline official_name", fig_r["official_name"], "DRAGON BALL SPIRITFLICKS 03")
eq("C09 pipeline name_source", fig_r["name_source"], "bsp_breadcrumb")
eq("C10 pipeline maker", fig_r["maker_code"], "bandai_spirits")
eq("C11 pipeline ip", fig_r["ip_code"], "dragon_ball")
eq("C12 pipeline series_group（03 → 3）", fig_r["series_group"], "3")
eq("C13 pipeline ready_for_matching", fig_r["ready_for_matching"], True)

# ======================================================= D. bsp plush（多尺寸）
plush_p = bsp_parser.parse_detail(read("bsp_detail_plush.html"))
eq("D01 plush spec_branch", plush_p["spec_branch"], "plush_multi")
eq("D02 plush size_cm = 最大 16", plush_p["spec"]["size_cm"], 16.0)
check("D03 plush size_text 保留原文（含 15cm）",
      "約15cm" in (plush_p["spec"]["size_text"] or ""), plush_p["spec"]["size_text"])
plush_r = pipeline.bsp_detail(read("bsp_detail_plush.html"))
eq("D04 plush ip（ポケットモンスターシリーズ → pokemon）", plush_r["ip_code"], "pokemon")
eq("D05 plush spec_branch 帶到結果", plush_r["spec_branch"], "plush_multi")

# ======================================================= E. bsp くじ（雙 breadcrumb 陷阱）
k_p = bsp_parser.parse_detail(kuji)
eq("E01 くじ頁 breadcrumb 區塊數", k_p["breadcrumb_blocks"], 2)
eq("E02 くじ頁作品唔會攞錯角色鏈", k_p["ip_title"], "ワンピース")
eq("E03 くじ頁角色抽到", k_p["character_name"], "ジュラキュール・ミホーク")
eq("E04 くじ spec_branch", k_p["spec_branch"], "kuji")
eq("E05 くじ 每回價格", k_p["spec"]["price_per_play"], 10000)
eq("E06 くじ 冇 size 喺 spec", k_p["spec"]["size_cm"], None)
k_r = pipeline.bsp_detail(kuji)
eq("E07 くじ ip（唔係角色名）", k_r["ip_code"], "one_piece")
eq("E08 くじ is_kuji", k_r["is_kuji"], True)
eq("E09 くじ 尺寸由描述文抽（約34cm）", k_r["size_cm"], 34.0)
eq("E10 くじ 發售日", k_r["release_text"], "2027-03-27")
eq("E11 くじ official_name", k_r["official_name"],
   "バンプレくじ PREMIUM ワンピース-ジュラキュール・ミホーク-")

# ======================================================= F. コレトレ 文章頁
art_p = kore_parser.parse_article(kore_art)
eq("F01 文章頁 has_spec_table", art_p["has_spec_table"], True)
check("F02 文章頁 raw_title 用 h1", art_p["raw_title"].startswith("【鬼滅の刃】冨岡義勇の"), art_p["raw_title"][:20])
art_r = pipeline.kore_article(kore_art)
eq("F03 文章頁 official_name 用 spec 表", art_r["official_name"],
   "アニメ「鬼滅の刃」 MAXIMATIC GIYU TOMIOKAⅡ")
eq("F04 文章頁 name_source", art_r["name_source"], "kore_spec_table")
eq("F05 文章頁 maker（バンプレスト → bandai_spirits）", art_r["maker_code"], "bandai_spirits")
eq("F06 文章頁 ip", art_r["ip_code"], "kimetsu")
eq("F07 文章頁 size", art_r["size_cm"], 19.0)
eq("F08 文章頁 series_group", art_r["series_group"], "2")
eq("F09 文章頁 ready", art_r["ready_for_matching"], True)

# ======================================================= G. コレトレ 一覽（只做索引）
idx = pipeline.kore_index(read("kore_index.html"))
eq("G01 一覽頁只抽到文章連結（nav 已過濾）", len(idx), 5)
check("G02 一覽頁全部 index_only", all(x["is_index_only"] for x in idx))
check("G03 一覽頁完全冇 official_name 欄位",
      all("official_name" not in x for x in idx))
_nav = [x for x in idx if "about-our-site" in x["detail_url"] or "privacy" in x["detail_url"]]
eq("G04 nav/fixed 頁面已被過濾", len(_nav), 0)


def _try_guard_index():
    pipeline.guard_matchable({"official_name": None, "status": "index_only"}, stage="kore_index")


try:
    _try_guard_index()
    check("G05 索引資料過閘要 raise", False, "冇 raise")
except pipeline.PolicyViolation as e:
    check("G05 索引資料過閘要 raise", True, str(e))

# ======================================================= H. 電撃PF（只看板）
pre = pipeline.dengeki_preview(read("dengeki_report.html"))
eq("H01 預告行數", len(pre), 7)
check("H02 全部 is_item=False", all(x["is_item"] is False for x in pre))
check("H03 全部 board=preview", all(x["board"] == "preview" for x in pre))
eq("H04 預告 maker（エイコー）", pre[0]["maker_code"], "eikoh")
check("H05 預告 多 IP：星のカービィ", "star_kirby" in pre[0]["ip_codes"], str(pre[0]["ip_codes"]))
check("H06 預告 多 IP：着せ恋", "kisekoi" in [x for x in pre if "着せ恋" in x["raw_title"]][0]["ip_codes"], str([x for x in pre if "着せ恋" in x["raw_title"]][0]["ip_codes"]))
check("H07 預告冇 official_name", all(x["official_name"] is None for x in pre))


def _try_guard_preview():
    pipeline.guard_matchable(pre[0], stage="dengeki")


try:
    _try_guard_preview()
    check("H08 預告資料過閘要 raise", False, "冇 raise")
except pipeline.PolicyViolation as e:
    check("H08 預告資料過閘要 raise", True, str(e))

# ======================================================= I. 統計
s = pipeline.summarize("bsp-prize", [x["result"] for x in pipe_list])
eq("I01 bsp 列表 coverage", s["coverage"], 1.0)
s2 = pipeline.summarize("dengeki-prizefair", pre)
eq("I02 dengeki coverage = 0", s2["coverage"], 0.0)

# ======================================================= 輸出
print("=" * 88)
width = max(len(n) for n, _, _ in results)
passed = 0
for name, ok, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name:<{width}}  {detail}")
    passed += ok
print("=" * 88)
print(f"passed={passed} failed={len(results) - passed} total={len(results)}")
if passed != len(results):
    sys.exit(1)
print("模塊 #2 全部測試通過")

