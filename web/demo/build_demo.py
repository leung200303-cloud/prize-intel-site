# -*- coding: utf-8 -*-
"""生成前端 MVP 靜態 Demo 數據。

輸出：
  web/demo/data/taxonomy.json   由 module1 導出（分類樹）
  web/demo/data/items.json      示範商品索引（真實驗證過嘅標題 + 標明 DEMO 嘅合成貨）
  web/demo/standalone.html      全內聯版本（file:// 雙擊即開，唔需要 server）

原則：
  - 真實標題（bsp/kore 實測）標 is_real=True，其餘 demo=True 並喺 UI 顯示 DEMO 標籤
  - 一番くじ 同夾機景品分開（channel），一番くじ 有 prize_tier / pool 概念
  - 電撃PF 報導只入 `preview`（新貨速報看板），**唔入商品索引**（對應模塊政策）
  - 冇圖片（版權），用文字卡 + 色帶
"""
from __future__ import annotations

import hashlib
import json
import random
import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent          # prize-intel/web/demo
PROJ = HERE.parents[1]                          # prize-intel
OUT = HERE / "data"
CONFIG_PATH = HERE / "config.json"

sys.path.insert(0, str(PROJ / "module1"))
from aliases import BRANDS, MAKERS, WORKS   # noqa: E402

TAXONOMY_SRC = PROJ / "web" / "taxonomy.json"

# ---------------------------------------------------------------- 真實標題
# 全部來自 2026-10-28 實測（bsp-prize item 頁 / コレトレ 文章 / カレンダー）
REAL: list[tuple] = [
    # (name, maker, brand, ip, chars, channel, category, month, size, series)
    ("アニメ「鬼滅の刃」 MAXIMATIC GIYU TOMIOKAⅡ", "bandai_spirits", "maximatic", "kimetsu", ["冨岡義勇"], "prize", "figure", "2026-10", 19, "2"),
    ("アニメ「鬼滅の刃」 MAXIMATIC AKAZA", "bandai_spirits", "maximatic", "kimetsu", ["猗窩座"], "prize", "figure", "2026-10", 19, None),
    ("アニメ「鬼滅の刃」 MAXIMATIC TANJIRO KAMADOⅢ", "bandai_spirits", "maximatic", "kimetsu", ["竈門炭治郎"], "prize", "figure", "2026-10", 19, "3"),
    ("DRAGON BALL SPIRITFLICKS 03", "bandai_spirits", "spiritflicks", "dragon_ball", ["ゴジータ", "ブロリー"], "prize", "figure", "2026-10", 10, "3"),
    ("-NARUTO 72 series- 19 忍界造形列伝-うずまきナルト-", "bandai_spirits", "naruto72", "naruto", ["うずまきナルト"], "prize", "figure", "2026-10", 18, "19"),
    ("NARUTO-ナルト- 疾風伝 Memorable Saga-うちはサスケ＆うちはイタチ-", "bandai_spirits", "memorable_saga", "naruto", ["うちはサスケ", "うちはイタチ"], "prize", "figure", "2026-10", 15, None),
    ("ワンピース BATTLE RECORD COLLECTION-RORONOA ZORO Ⅲ-", "bandai_spirits", "brc", "one_piece", ["ロロノア・ゾロ"], "prize", "figure", "2026-10", 16, "3"),
    ("ポケットモンスター SOFVIMATES～フシギバナ～", "bandai_spirits", "sofvimates", "pokemon", ["フシギバナ"], "prize", "figure", "2026-10", 12, None),
    ("ポケットモンスター しっぽみてみて！ぬいぐるみ～ピカチュウ（メスのすがた）・ドーブル・チラーミィ～", "bandai_spirits", None, "pokemon", ["ピカチュウ", "ドーブル", "チラーミィ"], "prize", "plush", "2026-10", 16, None),
    ("劇場版『チェンソーマン レゼ篇』 GLITTER&GLAMOURS-REZE-夜の学校ver.", "bandai_spirits", "glitter_glamours", "chainsaw_man", ["レゼ"], "prize", "figure", "2026-10", 21, None),
    ("TVアニメ『薬屋のひとりごと』 Glasscape-猫猫-", "bandai_spirits", "glasscape", "kusuriya", ["猫猫"], "prize", "figure", "2026-11", 12, None),
    ("学園アイドルマスター ESPRESTO-Frilly lace-倉本千奈", "bandai_spirits", "espresto", "gakuen_idolmaster", ["倉本千奈"], "prize", "figure", "2026-11", 17, None),
    ("学園アイドルマスター ESPRESTO-Textural layer-篠澤 広", "bandai_spirits", "espresto", "gakuen_idolmaster", ["篠澤広"], "prize", "figure", "2026-11", 17, None),
    ("LOVOT ぬいぐるみマスコット～Ruby＆Amber～", "bandai_spirits", None, "lovot", ["Ruby", "Amber"], "prize", "plush", "2026-11", 20, None),
    ("ワンピース メガワールドコレクタブルフィギュア-ロキ-", "bandai_spirits", "banpresto_figure", "one_piece", ["ロキ"], "prize", "figure", "2026-11", 9, None),
    ("NARUTO-ナルト- 疾風伝 Noir Edge Collection-UCHIHA ITACHI-", "bandai_spirits", "banpresto_figure", "naruto", ["うちはイタチ"], "prize", "figure", "2026-11", 18, None),
    ("バンプレくじ PREMIUM ワンピース-ジュラキュール・ミホーク-", "bandai_spirits", "banpre_kuji", "one_piece", ["ジュラキュール・ミホーク"], "ichiban_kuji", "figure", "2027-03", 34, None),
    ("刃牙 Grandista×フィグライフッッ!! 範馬勇次郎-強くなりたくば吊るせッッ-", "bandai_spirits", "grandista", "baki", ["範馬勇次郎"], "prize", "figure", "2026-10", 24, None),
    ("こちら葛飾区亀有公園前派出所 ぬーどるストッパーフィギュアー両津勘吉ー", "furyu", "noodle_stopper", "kochikame", ["両津勘吉"], "prize", "figure", "2026-10", 14, None),
    ("けいおん！ BiCute Dark Figureー平沢唯ー", "furyu", "bicute_dark", "k_on", ["平沢唯"], "prize", "figure", "2026-10", 23, None),
    ("サラブレッドコレクション パカパカサラブレッド(イクイノックス)", "other", None, "thoroughbred", ["イクイノックス"], "prize", "figure", "2026-10", 10, None),
    ("マインクラフト 加湿器：クリーパー", "other", None, "minecraft", ["クリーパー"], "prize", "goods", "2026-10", 11, None),
    ("薬屋のひとりごと BRILLIANTフィギュア Seasonal 猫猫 殭屍", "other", None, "kusuriya", ["猫猫"], "prize", "figure", "2026-10", 20, None),
    ("ポケットモンスター フェイスぬいぐるみバンド イーブイフレンズ～イーブイ・ブラッキー・リーフィア・グレイシア・ニンフィア～", "bandai_spirits", None, "pokemon", ["イーブイ", "ブラッキー", "リーフィア"], "prize", "plush", "2026-10", 15, None),
    ("初音ミクシリーズ FIGURIZMα “初音ミク”-Cosmic-", "sega_fave", None, "hatsune_miku", ["初音ミク"], "prize", "figure", "2026-10", 18, None),
    ("進撃の巨人 Figuno-EREN YEAGER&LEVI-", "other", None, "shingeki", ["エレン・イェーガー", "リヴァイ"], "prize", "figure", "2026-10", 15, None),
    ("とある科学の超電磁砲T FIGURIZMα ‐御坂美琴‐", "sega_fave", None, "toaru", ["御坂美琴"], "prize", "figure", "2026-10", 16, None),
    ("咲-Saki- -Relax time-宮永咲", "other", None, "saki", ["宮永咲"], "prize", "figure", "2026-10", 15, None),
    ("にゃんこ大戦争 皇獣ガオウダーク魂クラフトフィギュア(メタリック)", "other", None, "nyanko", ["皇獣ガオウ"], "prize", "figure", "2026-10", 18, None),
    ("『キン肉マン』 リアルフィギュアシリーズ-ウォーズマン-", "other", None, "kinnikuman", ["ウォーズマン"], "prize", "figure", "2026-10", 20, None),
]

# ---------------------------------------------------------------- 合成用資料
CHARS: dict[str, list[str]] = {
    "kimetsu": ["竈門炭治郎", "竈門禰豆子", "我妻善逸", "嘴平伊之助", "胡蝶しのぶ"],
    "one_piece": ["モンキー・D・ルフィ", "ナミ", "サンジ", "ポートガス・D・エース", "ヤマト"],
    "jujutsu": ["五条悟", "虎杖悠仁", "伏黒恵", "釘崎野薔薇", "宿儺"],
    "dragon_ball": ["孫悟空", "ベジータ", "孫悟飯", "フリーザ", "ブロリー"],
    "naruto": ["うちはサスケ", "うちはイタチ", "はたけカカシ", "春野サクラ"],
    "chiikawa": ["ちいかわ", "ハチワレ", "うさぎ", "モモンガ"],
    "sanrio": ["ハローキティ", "マイメロディ", "クロミ", "シナモロール", "ポムポムプリン"],
    "blue_archive": ["ホシノ", "シロコ", "アリス", "ユウカ", "ミカ"],
    "uma_musume": ["スペシャルウィーク", "サイレンススズカ", "トウカイテイオー", "オグリキャップ"],
    "touhou": ["博麗霊夢", "霧雨魔理沙", "レミリア・スカーレット", "フランドール・スカーレット"],
    "evangelion": ["綾波レイ", "式波・アスカ・ラングレー", "真希波・マリ・イラストリアス"],
    "k_on": ["秋山澪", "田井中律", "琴吹紬", "中野梓"],
    "zootopia": ["ジュディ・ホップス", "ニック・ワイルド"],
    "minecraft": ["スティーブ", "エンダーマン"],
    "toy_story": ["ウッディ", "バズ・ライトイヤー", "ジェシー"],
    "kingdom": ["信", "嬴政", "羌瘣"],
    "hunter": ["ゴン＝フリークス", "キルア＝ゾルディック", "クラピカ"],
    "overlord": ["アインズ", "アルベド", "シャルティア"],
    "lycoris": ["錦木千束", "井ノ上たきな", "クルミ"],
    "dandadan": ["綾瀬桃", "オカルン", "ターボババア"],
    "kamen_rider": ["仮面ライダー電王", "仮面ライダーゼロワン"],
    "ultraman": ["ウルトラマン", "ウルトラマンタロウ", "ウルトラマンゼロ"],
    "irodori": ["西野つかさ", "東城綾", "北大路さつき"],
    "to_love_ru": ["古手川唯", "金色の闇", "結城美柑"],
    "kisekoi": ["喜多川海夢", "五条新菜"],
    "blue_lock": ["潔世一", "蜂楽廻", "凪誠士郎"],
    "doraemon": ["ドラえもん", "のび太", "しずか"],
    "pokemon": ["ピカチュウ", "イーブイ", "リザードン", "ミュウツー"],
    "precure": ["キュアブラック", "キュアホワイト"],
    "one_punch": ["サイタマ", "ジェノス", "タツマキ"],
    "kusuriya": ["壬氏"],
    "baki": ["範馬刃牙", "烈海王"],
    "thoroughbred": ["トウカイテイオー", "オグリキャップ"],
    "chainsaw_man": ["デンジ", "パワー", "マキマ"],
    "gakuen_idolmaster": ["藤田ことね", "花海咲季"],
    "star_kirby": ["カービィ", "ワドルディ", "メタナイト"],
    "suzumiya": ["涼宮ハルヒ", "長門有希", "朝比奈みくる"],
    "hokuto": ["ケンシロウ", "ラオウ", "トキ"],
    "gundam_seed": ["キラ・ヤマト", "アスラン・ザラ", "ラクス・クライン"],
    "needy_girl": ["超てんちゃん"],
    "lovot": ["ラブ"],
    "nyanko": ["にゃんこ", "タマ", "ネコ"],
    "shingeki": ["ミカサ・アッカーマン"],
    "toaru": ["白井黒子", "一方通行"],
    "saki": ["原村和"],
    "tensura": ["リムル", "ミリム", "シオン"],
    "kingdom_hearts": ["ソラ", "リク", "カイリ"],
    "hatsune_miku": ["鏡音リン", "鏡音レン", "巡音ルカ"],
    "kinnikuman": ["キン肉スグル", "テリーマン"],
    # ---- 2026-10-28 自測補漏：新 IP 都要有樣本，否則加咗別名都搜唔到 ----"
    "frieren": ["フリーレン", "フェルン", "ヒンメル"],
    "oshi_no_ko": ["星野アイ", "星野アクア", "星野ルビー"],
    "spy_family": ["アーニャ・フォージャー", "ロイド・フォージャー", "ヨル・フォージャー"],
    "tokyo_revengers": ["花垣武道", "佐野万次郎", "松野千冬"],
    "haikyu": ["日向翔陽", "影山飛雄", "孤爪研磨"],
    "heroaca": ["緑谷出久", "爆豪勝己", "麗日お茶子"],
    "hololive": ["さくらみこ", "星街すいせい", "兎田ぺこら"],
    "nijisanji": ["月ノ美兎", "静凛", "樋口楓"],
    "sumikko": ["しろくま", "ぺんぎん？", "とんかつ"],
    "opanchu": ["おぱんちゅうさぎ"],
    "mofusand": ["モフサンド", "ねこ"],
    "kaiju_no8": ["日比野カフカ", "四ノ宮キコル"],
    "dungeon_meshi": ["ライオス", "マルシル", "センシ"],
    "jojo": ["空条承太郎", "ジョルノ・ジョバァーナ"],
    "fate": ["セイバー", "アルトリア", "マシュ・キリエライト"],
    "gundam": ["アムロ・レイ", "シャア・アズナブル"],
    "bleach": ["黒崎一護", "朽木ルキア"],
    "gintama": ["坂田銀時", "神楽"],
    "lovelive": ["高坂穂乃果", "南ことり"],
    "idolmaster": ["如月千早", "島村卯月"],
}

BRAND_BY_CODE = {c: (m, jp) for c, m, jp, _en, _o in BRANDS}
SIZE_BY_BRAND = {
    "maximatic": 19, "grandista": 24, "vibration_stars": 18, "memorable_saga": 15,
    "spiritflicks": 10, "banpresto_figure": 16, "luminasta": 20, "spm": 22,
    "yumemirize": 18, "desktop_x2": 12, "desktop_cute": 10, "amp_plus": 12,
    "noodle_stopper": 14, "bicute_bunnies": 23, "bicute_dark": 23, "kurippy": 12,
    "melffy": 11, "tenitol": 20, "brc": 16, "glitter_glamours": 21,
    "glasscape": 12, "espresto": 17, "sofvimates": 12, "banpre_kuji": 30, "naruto72": 18,
}
PRICE_BY_SIZE = {9: 300, 10: 350, 11: 400, 12: 450, 14: 600, 15: 700, 16: 800,
                 17: 900, 18: 1000, 19: 1100, 20: 1200, 21: 1300, 22: 1400,
                 23: 1500, 24: 1600, 30: 2200, 34: 3500}

MONTHS = ["2026-07", "2026-08", "2026-09", "2026-10", "2026-10", "2026-10",
          "2026-11", "2026-11", "2026-12", "2027-01", "2027-02", "2027-03"]


def det_int(seed: str, lo: int, hi: int) -> int:
    h = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16)
    return lo + h % (hi - lo + 1)


def make_item(idx: int, name, maker, brand, ip, chars, channel, category,
              month, size, series, is_real: bool, baseline: int | None = None) -> dict:
    iid = f"itm_{idx:04d}"
    size = size or det_int(iid + "s", 10, 24)
    baseline = baseline or PRICE_BY_SIZE.get(size, 800)
    sold_min = int(baseline * (0.75 + det_int(iid + "a", 0, 30) / 100))
    sold_max = int(baseline * (1.3 + det_int(iid + "b", 0, 220) / 100))
    views = det_int(iid + "v", 30, 3200)
    if brand in ("maximatic", "luminasta", "grandista"):
        views = int(views * 1.8)
    return {
        "id": iid,
        "official_name": name,
        "raw_title": name,
        "maker": maker,
        "brand": brand,
        "ip": ip,
        "characters": chars,
        "channel": channel,
        "category": category,
        "release_month": month,
        "size_cm": size,
        "series_group": series,
        "is_resale": det_int(iid + "r", 0, 9) == 0,
        "is_kuji_pool": channel == "ichiban_kuji" and det_int(iid + "k", 0, 2) == 0,
        "prize_tier": (["A賞", "B賞", "ラストワン賞"][det_int(iid + "t", 0, 2)]
                       if channel == "ichiban_kuji" else None),
        "status": "on_sale" if month <= "2026-10" else "announced",
        "stock_flag": "low" if det_int(iid + "st", 0, 9) == 0 else "normal",
        "views_7d": views,
        "price": {
            "baseline_jpy": baseline,
            "sold_min_jpy": sold_min,
            "sold_max_jpy": sold_max,
            "captured_at": "2026-10-20",
        },
        "market_links": {
            "surugaya": "https://www.suruga-ya.jp/search?search_word=" + name,
            "mercari": "https://jp.mercari.com/search?keyword=" + name,
            "yahoo": "https://auctions.yahoo.co.jp/search/search?p=" + name,
        },
        "is_real": is_real,
        "demo": not is_real,
    }


def build_items() -> list[dict]:
    items: list[dict] = []
    for i, row in enumerate(REAL, start=1):
        name, maker, brand, ip, chars, ch, cat, month, size, series = row
        items.append(make_item(i, name, maker, brand, ip, chars, ch, cat, month, size, series, True))

    rnd = random.Random(20261028)
    synthetic_target = 96
    ips = [w[0] for w in WORKS if CHARS.get(w[0])]
    brand_codes = list(BRAND_BY_CODE)
    made = 0

    def gen_one(ip: str) -> dict:
        nonlocal made
        brand = rnd.choice(brand_codes)
        maker, brand_jp = BRAND_BY_CODE[brand]
        chars = rnd.sample(CHARS[ip], k=min(2, len(CHARS[ip])))
        month = rnd.choice(MONTHS)
        channel = "ichiban_kuji" if rnd.random() < 0.18 else "prize"
        category = "plush" if rnd.random() < 0.2 else "figure"
        size = SIZE_BY_BRAND.get(brand, 16)
        if category == "plush":
            size = size + 4
        base = PRICE_BY_SIZE.get(size, 800)
        if channel == "ichiban_kuji":
            base = rnd.choice([700, 790, 850, 950])
        ip_jp = next(w[1] for w in WORKS if w[0] == ip)
        title = f"{ip_jp} {brand_jp} {chars[0]} ver."
        if rnd.random() < 0.35:
            title += f" vol.{rnd.randint(1, 4)}"
        series = None
        if "vol." in title:
            series = title.rsplit("vol.", 1)[1].strip()
        made += 1
        return make_item(len(items) + 1, title, maker, brand, ip, chars,
                         channel, category, month, size, series, False, base)

    # 第一輪：保證每個有角色表嘅 IP 至少 1 款（自測發現隨機抽樣會漏 IP）
    for ip in ips:
        if made >= synthetic_target:
            break
        items.append(gen_one(ip))

    # 第二輪：隨機補足
    while made < synthetic_target:
        items.append(gen_one(rnd.choice(ips)))
    return items


def build_preview() -> list[dict]:
    """電撃PF 新貨速報（唔入商品索引，只做看板）。"""
    rows = [
        ("エイコー", "『星のカービィ』ドーナツ型ライト"),
        ("エイコー", "『仮面ライダーカブト』プライズアイテム"),
        ("フリュー", "『いちご100％』東城綾 フィギュア"),
        ("フリュー", "『To LOVEる』古手川唯 ぬーどるストッパーフィギュア"),
        ("フリュー", "『東方Project』四季映姫・ヤマザナドゥ ぬーどるストッパーフィギュア"),
        ("タイトー", "『いちご100％』北大路さつき フィギュア"),
        ("タイトー", "『To LOVEる ダークネス』金色の闇 もこもこバニー"),
        ("タイトー", "『着せ恋』喜多川海夢～十六夜ありさver.～"),
        ("セガ フェイブ", "『リコリス・リコイル』錦木千束 ハイプレミアムフィギュア STREET SNAP"),
        ("セガ フェイブ", "TVアニメ『ダンダダン』Luminasta アイラ（変身）"),
        ("BANDAI SPIRITS", "『機動戦士ガンダムSEED』プライズフィギュア"),
        ("システムサービス", "アニメ『北斗の拳 -FIST OF THE NORTH STAR-』プライズフィギュア"),
        ("コナミアーケードゲームス", "『涼宮ハルヒの憂鬱』プライズフィギュア"),
        ("システムサービス", "アニメ「NEEDY GIRL OVERDOSE」プライズフィギュア"),
    ]
    return [{"maker_text": m, "title": t, "source": "電撃ホビーウェブ 第85回プライズフェア",
             "note": "報導描述句，冇官方商品名／尺寸，只作預告提示"} for m, t in rows]


def load_config() -> dict:
    cfg = {"beta_version": "v0.1", "contact_email": ""}
    if CONFIG_PATH.exists():
        cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    return cfg


def inject_config(html: str, cfg: dict) -> str:
    email = (cfg.get("contact_email") or "").strip()
    if not email:
        email = "contact@example.com"
        print("⚠️  config.json contact_email 未設定 —— dist 會用 placeholder（上線前一定要改）")
    ver = cfg.get("beta_version") or "v0.1"
    html = html.replace("__CONTACT_EMAIL__", email).replace("__BETA_VERSION__", ver)
    html = html.replace("Beta v0.1", f"Beta {ver}")
    return html


def inline_standalone(items_data: dict) -> None:
    """把 CSS/JS/JSON 全部內聯成一個可 file:// 雙擊開啟嘅 HTML。

    ⚠️ 內聯時會剷走 app.js 嘅 `@NET-BEGIN … @NET-END` 區塊（fetch 外部 JSON），
       令 standalone 版完全冇網絡原語 —— 可以靜態驗證「零收集」。
    """
    html = (HERE / "index.html").read_text(encoding="utf-8")
    css = (HERE / "styles.css").read_text(encoding="utf-8")
    js = (HERE / "app.js").read_text(encoding="utf-8")
    tax = (OUT / "taxonomy.json").read_text(encoding="utf-8")
    data = json.dumps(items_data, ensure_ascii=False)

    # 剷走網絡 loader（保留不可達錯誤分支）
    start, end = js.find("// @NET-BEGIN"), js.find("// @NET-END")
    if start == -1 or end == -1:
        raise SystemExit("app.js 缺少 @NET-BEGIN/@NET-END 標記")
    js = (js[:start]
          + "    throw new Error('standalone 版冇外部數據（本應內聯）');\n"
          + js[end + len("// @NET-END"):])
    for pat in ("fetch(", "XMLHttpRequest", "sendBeacon"):
        if pat in js:
            raise SystemExit(f"內聯後仍然有網絡原語：{pat}")

    html = html.replace('<link rel="stylesheet" href="./styles.css">',
                        f"<style>\n{css}\n</style>")
    html = html.replace('<script src="./app.js"></script>',
                        f"<script>\nwindow.__PI_INLINE__ = {{taxonomy: {tax}, items: {data}}};\n</script>\n"
                        f"<script>\n{js}\n</script>")
    html = inject_config(html, load_config())
    (HERE / "standalone.html").write_text(html, encoding="utf-8")
    print(f"wrote standalone.html ({(HERE / 'standalone.html').stat().st_size // 1024} KB)")


def write_dist() -> None:
    """組裝 Cloudflare Pages 上傳目錄：dist/ 只放 standalone 版（單檔、零依賴）。"""
    dist = HERE / "dist"
    dist.mkdir(parents=True, exist_ok=True)

    (dist / "index.html").write_text((HERE / "standalone.html").read_text(encoding="utf-8"),
                                     encoding="utf-8")

    (dist / "robots.txt").write_text(
        "# Beta 示範版：暫時唔畀搜尋引擎索引（避免示範數據被當成真實情報）\n"
        "User-agent: *\nDisallow: /\n", encoding="utf-8")

    # Cloudflare Pages 專用 _headers
    # CSP 用 default-src 'none'：連 connect-src 都封，等於就算日後有人偷加追蹤 script 都送唔出數據
    (dist / "_headers").write_text(
        "/*\n"
        "  X-Frame-Options: DENY\n"
        "  X-Content-Type-Options: nosniff\n"
        "  Referrer-Policy: no-referrer\n"
        "  Permissions-Policy: geolocation=(), microphone=(), camera=(), interest-cohort=()\n"
        "  Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; "
        "script-src 'unsafe-inline'; img-src data:; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'\n",
        encoding="utf-8")

    print(f"wrote dist/ : index.html ({(dist / 'index.html').stat().st_size // 1024} KB), "
          f"robots.txt, _headers")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", type=Path,
                    help="用現成 items.json（例：data/items.real.json）代替生成示範數據")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy(TAXONOMY_SRC, OUT / "taxonomy.json")

    if args.items:
        payload = json.loads(args.items.read_text(encoding="utf-8"))
        payload.setdefault("_meta", {})["mode"] = f"from {args.items.name}"
        (OUT / "items.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        print("using real items:", args.items.name, payload["_meta"].get("counts"))
        inline_standalone(payload)
        write_dist()
        return

    items = build_items()
    payload = {
        "_meta": {
            "generated_at": date.today().isoformat(),
            "generator": "web/demo/build_demo.py",
            "note": "示範數據：真實標題來自 2026-10-28 實測；其餘標 demo=true 為合成示範貨",
            "counts": {"total": len(items),
                       "real": sum(1 for x in items if x["is_real"]),
                       "prize": sum(1 for x in items if x["channel"] == "prize"),
                       "kuji": sum(1 for x in items if x["channel"] == "ichiban_kuji")},
            "ranking_label": "玩家瀏覽熱度（非採購行情指標）",
            "privacy": "搜尋／瀏覽／收藏全部喺瀏覽器本地，唔上傳伺服器",
        },
        "items": items,
        "preview": build_preview(),
    }
    (OUT / "items.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print("wrote data/items.json", payload["_meta"]["counts"])
    inline_standalone(payload)
    write_dist()


if __name__ == "__main__":
    main()

