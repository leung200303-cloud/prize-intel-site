# -*- coding: utf-8 -*-
"""模塊 #1：商品名抽取層。

核心原則（Step 3 PoC 結論）：
    raw_title      = 頁面原標題（保留追溯，永遠唔做比對）
    official_name  = 抽出嚟嘅乾淨官方商品名（**唯一**可以做比對嘅輸入）

四個 extractor 對應四種源頭形態：
    extract_bsp()         bsp-prize item 頁 → JSON-LD BreadcrumbList
    extract_kore_tore()   コレトレ 文章     → spec 表「商品名」
    extract_dengeki()     電撃プライズフェア → 只有描述句，冇官方名（誠實回 None）
    extract_generic()     其他             → 冇官方名，回 None + warning

輸出係純 dict／dataclass，唔碰 DB，唔碰 SQL。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

from aliases import resolve_ip, resolve_ips, resolve_maker
from normalize import (detect_kuji, extract_series_group, normalize_text,
                       parse_sizes, strip_ip_suffix)

# 源頭層級嘅廠商預設值（bsp-prize = BANDAI SPIRITS 自家站）
SOURCE_MAKER_DEFAULT = {
    "bsp-prize": "bandai_spirits",
}

NAME_SOURCE = {
    "bsp_breadcrumb": "JSON-LD BreadcrumbList 最後一項",
    "bsp_title_tag": "<title> 前段（backup）",
    "bsp_list_card": "bsp 列表卡商品名（詳情頁優先）",
    "kore_spec_table": "spec 表「商品名」欄",
    "dengeki_none": "報導描述句，冇官方商品名",
    "none": "冇可用來源",
}


@dataclass
class NamingResult:
    raw_title: str
    official_name: str | None
    name_source: str
    maker_code: str | None = None
    maker_match: str | None = None
    maker_method: str | None = None
    ip_code: str | None = None
    ip_match: str | None = None
    ip_method: str | None = None
    ip_codes: list[str] = field(default_factory=list)   # 一段文字可能含多個 IP
    size_cm: float | None = None
    size_text: str | None = None
    series_group: str | None = None
    is_kuji: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def official_name_source_label(self) -> str:
        return NAME_SOURCE.get(self.name_source, self.name_source)

    @property
    def ready_for_matching(self) -> bool:
        """可唔可以做 L2/L3 比對？冇官方商品名嘅一律唔准自動合併。"""
        return bool(self.official_name)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ready_for_matching"] = self.ready_for_matching
        d["name_source_label"] = self.official_name_source_label
        return d


# --------------------------------------------------------------------- spec
def parse_spec(text: str | None) -> dict:
    """解析 bsp 嘅 `dl.productDetail_spec` 三種格式。

    回傳：{kinds, sizes, size_cm, size_text, release_text, price_per_play, raw_lines}
    """
    out = {"kinds": None, "sizes": [], "size_cm": None, "size_text": None,
           "release_text": None, "price_per_play": None, "raw_lines": []}
    if not text:
        return out

    lines = [ln.strip() for ln in re.split(r"[|\n]", text) if ln.strip()]
    out["raw_lines"] = lines

    for ln in lines:
        if "商品仕様" in ln:
            continue
        m = re.search(r"全\s*(\d+)\s*種", ln)
        if m:
            out["kinds"] = int(m.group(1))
        m = re.search(r"発売日\s*[:：]\s*(.+)", ln)
        if m:
            out["release_text"] = m.group(1).strip()
        m = re.search(r"(\d[\d,]*)\s*円", ln)
        if m and ("1回" in ln or "価格" in ln):
            out["price_per_play"] = int(m.group(1).replace(",", ""))

    sizes = parse_sizes(text)
    out["sizes"] = sizes["sizes"]
    out["size_cm"] = sizes["size_cm"]
    out["size_text"] = sizes["size_text"]
    return out


# --------------------------------------------------------------------- 共用
def _finalize(raw_title: str, official: str | None, name_source: str,
              context_text: str, payload: dict) -> NamingResult:
    """由官方名 + 上下文文字收斂所有欄位。"""
    r = NamingResult(raw_title=raw_title, official_name=official, name_source=name_source)
    hints = payload.get("hints", {}) or {}
    primary_text = official or raw_title            # 比對優先用官方名
    combined = " ".join(x for x in (primary_text, raw_title, context_text) if x)

    # --- 廠商：hint > 文字 > 源頭預設
    maker = None
    if hints.get("maker_code"):
        maker = {"code": hints["maker_code"], "match": "hint", "method": "hint"}
    if not maker:
        maker = resolve_maker(context_text) or resolve_maker(raw_title)
    if not maker and payload.get("source") in SOURCE_MAKER_DEFAULT:
        maker = {"code": SOURCE_MAKER_DEFAULT[payload["source"]],
                 "match": payload["source"], "method": "source_default"}
    if maker:
        r.maker_code, r.maker_match, r.maker_method = (
            maker["code"], maker["match"], maker["method"])
    else:
        r.warnings.append("maker_unresolved")

    # --- 作品：hint > 官方名 > 原標題（支援一段文字多個 IP）
    ips: list[dict] = []
    if hints.get("ip_code"):
        ips = [{"code": hints["ip_code"], "match": "hint", "method": "hint"}]
    if not ips:
        for txt in (primary_text, raw_title, context_text):
            ips = resolve_ips(txt)
            if ips:
                break
    if ips:
        r.ip_code, r.ip_match, r.ip_method = (
            ips[0]["code"], ips[0]["match"], ips[0]["method"])
        r.ip_codes = [x["code"] for x in ips]
    else:
        r.warnings.append("ip_unresolved")

    # --- 尺寸
    sizes = parse_sizes(combined)
    r.size_cm, r.size_text = sizes["size_cm"], sizes["size_text"]

    # --- 系列號（羅馬數字／vol／弾）
    r.series_group = extract_series_group(official or raw_title)

    # --- 一番くじ
    r.is_kuji = detect_kuji(context_text) or bool(hints.get("is_kuji"))

    if not official:
        r.warnings.append("no_official_name")
    return r


# --------------------------------------------------------------------- bsp
def extract_bsp(raw_title: str, breadcrumb: list[str] | None = None,
                title_tag: str | None = None, spec_text: str | None = None,
                body_text: str | None = None,
                hints: dict | None = None,
                official_name_hint: str | None = None) -> NamingResult:
    """bsp-prize item 頁 / 列表卡。

    官方商品名來源優先次序：
      1. JSON-LD BreadcrumbList 最後一項（詳情頁，實測最穩）
      2. <title> 前段（去掉 ｜商品情報｜バンプレストナビサイト）
      3. official_name_hint（列表卡商品名；詳情頁唔會用到）
    """
    warnings: list[str] = []
    official = None
    source = "none"

    crumb = [c for c in (breadcrumb or []) if c]
    if crumb and len(crumb) >= 3:
        cand = crumb[-1].strip()
        if cand and cand not in ("トップページ", "作品タイトル", "商品一覧"):
            official, source = cand, "bsp_breadcrumb"

    if not official and title_tag:
        cand = title_tag.split("｜")[0].strip()
        if cand:
            official, source = cand, "bsp_title_tag"
            warnings.append("breadcrumb_missing")

    if not official and official_name_hint:
        official, source = official_name_hint.strip(), "bsp_list_card"
        warnings.append("name_from_list_card")

    # cross-check
    if official and crumb and len(crumb) >= 3:
        if normalize_text(crumb[-1]) != normalize_text(official):
            warnings.append("breadcrumb_title_mismatch")
    if official and title_tag:
        if normalize_text(title_tag.split("｜")[0]) != normalize_text(official):
            warnings.append("title_tag_mismatch")

    context = " ".join(x for x in (spec_text, body_text) if x)
    payload = {"source": "bsp-prize", "hints": hints or {}}
    r = _finalize(raw_title or (title_tag or ""), official, source,
                  context + " " + (crumb[-2] if len(crumb) >= 3 else ""), payload)
    r.warnings.extend(warnings)
    return r


# --------------------------------------------------------------------- コレトレ
def extract_kore_tore(raw_title: str, spec_rows: list[list[str]] | None = None,
                      body_text: str | None = None,
                      hints: dict | None = None) -> NamingResult:
    """コレトレ 文章頁：官方商品名喺 spec 表「商品名」欄。

    冇 spec 表（例如由月別一覽頁抓到）→ official_name = None，
    並標 warning `no_spec_table`：呢種資料**唔准做自動合併**。
    """
    warnings: list[str] = []
    spec: dict[str, str] = {}
    for row in (spec_rows or []):
        if len(row) >= 2:
            spec[normalize_text(row[0]).replace(" ", "")] = row[1].strip()

    def pick(*labels):
        for label in labels:
            key = normalize_text(label).replace(" ", "")
            if key in spec:
                return spec[key]
        return None

    official = pick("商品名", "商品名稱") or None
    source = "kore_spec_table" if official else "none"

    ctx_parts = [pick("作品名", "作品"), pick("種類"), pick("サイズ"), pick("メーカー"), body_text]
    context = " ".join(p for p in ctx_parts if p)

    payload = {"source": "kore-tore", "hints": hints or {}}
    if not spec:
        warnings.append("no_spec_table")
    elif not official:
        warnings.append("spec_missing_official_name")

    r = _finalize(raw_title, official, source, context, payload)
    r.warnings.extend(warnings)
    # 尺寸優先信 spec 表「サイズ」
    spec_size = pick("サイズ")
    if spec_size:
        s = parse_sizes(spec_size)
        if s["size_cm"] is not None:
            r.size_cm, r.size_text = s["size_cm"], spec_size
    return r


# --------------------------------------------------------------------- 電撃PF
def extract_dengeki(raw_title: str, hints: dict | None = None) -> NamingResult:
    """電撃ホビーウェブ プライズフェア 速報：只有「廠商：描述」句，冇官方商品名。

    誠實回 None —— 呢批資料只可以做「預告提示」，唔可以入正式 item 做比對。
    """
    official = None
    context = raw_title
    payload = {"source": "dengeki-prizefair", "hints": hints or {}}
    r = _finalize(raw_title, official, "dengeki_none", context, payload)
    if "no_official_name" not in r.warnings:
        r.warnings.append("no_official_name")
    r.warnings.append("report_description_only")
    return r


# --------------------------------------------------------------------- 通用
def extract_generic(raw_title: str, context_text: str | None = None,
                    hints: dict | None = None) -> NamingResult:
    payload = {"source": "generic", "hints": hints or {}}
    return _finalize(raw_title, None, "none", context_text or "", payload)


# --------------------------------------------------------------------- 入口
def run(item: dict) -> NamingResult:
    """統一分派。item 結構見 fixtures.json。"""
    extractor = item.get("extractor", "generic")
    p = item.get("payload", {})
    if extractor == "bsp":
        return extract_bsp(
            raw_title=p.get("raw_title", ""),
            breadcrumb=p.get("breadcrumb"),
            title_tag=p.get("title_tag"),
            spec_text=p.get("spec_text"),
            body_text=p.get("body_text"),
            hints=p.get("hints"))
    if extractor == "kore":
        return extract_kore_tore(
            raw_title=p.get("raw_title", ""),
            spec_rows=p.get("spec_rows"),
            body_text=p.get("body_text"),
            hints=p.get("hints"))
    if extractor == "dengeki":
        return extract_dengeki(p.get("raw_title", ""), hints=p.get("hints"))
    return extract_generic(p.get("raw_title", ""), p.get("body_text"), p.get("hints"))
