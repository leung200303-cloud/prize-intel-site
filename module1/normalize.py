# -*- coding: utf-8 -*-
"""文字正規化：全形／假名／裝飾符號／作品名後綴／系列號（含羅馬數字）。

呢個模組係「唯一真相」：SQL 嘅 normalize_title() 同本模組要保持一致。
"""
from __future__ import annotations

import re

# 全形 ASCII → 半形
ZEN2HAN = {chr(0xFF01 + i): chr(0x21 + i) for i in range(94)}

# 裝飾符號（比對時直接刪）
DECOR = set("　 \t\n【】[]（）()「」『』〔〕〈〉《》・･-–—―_/／\\:：;；!！?？★☆♪♡♥、,，.。~〜+＋*＊#＃@＠|｜'\"’”")

ROMAN = {"Ⅰ": 1, "Ⅱ": 2, "Ⅲ": 3, "Ⅳ": 4, "Ⅴ": 5,
         "Ⅵ": 6, "Ⅶ": 7, "Ⅷ": 8, "Ⅸ": 9, "Ⅹ": 10,
         "ⅰ": 1, "ⅱ": 2, "ⅲ": 3, "ⅳ": 4, "ⅴ": 5,
         "ⅵ": 6, "ⅶ": 7, "ⅷ": 8, "ⅸ": 9, "ⅹ": 10}

# 作品名常見後綴（比對 key 要剝走）
IP_SUFFIXES = ("シリーズ", "シリーズ。", "series", "Series", "ＳＥＲＩＥＳ")


def kana_fold(s: str) -> str:
    """片假名 → 平假名（ァ..ヶ = U+30A1..30F6，減 96）。"""
    return "".join(chr(ord(c) - 96) if 0x30A1 <= ord(c) <= 0x30F6 else c for c in s)


def normalize_text(s: str | None) -> str:
    """顯示用正規化：全形→半形、假名統一、細楷、拆裝飾、壓空白。保留可讀性。"""
    if not s:
        return ""
    out = "".join(ZEN2HAN.get(c, c) for c in s)
    out = kana_fold(out).lower()
    out = "".join(" " if c in DECOR else c for c in out)
    return re.sub(r"\s+", " ", out).strip()


def match_key(s: str | None) -> str:
    """比對用 key：喺 normalize_text 之上再刪走所有空白（連詞都唔留）。"""
    return normalize_text(s).replace(" ", "")


def strip_ip_suffix(s: str | None) -> str:
    """剝走「シリーズ」類後綴 —— PoC 實測：ドラゴンボール シリーズ / ポケモンモンスターシリーズ。"""
    if not s:
        return ""
    out = s.strip()
    for suf in sorted(IP_SUFFIXES, key=len, reverse=True):
        if out.endswith(suf):
            out = out[: -len(suf)].strip()
    return out


def roman_to_int(tok: str) -> int | None:
    if tok in ROMAN:
        return ROMAN[tok]
    return None


# 系列號抽取：vol.1 / 第2弾 / 03 / Ⅱ / ZORO Ⅲ
_SERIES_PATTERNS = [
    (re.compile(r"vol\.?\s*(\d+)", re.I), "vol"),
    (re.compile(r"第\s*(\d+)\s*弾"), "dan"),
    (re.compile(r"(\d+)\s*弾"), "dan"),
    (re.compile(r"(?:[\s\-_ー])(\d{2})$"), "num"),
]


def extract_series_group(title: str | None) -> str | None:
    """由商品名抽系列號，統一回傳阿拉伯數字字串。

    覆蓋 PoC 見到嘅四種寫法：
      MAXIMATIC GIYU TOMIOKAⅡ（羅馬數字後綴）
      MAXIMATIC TANJIRO KAMADOⅢ
      BATTLE RECORD COLLECTION-RORONOA ZORO Ⅲ
      DRAGON BALL SPIRITFLICKS 03
    """
    if not title:
        return None
    t = title.strip()

    # 1) 尾隨羅馬數字（最常見：Ⅱ / Ⅲ）；容許尾隨連字號，例 ZORO Ⅲ-
    m = re.search(r"([ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹ])\s*[-‐–—ー]?\s*$", t)
    if m:
        n = roman_to_int(m.group(1))
        if n:
            return str(n)

    # 2) vol. / 第N弾 / 2位數編號
    for pat, _kind in _SERIES_PATTERNS:
        mm = pat.search(t)
        if mm:
            return str(int(mm.group(1)))
    return None


# 尺寸：約19cm / 約 10 cm / A3 / 約9〜12cm
_SIZE_PATTERNS = [
    re.compile(r"約\s*(\d+(?:\.\d+)?)\s*(?:〜|～|~|-)\s*(\d+(?:\.\d+)?)\s*cm"),
    re.compile(r"約\s*(\d+(?:\.\d+)?)\s*cm"),
]


def parse_sizes(text: str | None) -> dict:
    """回傳 {size_cm, size_text, sizes[]}。

    多角色多尺寸（PoC 實測）→ size_cm 取最大值，原文完整保留喺 size_text。
    """
    if not text:
        return {"size_cm": None, "size_text": None, "sizes": []}
    sizes: list[float] = []
    for m in _SIZE_PATTERNS[0].finditer(text):
        sizes.extend([float(m.group(1)), float(m.group(2))])
    for m in _SIZE_PATTERNS[1].finditer(text):
        sizes.append(float(m.group(1)))
    sizes = sorted(set(sizes))
    return {
        "size_cm": max(sizes) if sizes else None,
        "size_text": text.strip(),
        "sizes": sizes,
    }


def detect_kuji(text: str | None) -> bool:
    """一番くじ／バンプレくじ 判斷：靠「1回◯円」「くじ」「賞」等訊號。"""
    if not text:
        return False
    t = normalize_text(text)
    return any(k in t for k in ("1回", "くじ", "一番くじ", "ラストワン"))
