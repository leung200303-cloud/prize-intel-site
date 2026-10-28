# -*- coding: utf-8 -*-
"""離線 SQL 結構檢查（冇得開 Postgres 時嘅最低保障）。

檢查項：
 1. BEGIN / COMMIT 配對、括號平衡
 2. CREATE TYPE 嘅 enum 名 vs 欄位用到嘅型別
 3. REFERENCES 指向嘅表存在
 4. trigger 引用嘅 function 存在
 5. translate() 兩邊字串長度一致（正規化函式最易錯）
 6. 私隱閘：唔准出現 user / query_log 類表
 7. INSERT 欄位數 vs VALUES 值數
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SCHEMA = Path(r"prize-intel\schema\01_schema.sql")
SEED = Path(r"prize-intel\schema\02_seed.sql")

BASE_TYPES = {
    "uuid", "bigserial", "serial", "bigint", "integer", "int", "smallint",
    "text", "varchar", "char", "numeric", "decimal", "boolean", "bool",
    "date", "timestamp", "timestamptz", "jsonb", "json", "tsvector",
    "bytea", "interval", "in", "out",
}
FORBIDDEN_TABLES = {
    "user", "users", "account", "accounts", "session", "sessions",
    "query_log", "query_logs", "search_history", "search_log",
    "purchase_record", "purchase_records", "favorite", "favorites",
    "user_profile", "analytics_event", "analytics_events",
}

errors: list[str] = []
warns: list[str] = []


def err(m):
    errors.append(m)


def warn(m):
    warns.append(m)


sql = SCHEMA.read_text(encoding="utf-8")
seed = SEED.read_text(encoding="utf-8") if SEED.exists() else ""

# ---- 1. 交易塊 / 括號
if sql.count("BEGIN;") != 1 or sql.count("COMMIT;") != 1:
    err(f"BEGIN/COMMIT 數量異常：BEGIN={sql.count('BEGIN;')} COMMIT={sql.count('COMMIT;')}")
if sql.count("(") != sql.count(")"):
    err(f"括號不平衡：{sql.count('(')} vs {sql.count(')')}")

# ---- 2/3/4. 收集宣告
enums = set(re.findall(r"CREATE TYPE (\w+) AS ENUM", sql))
tables = set(re.findall(r"CREATE TABLE (\w+)", sql))
views = set(re.findall(r"CREATE (?:MATERIALIZED )?VIEW (\w+)", sql))
funcs = set(re.findall(r"CREATE OR REPLACE FUNCTION (\w+)", sql))
triggers = set(re.findall(r"CREATE TRIGGER (\w+)", sql))
known = tables | views

if not enums:
    err("冇 CREATE TYPE")
if len(triggers) != len(set(triggers)):
    warn("有 trigger 名重複")

# 私隱閘
for t in tables & FORBIDDEN_TABLES:
    err(f"[私隱閘] 出現禁止嘅使用者資料表：{t}")

# REFERENCES
for tgt in re.findall(r"REFERENCES\s+(\w+)", sql):
    if tgt not in known:
        err(f"REFERENCES 指向唔存在嘅表/視圖：{tgt}")

# EXECUTE FUNCTION
for fn in re.findall(r"EXECUTE FUNCTION (\w+)", sql):
    if fn not in funcs:
        err(f"trigger 引用唔存在嘅 function：{fn}")

# ---- 欄位型別
body_blocks = re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", sql, re.S)
if len(body_blocks) != len(tables):
    warn(f"表 body 解析到 {len(body_blocks)} / {len(tables)} 個")

cols_checked = 0
for tname, block in body_blocks:
    for raw in block.split("\n"):
        line = raw.strip()
        if not line or line.startswith("--"):
            continue
        if re.match(r"^(CONSTRAINT|PRIMARY KEY|UNIQUE|CHECK|FOREIGN KEY|EXCLUDE)\b", line):
            continue
        m = re.match(r"^(\w+)\s+([\w]+)", line)
        if not m:
            continue
        col, typ = m.group(1), m.group(2)
        cols_checked += 1
        if typ in BASE_TYPES or typ in enums:
            continue
        err(f"{tname}.{col} 型別未定義：{typ}")

# ---- 5. translate 長度
m = re.search(r"translate\(\s*coalesce\(p_text, ''\),\s*'([^']+)',\s*'([^']+)'\s*\)", sql, re.S)
if not m:
    err("搵唔到 translate() 呼叫")
else:
    src, dst = m.group(1), m.group(2)
    if len(src) != len(dst):
        err(f"translate 長度唔一致：{len(src)} vs {len(dst)}")
    else:
        print(f"  translate OK: {len(src)} chars each")

# ---- 6. seed INSERT 欄位數
for stmt in re.findall(r"INSERT INTO (\w+) \(([^)]*)\) VALUES(.*?)ON CONFLICT", seed, re.S):
    tbl, cols, vals = stmt
    ncols = len([c for c in cols.split(",") if c.strip()])
    tuples = re.findall(r"^\s*\((.*)\),?\s*$", vals, re.M)
    for t in tuples:
        depth, n, in_str = 0, 1, False
        i = 0
        while i < len(t):
            ch = t[i]
            if ch == "'":
                if in_str and i + 1 < len(t) and t[i + 1] == "'":
                    i += 2
                    continue
                in_str = not in_str
            elif not in_str:
                if ch in "([":
                    depth += 1
                elif ch in ")]":
                    depth -= 1
                elif ch == "," and depth == 0:
                    n += 1
            i += 1
        if n != ncols:
            err(f"seed {tbl}: 欄位 {ncols} vs 值 {n} → {t[:70]}")

# ---- 視圖引欄位存在性（粗檢）
item_cols = set()
for tname, block in body_blocks:
    if tname == "item":
        for raw in block.split("\n"):
            m2 = re.match(r"^\s*(\w+)\s+[\w(]", raw)
            if m2:
                item_cols.add(m2.group(1))
for ref in re.findall(r"\bi\.(\w+)", sql):
    if ref not in item_cols:
        err(f"視圖引用 item.{ref} 唔存在")

# ---- 輸出
print(f"\n表={len(tables)} 視圖={len(views)} enum={len(enums)} "
      f"function={len(funcs)} trigger={len(triggers)} 欄位檢查={cols_checked}")
print("tables:", ", ".join(sorted(tables)))
if warns:
    print("\nWARN:")
    for w in warns:
        print("  -", w)
if errors:
    print("\nERROR:")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print("\n✅ 結構檢查全部通過")
