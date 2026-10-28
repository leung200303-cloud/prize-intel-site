# -*- coding: utf-8 -*-
"""由單一真相生成前端用 taxonomy.json（分類索引樹）。

來源：
  廠商 / 作品 / 系列線 ← module1/aliases.py + schema/gen_seed.py 嘅 BRANDS
  品類 / channel / 賞級 / 尺寸桶 ← 01_schema.sql 嘅 enum 定義（鏡像）

⚠️ 唔准手改 taxonomy.json：改 aliases 或 schema 之後重跑呢個 script。
   `nav` 入面標咗 pending 嘅項目，要等兩個決策定咗先可以鎖死（見 docs/IA_審核備忘.md）。
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from aliases import (BRAND_ALIASES, BRANDS, EXCLUDED_IPS,   # noqa: E402
                     EXCLUDED_MAKERS, MAKERS, WORKS)

OUT = HERE.parent / "web" / "taxonomy.json"

# ---- 以下鏡像 01_schema.sql 嘅 enum（改 schema 要同步）
CHANNEL_TYPES = [
    {"code": "prize", "label_zh": "夾機景品", "label_jp": "プライズ", "nav": "prize"},
    {"code": "ichiban_kuji", "label_zh": "一番くじ", "label_jp": "一番くじ", "nav": "kuji"},
    {"code": "gacha", "label_zh": "扭蛋", "label_jp": "ガチャ", "nav": None},
    {"code": "retail", "label_zh": "一般販售", "label_jp": "一般販売", "nav": None},
]

CATEGORIES = [
    {"code": "figure", "label_zh": "人形手辦", "label_jp": "フィギュア"},
    {"code": "plush", "label_zh": "毛絨公仔", "label_jp": "ぬいぐるみ"},
    {"code": "mascot", "label_zh": "吉祥物小物", "label_jp": "マスコット"},
    {"code": "goods", "label_zh": "雜貨", "label_jp": "雑貨・グッズ"},
    {"code": "cushion", "label_zh": "攬枕", "label_jp": "クッション"},
    {"code": "towel", "label_zh": "毛巾", "label_jp": "タオル"},
    {"code": "tableware", "label_zh": "食器", "label_jp": "食器"},
    {"code": "lamp", "label_zh": "燈飾", "label_jp": "ランプ"},
    {"code": "acrylic_stand", "label_zh": "亞克力立牌", "label_jp": "アクリルスタンド"},
    {"code": "colored_paper", "label_zh": "色紙", "label_jp": "色紙"},
    {"code": "keychain", "label_zh": "掛飾／鑰匙扣", "label_jp": "キーホルダー"},
    {"code": "other", "label_zh": "其他", "label_jp": "その他"},
]

PRIZE_TIERS = [
    {"code": "A", "label_jp": "A賞", "label_zh": "A賞"},
    {"code": "B", "label_jp": "B賞", "label_zh": "B賞"},
    {"code": "C", "label_jp": "C賞", "label_zh": "C賞"},
    {"code": "D", "label_jp": "D賞", "label_zh": "D賞"},
    {"code": "E", "label_jp": "E賞", "label_zh": "E賞"},
    {"code": "last_one", "label_jp": "ラストワン賞", "label_zh": "尾賞",
     "aliases": ["尾賞", "最終賞", "ラストワン"]},
]

# brand_line（同 gen_seed.py 同源：aliases.BRANDS），加片假名別名畀搜尋用
BRAND_LINES = [
    {"code": c, "maker": m, "name": jp, "aliases": BRAND_ALIASES.get(c, [])}
    for c, m, jp, _en, _order in sorted(BRANDS, key=lambda x: (x[1], x[4]))
]

SIZE_BUCKETS = [{"cm": c, "label": f"約{c}cm", "rule": "5cm 桶（DB round(size/5)*5）"}
                for c in (10, 15, 20, 25, 30, 35, 40)]


def main() -> None:
    taxonomy = {
        "_meta": {
            "generated_at": date.today().isoformat(),
            "generator": "module1/export_taxonomy.py",
            "sources": ["module1/aliases.py", "schema/01_schema.sql", "schema/gen_seed.py"],
            "do_not_edit": "唔准手改；改來源後重跑 script",
            "counts": {"makers": len(MAKERS), "works": len(WORKS),
                       "brand_lines": len(BRAND_LINES), "categories": len(CATEGORIES)},
        },
        # 頂部導航：7 個主分類。pending 嘅代表功能未定（見 IA 審核備忘）
        "nav": [
            {"id": "kuji", "label_zh": "一番くじ", "label_jp": "一番くじ",
             "route": "/kuji", "status": "ok"},
            {"id": "prize", "label_zh": "夾機景品", "label_jp": "プライズ",
             "route": "/prize", "status": "ok"},
            {"id": "used", "label_zh": "中古二手", "label_jp": "中古",
             "route": "/used", "status": "ok",
             "note": "只存外部連結＋樣本價，唔抓全量"},
            {"id": "schedule", "label_zh": "發售日程", "label_jp": "発売スケジュール",
             "route": "/schedule", "status": "ok"},
            {"id": "market", "label_zh": "行情數據", "label_jp": "相場",
             "route": "/market", "status": "phase2",
             "note": "第一階段只出 price_ref 基準線，唔做走勢圖"},
            {"id": "ranking", "label_zh": "排行榜", "label_jp": "ランキング",
             "route": "/ranking", "status": "pending",
             "note": "等決定：item 級每日聚合（方案A）或外部訊號（方案B）"},
            {"id": "mine", "label_zh": "我的收藏", "label_jp": "マイリスト",
             "route": "/mine", "status": "ok",
             "note": "純 localStorage，零後端"},
        ],
        # 左側篩選
        "filters": {
            "channel_type": CHANNEL_TYPES,
            "maker": [{"code": c, "name_jp": jp, "name_en": en, "aliases": al}
                      for c, jp, en, al, _o in MAKERS],
            "brand_line": BRAND_LINES,
            "ip_work": [{"code": c, "title_jp": jp, "title_en": en, "title_zh": zh,
                         "aliases": al}
                        for c, jp, en, zh, al in WORKS],
            "category": CATEGORIES,
            "prize_tier": PRIZE_TIERS,
            "size_bucket": SIZE_BUCKETS,
            "release_month": {"type": "month", "format": "YYYY-MM",
                              "note": "由 item.release_month 派生，唔寫死清單"},
            "condition": [
                {"code": "new", "label_zh": "全新"},
                {"code": "unopened", "label_zh": "未拆"},
                {"code": "opened", "label_zh": "僅拆"},
                {"code": "flawed", "label_zh": "有瑕疵"},
            ],
            "price_range": {"currency": "JPY", "note": "第一階段只日圓，不做港元換算"},
        },
        # 排序 / 展示規則
        "rules": {
            "size_bucket_rule": "round(size_cm / 5) * 5",
            "series_group_format": "純阿拉伯數字字串，例如 '2'（Ⅱ→2、03→3）",
            "official_name_only": "只有 official_name 可以做去重／比對；raw_title 只做溯源",
            "kuji_model": "kuji 池（is_kuji_pool=true）→ 賞品（parent_item_id + prize_tier）",
            "privacy": {
                "search": "前端本地運算（mv_search_index 靜態 JSON）",
                "server_logs": "冇 query_log / user_id / session",
                "local_only": ["瀏覽記錄", "收藏", "最近搜尋關鍵詞（localStorage）"],
            },
        },
        "excluded": {
            "makers": EXCLUDED_MAKERS,
            "ip_work": EXCLUDED_IPS,
            "note": "明確排除，唔會出現喺 filters；改 aliases.py 後重生",
        },
        "decisions_pending": [
            "排行榜數據來源（A: item_view_daily 聚合 / B: 外部訊號）",
            "廠商清單：確認移走 Namco、Good Smile；TAKARA 放その他",
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(taxonomy, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    print("counts:", taxonomy["_meta"]["counts"],
          "| nav:", len(taxonomy["nav"]),
          "| filters:", len(taxonomy["filters"]))


if __name__ == "__main__":
    main()
