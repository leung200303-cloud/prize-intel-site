# -*- coding: utf-8 -*-
"""模塊 #1 測試：單元測試 + fixtures 對答案。

用法：python test_module1.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from aliases import resolve_ip, resolve_maker           # noqa: E402
from extract import parse_spec, run                     # noqa: E402
from normalize import (detect_kuji, extract_series_group, match_key,
                       normalize_text, parse_sizes, strip_ip_suffix)

FIELDS = ["official_name", "name_source", "maker_code", "ip_code", "size_cm",
          "series_group", "is_kuji"]
results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, bool(cond), detail))


def eq(name: str, got, want) -> None:
    check(name, got == want, f"got={got!r} want={want!r}")


# ============================================================ A. 正規化
eq("A01 裝飾符號：兩個標題 normalize 後相同",
   match_key("【鬼滅の刃】MAXIMATIC"), match_key("鬼滅の刃 MAXIMATIC"))
eq("A02 片假名→平假名", match_key("フリュー"), match_key("ふりゅー"))
eq("A03 全形→半形", match_key("ｉｃｈｉｇｏ"), "ichigo")
eq("A04 全形百分號", match_key("いちご100％"), match_key("いちご100%"))
eq("A05 strip_ip_suffix：ドラゴンボール シリーズ", strip_ip_suffix("ドラゴンボール シリーズ"), "ドラゴンボール")
eq("A06 strip_ip_suffix：ポケモンモンスターシリーズ", strip_ip_suffix("ポケモンモンスターシリーズ"), "ポケモンモンスター")
eq("A07 strip_ip_suffix：冇後綴唔改", strip_ip_suffix("ワンピース"), "ワンピース")

# ============================================================ B. 系列號（含羅馬數字）
eq("B01 Ⅱ → 2", extract_series_group("アニメ「鬼滅の刃」 MAXIMATIC GIYU TOMIOKAⅡ"), "2")
eq("B02 Ⅲ → 3", extract_series_group("アニメ「鬼滅の刃」 MAXIMATIC TANJIRO KAMADOⅢ"), "3")
eq("B03 ZORO Ⅲ → 3", extract_series_group("ワンピース BATTLE RECORD COLLECTION-RORONOA ZORO Ⅲ-"), "3")
eq("B04 SPIRITFLICKS 03 → 3", extract_series_group("DRAGON BALL SPIRITFLICKS 03"), "3")
eq("B05 vol.2 → 2", extract_series_group("Luminasta 五条悟 vol.2"), "2")
eq("B06 第2弾 → 2", extract_series_group("るかっぷ 第2弾"), "2")
eq("B07 冇系列號 → None", extract_series_group("バンプレくじ PREMIUM ワンピース-ジュラキュール・ミホーク-"), None)

# ============================================================ C. 尺寸
eq("C01 單尺寸", parse_sizes("商品仕様|・全1種|・約19cm")["size_cm"], 19.0)
m = parse_sizes("・ピカチュウ：約15cm、ドーブル：約16cm、チラーミィ：約16cm")
eq("C02 多尺寸取最大", m["size_cm"], 16.0)
eq("C03 多尺寸全部抽到", m["sizes"], [15.0, 16.0])
eq("C04 尺寸範圍取最大", parse_sizes("約9〜12cm")["size_cm"], 12.0)
eq("C05 冇尺寸 → None", parse_sizes("■発売日：2027年3月27日")["size_cm"], None)

# ============================================================ D. spec 三格式
s_fig = parse_spec("商品仕様|・全1種|・約19cm")
eq("D01 figure 種數", s_fig["kinds"], 1)
eq("D02 figure 尺寸", s_fig["size_cm"], 19.0)
s_kuji = parse_spec("商品仕様|■発売日：2027年3月27日(土)より順次発売予定|■メーカー希望小売価格：1回10,000円（税込）")
eq("D03 くじ 發售日", s_kuji["release_text"], "2027年3月27日(土)より順次発売予定")
eq("D04 くじ 每回價格", s_kuji["price_per_play"], 10000)
eq("D05 くじ 冇尺寸", s_kuji["size_cm"], None)
check("D06 detect_kuji くじ", detect_kuji("バンプレくじ PREMIUM ワンピース"))
check("D07 detect_kuji 一般品為 False", not detect_kuji("MAXIMATIC GIYU TOMIOKAⅡ"))

# ============================================================ E. maker alias
eq("E01 バンプレスト", resolve_maker("バンプレスト")["code"], "bandai_spirits")
eq("E02 BANDAI SPIRITS", resolve_maker("BANDAI SPIRITS")["code"], "bandai_spirits")
eq("E03 セガ", resolve_maker("セガ")["code"], "sega_fave")
eq("E04 セガ フェイブ", resolve_maker("セガ フェイブ")["code"], "sega_fave")
eq("E05 タイトー", resolve_maker("タイトー")["code"], "taito")
eq("E06 フリュー", resolve_maker("フリュー")["code"], "furyu")
eq("E07 コナミ", resolve_maker("コナミアーケードゲームス")["code"], "konami_ags")
eq("E08 システムサービス", resolve_maker("システムサービス")["code"], "system_service")
eq("E09 冇廠商 → None", resolve_maker("【鬼滅の刃】冨岡義勇のMAXIMATICフィギュアがオンクレに登場！"), None)

# ============================================================ F. ip alias（後綴差異）
eq("F01 ドラゴンボール シリーズ", resolve_ip("ドラゴンボール シリーズ")["code"], "dragon_ball")
eq("F02 ポケモンモンスターシリーズ", resolve_ip("ポケモンモンスターシリーズ")["code"], "pokemon")
eq("F03 ワンピース", resolve_ip("ワンピース")["code"], "one_piece")
eq("F04 ONE PIECE", resolve_ip("ONE PIECE")["code"], "one_piece")
eq("F05 ナルト（短別名）", resolve_ip("【ナルト】19巻表紙")["code"], "naruto")
eq("F06 いちご100％", resolve_ip("いちご100％")["code"], "irodori")
eq("F07 着せ恋（簡稱）", resolve_ip("『着せ恋』喜多川海夢")["code"], "kisekoi")
eq("F08 To LOVEる ダークネス", resolve_ip("To LOVEる ダークネス")["code"], "to_love_ru")
eq("F09 ガンダムSEED 唔會撞其他高達", resolve_ip("機動戦士ガンダムSEED")["code"], "gundam_seed")
eq("F10 冇作品 → None", resolve_ip("ドーナツ型ライト")["code"] if resolve_ip("ドーナツ型ライト") else None, None)

# ============================================================ G. 安全規則
d = run({"extractor": "dengeki", "payload": {"raw_title": "エイコー：『星のカービィ』ドーナツ型ライト"}})
check("G01 電撃PF 冇官方名（誠實回 None）", d.official_name is None)
check("G02 電撃PF 唔准自動比對", d.ready_for_matching is False)
check("G03 電撃PF 仍然解析到 maker/ip",
      d.maker_code == "eikoh" and d.ip_code == "star_kirby", f"{d.maker_code}/{d.ip_code}")
k = run({"extractor": "kore", "payload": {"raw_title": "【鬼滅の刃】猗窩座のMAXIMATICフィギュアがオンクレに登場！"}})
check("G04 コレトレ 冇 spec 表 → 唔准自動比對", k.ready_for_matching is False)
check("G05 冇 spec 表有 warning", "no_spec_table" in k.warnings, str(k.warnings))
b = run({"extractor": "bsp", "payload": {
    "raw_title": "X", "breadcrumb": ["トップページ", "作品タイトル", "鬼滅の刃", "テスト商品名"]}})
check("G06 bsp breadcrumb 抽出成功", b.official_name == "テスト商品名")
check("G07 bsp 有官方名 → 准自動比對", b.ready_for_matching is True)

# ============================================================ H. fixtures 對答案
data = json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))
for it in data["items"]:
    r = run(it).to_dict()
    exp = it["expect"]
    bad = [f for f in FIELDS if r.get(f) != exp.get(f)]
    check(f"H {it['id']}", not bad,
          "" if not bad else f"差異={bad} got={ {f: r.get(f) for f in bad} }")

# ============================================================ 輸出
print("=" * 84)
width = max(len(n) for n, _, _ in results)
passed = 0
for name, ok, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name:<{width}}  {detail}")
    passed += ok
print("=" * 84)
print(f"passed={passed} failed={len(results) - passed} total={len(results)}")
if passed != len(results):
    sys.exit(1)
print("模塊 #1 全部測試通過")
