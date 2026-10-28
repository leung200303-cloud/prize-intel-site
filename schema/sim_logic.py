# -*- coding: utf-8 -*-
"""DB 邏輯模擬驗證（冇真 Postgres 時嘅替代驗證）。

模擬 01_schema.sql 入面嘅以下機制，用同一套規則跑測試矩陣：
  - item_before_write()：normalized_title / title_hash / match_fingerprint
  - enforce_price_ref_cap()：每款 3 條上限、淘汰次序（先成交樣本、再最舊）
  - uq_price_baseline：每平台基準線唯一（配 UPSERT）
  - chk_item_no_self_parent / prevent_parent_cycle()：自我引用 + A→B→C→A 循環
  - chk_kuji_pool_has_no_parent / chk_prize_tier_needs_parent / chk_kuji_parent_channel

⚠️ 呢個唔係取代真 PG：佢驗證「規則推論」，唔驗證 SQL 語法、型別、約束互動。
   真 PG 一上線就要即刻跑 tests.sql。
"""
from __future__ import annotations

import hashlib
import sys

ZEN2HAN = {chr(0xFF01 + i): chr(0x21 + i) for i in range(94)}
STRIP = set("　【】[]（）()「」『』・･-–—_/／:：!！?？★☆♪♡♥、,，.。~〜 ")


def kana_fold(s: str) -> str:
    return "".join(chr(ord(c) - 96) if 0x30A1 <= ord(c) <= 0x30F6 else c for c in s)


def normalize_title(t: str) -> str:
    s = "".join(ZEN2HAN.get(c, c) for c in t)
    s = kana_fold(s).lower()
    return "".join(c for c in s if c not in STRIP)


def compute_fingerprint(maker, brand, ip, char, month, series, size):
    bucket = None if size is None else round(size / 5) * 5
    raw = "|".join([
        maker or "", brand or "", ip or "", char or "", month or "",
        normalize_title(series) if series else "NA",
        str(bucket) if bucket is not None else "NA",
    ])
    return hashlib.sha256(raw.encode()).hexdigest()


class UniqueViolation(Exception):
    pass


class CheckViolation(Exception):
    pass


class PriceRefStore:
    """模擬 price_ref 表 + 兩個觸發器行為。"""

    def __init__(self):
        self.rows: list[dict] = []
        self._seq = 0

    # ---- uq_price_baseline（partial unique index）
    def _baseline_exists(self, item_id, platform):
        return any(r["item_id"] == item_id and r["platform"] == platform
                   and r["basis"] == "reference_price" for r in self.rows)

    # ---- enforce_price_ref_cap（BEFORE INSERT）
    def _enforce_cap(self, item_id):
        mine = [r for r in self.rows if r["item_id"] == item_id]
        if len(mine) >= 3:
            # 排序：成交樣本先（False < True）、再最舊、再 id
            mine.sort(key=lambda r: (r["basis"] == "reference_price",
                                     r["captured_at"], r["id"]))
            evict = len(mine) - 2
            for r in mine[:evict]:
                self.rows.remove(r)

    def insert(self, item_id, platform, basis, price, captured_at):
        if basis == "reference_price" and self._baseline_exists(item_id, platform):
            raise UniqueViolation("uq_price_baseline")
        self._enforce_cap(item_id)
        self._seq += 1
        self.rows.append({"id": self._seq, "item_id": item_id, "platform": platform,
                          "basis": basis, "price": price, "captured_at": captured_at})

    def upsert_baseline(self, item_id, platform, price, captured_at):
        for r in self.rows:
            if (r["item_id"] == item_id and r["platform"] == platform
                    and r["basis"] == "reference_price"):
                r["price"], r["captured_at"] = price, captured_at
                return
        self._enforce_cap(item_id)
        self._seq += 1
        self.rows.append({"id": self._seq, "item_id": item_id, "platform": platform,
                          "basis": "reference_price", "price": price,
                          "captured_at": captured_at})

    def count(self, item_id):
        return sum(1 for r in self.rows if r["item_id"] == item_id)

    def platforms(self, item_id):
        return [r["platform"] for r in self.rows if r["item_id"] == item_id]


class ItemStore:
    """模擬 item 表嘅 parent 約束 + 循環偵測。"""

    MAX_DEPTH = 5

    def __init__(self):
        self.items: dict[str, dict] = {}

    def add(self, item_id, channel="prize", is_pool=False, parent=None, prize_tier=None):
        if is_pool and parent is not None:
            raise CheckViolation("chk_kuji_pool_has_no_parent")
        if prize_tier is not None and parent is None:
            raise CheckViolation("chk_prize_tier_needs_parent")
        if parent is not None and channel != "ichiban_kuji":
            raise CheckViolation("chk_kuji_parent_channel")
        if parent is not None:
            self._check_cycle(item_id, parent)
        self.items[item_id] = {"channel": channel, "is_pool": is_pool,
                               "parent": parent, "prize_tier": prize_tier}

    def _check_cycle(self, item_id, parent):
        if parent == item_id:
            raise CheckViolation("chk_item_no_self_parent")
        depth, cursor = 0, parent
        while cursor is not None:
            if cursor == item_id:
                raise CheckViolation("prevent_parent_cycle: 循環引用")
            depth += 1
            if depth > self.MAX_DEPTH:
                raise CheckViolation("prevent_parent_cycle: 層級過深")
            nxt = self.items.get(cursor)
            cursor = nxt["parent"] if nxt else None

    def set_parent(self, item_id, parent):
        me = self.items[item_id]
        if parent is not None:
            if me["is_pool"]:
                raise CheckViolation("chk_kuji_pool_has_no_parent")
            if me["channel"] != "ichiban_kuji":
                raise CheckViolation("chk_kuji_parent_channel")
            self._check_cycle(item_id, parent)
        me["parent"] = parent


# --------------------------------------------------------------------- 測試
results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, cond, detail))


def expect_raise(name: str, fn, exc_type, detail_contains: str = "") -> None:
    try:
        fn()
    except exc_type as e:
        ok = detail_contains in str(e) if detail_contains else True
        check(name, ok, f"raised {type(e).__name__}: {e}")
    except Exception as e:  # noqa: BLE001
        check(name, False, f"raised 錯類型 {type(e).__name__}: {e}")
    else:
        check(name, False, "冇 raise（唔應該成功）")


# ---- A. price_ref 3 條上限
s = PriceRefStore()
ITEM = "item-1"
s.insert(ITEM, "surugaya", "reference_price", 5000, "2026-10-01")
s.insert(ITEM, "mercari", "sold_sample", 6000, "2026-10-05")
s.insert(ITEM, "yahoo_auction", "sold_sample", 7000, "2026-10-10")
check("A1 3 條樣本", s.count(ITEM) == 3, f"count={s.count(ITEM)}")

s.insert(ITEM, "paypay_flea", "sold_sample", 8000, "2026-10-12")
check("A2 插第 4 條後仍然 3 條", s.count(ITEM) == 3, f"count={s.count(ITEM)}")
check("A3 最舊成交樣本（mercari）被淘汰", "mercari" not in s.platforms(ITEM), str(s.platforms(ITEM)))
check("A4 surugaya 基準線保留", "surugaya" in s.platforms(ITEM), str(s.platforms(ITEM)))
check("A5 最新樣本（paypay）保留", "paypay_flea" in s.platforms(ITEM), str(s.platforms(ITEM)))

expect_raise("A6 同平台基準線重複要報錯",
             lambda: s.insert(ITEM, "surugaya", "reference_price", 5200, "2026-10-20"),
             UniqueViolation)

s.upsert_baseline(ITEM, "surugaya", 4800, "2026-10-20")
base = [r for r in s.rows if r["item_id"] == ITEM and r["basis"] == "reference_price"][0]
check("A7 UPSERT 基準線成功", base["price"] == 4800, f"price={base['price']}")

# 全部係成交樣本時，淘汰最舊
s2 = PriceRefStore()
for i, p in enumerate(["mercari", "yahoo_auction", "paypay_flea"], start=1):
    s2.insert("item-2", p, "sold_sample", 1000 * i, f"2026-10-0{i}")
s2.insert("item-2", "other", "sold_sample", 9000, "2026-10-09")
check("A8 無基準線時淘汰最舊樣本", "mercari" not in s2.platforms("item-2"), str(s2.platforms("item-2")))

# ---- B. 一番くじ 約束
it = ItemStore()
it.add("pool", channel="ichiban_kuji", is_pool=True)
it.add("prizeA", channel="ichiban_kuji", parent="pool", prize_tier="A賞")
check("B1 賞品掛池成功", it.items["prizeA"]["parent"] == "pool")

expect_raise("B2 獎池有 parent 要報錯",
             lambda: it.set_parent("pool", "prizeA"), CheckViolation, "chk_kuji_pool_has_no_parent")
expect_raise("B3 prize_tier 冇 parent 要報錯",
             lambda: it.add("orphan", channel="ichiban_kuji", prize_tier="B賞"),
             CheckViolation, "chk_prize_tier_needs_parent")
expect_raise("B4 prize 通道掛池要報錯",
             lambda: it.add("bad", channel="prize", parent="pool", prize_tier="C賞"),
             CheckViolation, "chk_kuji_parent_channel")

# ---- C. 循環 parent
it.add("L1", channel="ichiban_kuji")
it.add("L2", channel="ichiban_kuji", parent="L1", prize_tier="L2")
it.add("L3", channel="ichiban_kuji", parent="L2", prize_tier="L3")
check("C1 三層鏈建立成功", it.items["L3"]["parent"] == "L2")

expect_raise("C2 A→B→C→A 循環要報錯",
             lambda: it.set_parent("L1", "L3"), CheckViolation, "循環")
expect_raise("C3 自我引用要報錯",
             lambda: it.set_parent("L1", "L1"), CheckViolation, "chk_item_no_self_parent")

# 深度 > 5
deep = ItemStore()
prev = None
for i in range(1, 8):
    nid = f"D{i}"
    if prev is None:
        deep.add(nid, channel="ichiban_kuji")
    else:
        try:
            deep.add(nid, channel="ichiban_kuji", parent=prev, prize_tier=f"T{i}")
        except CheckViolation as e:
            check("C4 層級過深要報錯", "過深" in str(e), str(e))
            break
    prev = nid
else:
    check("C4 層級過深要報錯", False, "深到 7 層都冇 raise")

it.set_parent("L3", "pool")
check("C5 正常改 parent 成功", it.items["L3"]["parent"] == "pool",
      f"parent={it.items['L3']['parent']}")

# ---- D. 指紋（L2 前提）
fp1 = compute_fingerprint("bandai_spirits", "maximatic", "kimetsu", None, "2026-10", None, 19)
fp2 = compute_fingerprint("bandai_spirits", "maximatic", "kimetsu", None, "2026-10", None, 19)
fp3 = compute_fingerprint("bandai_spirits", "luminasta", "kimetsu", None, "2026-10", None, 19)
fp4 = compute_fingerprint("bandai_spirits", "maximatic", "kimetsu", None, "2026-10", None, 20)
check("D1 同 spec → 指紋相同", fp1 == fp2)
check("D2 唔同系列線 → 指紋唔同", fp1 != fp3)
check("D3 19cm vs 20cm 落入同一 5cm 桶 → 指紋相同", fp1 == fp4,
      "size bucket 設計如此，配合 series_group 防誤併")

# ---- 輸出
print("=" * 72)
width = max(len(n) for n, _, _ in results)
passed = 0
for name, ok, detail in results:
    mark = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    print(f"[{mark}] {name:<{width}}  {detail}")
print("=" * 72)
print(f"passed={passed} failed={len(results) - passed} total={len(results)}")

if passed != len(results):
    sys.exit(1)
print("✅ DB 邏輯模擬全部通過（真 PG 上線後仍要跑 tests.sql）")
