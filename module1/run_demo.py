# -*- coding: utf-8 -*-
"""模塊 #1 demo：跑 fixtures，輸出結果表 + 準確率指標。

用法：python run_demo.py
輸出：results.json / results.csv 同 console 報告
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from extract import run   # noqa: E402

FIELDS = ["official_name", "name_source", "maker_code", "ip_code", "size_cm",
          "series_group", "is_kuji"]


def main() -> int:
    data = json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))
    items = data["items"]
    preds = [run(it).to_dict() for it in items]

    rows = []
    for it, r in zip(items, preds):
        exp = it["expect"]
        diff = [f for f in FIELDS if r.get(f) != exp.get(f)]
        rows.append({
            "id": it["id"],
            "extractor": it["extractor"],
            "raw_title": r["raw_title"][:44],
            "official_name": r["official_name"],
            "name_source": r["name_source"],
            "maker_code": r["maker_code"],
            "ip_code": r["ip_code"],
            "size_cm": r["size_cm"],
            "series_group": r["series_group"],
            "is_kuji": r["is_kuji"],
            "ready_for_matching": r["ready_for_matching"],
            "warnings": ",".join(r["warnings"]),
            "diff": ",".join(diff),
        })

    # ---------------- console 表
    print("=" * 116)
    print(f"{'ID':<22}{'來源':<11}{'official_name':<40}{'maker':<16}{'ip':<15}{'size':>5}{'ok':>4}")
    print("=" * 116)
    for row in rows:
        print(f"{row['id']:<22}{row['extractor']:<11}"
              f"{str(row['official_name'] or '—')[:38]:<40}"
              f"{str(row['maker_code'] or '—'):<16}"
              f"{str(row['ip_code'] or '—'):<15}"
              f"{str(row['size_cm'] if row['size_cm'] is not None else '—'):>5}"
              f"{'OK' if not row['diff'] else 'NG':>4}")

    total = len(items)

    field_hit = {f: sum(1 for it, r in zip(items, preds)
                        if r.get(f) == it["expect"].get(f))
                 for f in FIELDS}

    by_source: dict[str, dict] = {}
    for it, r in zip(items, preds):
        s = it["extractor"]
        d = by_source.setdefault(s, {"n": 0, "name_ok": 0, "maker_ok": 0,
                                     "ip_ok": 0, "size_case": 0, "size_ok": 0})
        d["n"] += 1
        d["name_ok"] += int(r["official_name"] == it["expect"]["official_name"])
        d["maker_ok"] += int(r["maker_code"] == it["expect"]["maker_code"])
        d["ip_ok"] += int(r["ip_code"] == it["expect"]["ip_code"])
        if it["expect"]["size_cm"] is not None:
            d["size_case"] += 1
            d["size_ok"] += int(r["size_cm"] == it["expect"]["size_cm"])

    print("\n" + "-" * 60)
    print("欄位準確率")
    for f, hit in field_hit.items():
        print(f"  {f:<18} {hit:>3}/{total}  {hit / total * 100:5.1f}%")

    print("\n按來源")
    for s, d in by_source.items():
        size_txt = f"{d['size_ok']}/{d['size_case']}" if d["size_case"] else "—"
        print(f"  {s:<11} n={d['n']:<3} official_name={d['name_ok']}/{d['n']}  "
              f"maker={d['maker_ok']}/{d['n']}  ip={d['ip_ok']}/{d['n']}  size={size_txt}")

    ready = sum(1 for r in preds if r["ready_for_matching"])
    print(f"\n可以做自動比對（有 official_name）：{ready}/{total} = {ready / total * 100:.1f}%")
    print("  其餘一律入候選／人手，唔准入 L2 自動合併")

    warn: dict[str, int] = {}
    for r in preds:
        for w in r["warnings"]:
            warn[w] = warn.get(w, 0) + 1
    print("\nwarnings:", warn)

    # ---------------- 寫檔
    (HERE / "results.json").write_text(
        json.dumps({"field_accuracy": field_hit, "by_source": by_source,
                    "ready_for_matching": ready, "total": total, "rows": rows},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    with (HERE / "results.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    bad = [r["id"] for r in rows if r["diff"]]
    print(f"\n{'全部符合預期' if not bad else '有偏差：' + ', '.join(bad)}")
    for r in rows:
        if r["diff"]:
            print(f"  {r['id']}: 差異欄位 = {r['diff']}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
