# -*- coding: utf-8 -*-
"""模塊 #3 測試：抓取層 / 排程 / ingest_run / 斷鏈告警。

全部用注入 transport，唔需要網絡。
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "module1"))
sys.path.insert(0, str(HERE.parent / "module2"))

import pipeline as m2_pipeline                             # noqa: E402
from alerts import AlertEvaluator, AlertSink               # noqa: E402
from fetcher import (FetchResult, HttpFetcher, RateLimiter,  # noqa: E402
                     RobotsCache, parse_robots)
from ingest import IngestRepo, PostgresRepo                # noqa: E402
from scheduler import Job, SourceRunner, plan_jobs          # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, cond, detail: str = "") -> None:
    results.append((name, bool(cond), detail))


def eq(name: str, got, want) -> None:
    check(name, got == want, f"got={got!r} want={want!r}")


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def sleep(self, d: float) -> None:
        self.t += d


def const_transport(status, body=""):
    """固定回應（用嚟模擬一直失敗嘅源頭）。"""
    return lambda url, ua, timeout: (status, body)


def seq_transport(seq):
    """依序回傳 (status, body) 或 raise 指定 exception。"""
    it = iter(seq)

    def _t(url, ua, timeout):
        item = next(it)
        if isinstance(item, Exception):
            raise item
        return item
    return _t


# ===================================================== A. fetcher
clk = FakeClock()
f = HttpFetcher(transport=seq_transport([(500, ""), (500, ""), (200, "<html>ok</html>")]),
                sleep=clk.sleep, clock=clk)
r = f.get("https://example.com/a")
eq("A01 5xx 兩次後成功", r.status, "ok")
eq("A02 attempts=3", r.attempts, 3)
check("A03 有 backoff 等待", clk.t > 0, f"clock={clk.t}")

clk2 = FakeClock()
f2 = HttpFetcher(transport=seq_transport([(404, "")]), sleep=clk2.sleep, clock=clk2)
r2 = f2.get("https://example.com/missing")
eq("A04 404 唔重試", r2.status, "http_error")
eq("A05 404 attempts=1", r2.attempts, 1)

r3 = HttpFetcher(transport=seq_transport([(429, ""), (200, "x")])).get("https://e.com/r")
eq("A06 429 會重試", (r3.status, r3.attempts), ("ok", 2))

r4 = HttpFetcher(transport=seq_transport([OSError("dns"), (200, "y")])).get("https://e.com/n")
eq("A07 網絡錯誤會重試", r4.status, "ok")

r5 = HttpFetcher(transport=seq_transport([(503, ""), (503, ""), (503, "")])).get("https://e.com/x")
eq("A08 連續失敗回 http_error", r5.status, "http_error")

# robots
eq("A09 parse_robots 抽 Disallow", parse_robots("User-agent: *\nDisallow: /private\n"), ["/private"])
eq("A10 parse_robots 忽略其他 UA",
   parse_robots("User-agent: Googlebot\nDisallow: /x\nUser-agent: *\nDisallow: /y\n"), ["/y"])

robots_t = seq_transport([(200, "User-agent: *\nDisallow: /private\n")])
rb = RobotsCache(robots_t, ua="test", clock=FakeClock())
check("A11 robots 允許普通路徑", rb.is_allowed("https://e.com/item/1"))
check("A12 robots 阻擋 Disallow 路徑", not rb.is_allowed("https://e.com/private/x"))
f6 = HttpFetcher(transport=seq_transport([(200, "should-not-fetch")]), robots=rb)
eq("A13 robots 阻擋後唔會發請求", f6.get("https://e.com/private/x").status, "blocked_by_robots")

# rate limit
clk3 = FakeClock()
lim = RateLimiter(min_interval=1.0, clock=clk3, sleep=clk3.sleep)
f7 = HttpFetcher(transport=seq_transport([(200, "a"), (200, "b")]),
                 limiter=lim, sleep=clk3.sleep, clock=clk3)
f7.get("https://same.com/1")
f7.get("https://same.com/2")
eq("A14 同 host 第二次要等 1 秒", lim.sleeps, [1.0])

# ===================================================== B. ingest 分流
repo = IngestRepo()
now = datetime(2026, 10, 28, 9, 0, 0)
run = repo.start_run("bsp_prize", now)
eq("B01 run 初始狀態", run.status, "running")

ok_row = {"official_name": "アニメ「鬼滅の刃」 MAXIMATIC GIYU TOMIOKAⅡ",
          "raw_title": "【鬼滅の刃】…", "warnings": []}
eq("B02 有官方名 → staged", repo.stage(ok_row, "bsp_prize", "https://x/1"), "staged")
eq("B03 同名重複 → updated", repo.stage(ok_row, "bsp_prize", "https://x/2"), "updated")
eq("B04 冇官方名 → candidate", repo.stage({"official_name": None, "warnings": ["no_official_name"]},
                                          "dengeki", "https://x/3"), "candidate")
eq("B05 預告板 → skipped",
   repo.stage({"official_name": None, "is_item": False, "board": "preview"}, "dengeki", "https://x/4"),
   "skipped")
eq("B06 索引 → skipped",
   repo.stage({"official_name": None, "status": "index_only"}, "kore_tore", "https://x/5"), "skipped")
eq("B07 staged 數量", len(repo.staged), 1)
eq("B08 candidate 數量", len(repo.candidates), 1)
eq("B09 candidate 帶原因", repo.candidates[0].reason, "no_official_name")


def _pg_stub():
    PostgresRepo("postgresql://localhost/x")


try:
    _pg_stub()
    check("B10 PostgresRepo 未接 DB 要明確 raise", False, "冇 raise")
except RuntimeError as e:
    check("B10 PostgresRepo 未接 DB 要明確 raise", "PostgreSQL" in str(e), str(e)[:60])

# ===================================================== C. alerts
ev = AlertEvaluator()
h_fail = [type("R", (), {"status": "failed", "items_seen": 0})() for _ in range(2)]
a = ev.evaluate(type("R", (), {"status": "failed", "source_code": "s1",
                               "notes": "http 503", "items_seen": 0})(), h_fail, None)
eq("C01 連續 3 次失敗 → broken_link", [x.code for x in a], ["broken_link"])
eq("C02 broken_link level=critical", a[0].level, "critical")

a2 = ev.evaluate(type("R", (), {"status": "success", "source_code": "s2",
                                "notes": "", "items_seen": 0})(), [], None)
check("C03 零產出 → zero_items", "zero_items" in [x.code for x in a2], str([x.code for x in a2]))

a3 = ev.evaluate(type("R", (), {"status": "success", "source_code": "s3",
                                "notes": "", "items_seen": 40})(), [], 100)
check("C04 產量跌 60% → big_drop", "big_drop" in [x.code for x in a3], str([x.code for x in a3]))

a4 = ev.evaluate(type("R", (), {"status": "success", "source_code": "s4",
                                "notes": "", "items_seen": 90})(), [], 100)
eq("C05 跌 10% 唔告警", a4, [])

_log_path = HERE / "_tmp_alerts.log"
try:
    if _log_path.exists():
        _log_path.unlink()
    sink = AlertSink(_log_path)
    sink.emit(a)
    lines = _log_path.read_text(encoding="utf-8").strip().splitlines()
    eq("C06 告警寫入檔案", len(lines), 1)
    check("C07 告警係合法 JSON", json.loads(lines[0])["code"] == "broken_link")
finally:
    if _log_path.exists():
        _log_path.unlink()

# ===================================================== D. scheduler
sources = [
    {"code": "a_daily", "crawl_mode": "auto_daily", "priority": 0, "url": "https://a/1"},
    {"code": "b_weekly", "crawl_mode": "weekly", "priority": 1, "url": "https://b/1"},
    {"code": "c_link", "crawl_mode": "link_only", "priority": 0, "url": "https://c/1"},
    {"code": "d_event", "crawl_mode": "event_driven", "priority": 1, "url": "https://d/1"},
    {"code": "e_manual", "crawl_mode": "manual", "priority": 2, "url": "https://e/1"},
    {"code": "f_nourl", "crawl_mode": "auto_daily", "priority": 2, "url": None},
]
monday = datetime(2026, 10, 26)      # 星期一
tuesday = datetime(2026, 10, 27)
jm = plan_jobs(sources, monday)
eq("D01 星期一：daily + weekly", [j.source_code for j in jm], ["a_daily", "b_weekly"])
jt = plan_jobs(sources, tuesday)
eq("D02 星期二：冇 weekly", [j.source_code for j in jt], ["a_daily"])
je = plan_jobs([{**sources[3], "force": True}], tuesday)
eq("D03 event_driven 要 force 才跑", [j.source_code for j in je], ["d_event"])

# ===================================================== E. runner
class Src:
    def __init__(self, code, mode="auto_daily", prio=0, url="https://src/1"):
        self.code, self.crawl_mode, self.priority, self.url = code, mode, prio, url


parse_ok = lambda html: [                                   # noqa: E731
    {"official_name": "商品A", "raw_title": "A", "warnings": []},
    {"official_name": "商品B", "raw_title": "B", "warnings": []},
    {"official_name": None, "raw_title": "C", "warnings": ["no_official_name"]},
]

repo2 = IngestRepo()
sink2 = AlertSink()
runner = SourceRunner(
    HttpFetcher(transport=seq_transport([(200, "<html>ok</html>")])),
    repo2, sink2, now_fn=lambda: now)
job = plan_jobs([{"code": "bsp_prize", "crawl_mode": "auto_daily",
                  "priority": 0, "url": "https://bsp-prize.jp/"}], monday)[0]
run_ok = runner.run(job, parse_ok)
eq("E01 run status=success", run_ok.status, "success")
eq("E02 items_seen", run_ok.items_seen, 3)
eq("E03 items_new", run_ok.items_new, 2)
eq("E04 candidates", run_ok.candidates, 1)
eq("E05 repo 有 run 紀錄", len(repo2.runs), 1)
eq("E06 已入庫 2 筆", len(repo2.staged), 2)
eq("E07 冇告警", sink2.alerts, [])

# 失敗源
repo3 = IngestRepo()
sink3 = AlertSink()
runner3 = SourceRunner(HttpFetcher(transport=const_transport(503)),
                       repo3, sink3, now_fn=lambda: now)
for _ in range(3):
    run_f = runner3.run(job, parse_ok)
eq("E08 失敗 run status=failed", run_f.status, "failed")
eq("E09 三次失敗後出 broken_link",
   [a.code for a in sink3.alerts], ["broken_link"])

# 解析器爆咗
repo4 = IngestRepo()
runner4 = SourceRunner(HttpFetcher(transport=seq_transport([(200, "x")])),
                       repo4, AlertSink(), now_fn=lambda: now)
run_p = runner4.run(job, lambda html: (_ for _ in ()).throw(ValueError("selector 改咗")))
eq("E10 解析器爆 → partial", run_p.status, "partial")
check("E11 解析錯誤寫入 notes", "parse_error" in run_p.notes, run_p.notes)

# ===================================================== F. 同 module2 整合
bsp_html = (HERE.parent / "module2" / "fixtures" / "bsp_top_list.html").read_text(encoding="utf-8")
parse_bsp_list = lambda html: [x["result"] for x in m2_pipeline.bsp_list(html)]   # noqa: E731
repo5 = IngestRepo()
runner5 = SourceRunner(HttpFetcher(transport=seq_transport([(200, bsp_html)])),
                       repo5, AlertSink(), now_fn=lambda: now)
run_i = runner5.run(Job("bsp_prize", "auto_daily", 0, "https://bsp-prize.jp/"), parse_bsp_list)
eq("F01 列表 3 款全部入庫", run_i.items_new, 3)
eq("F02 items_seen=3", run_i.items_seen, 3)
eq("F03 官方名保留", repo5.staged[0].official_name, "DRAGON BALL SPIRITFLICKS 03")
eq("F04 raw_title 亦保留", repo5.staged[0].raw_title, "DRAGON BALL SPIRITFLICKS 03")

# ===================================================== 輸出
print("=" * 86)
width = max(len(n) for n, _, _ in results)
passed = 0
for name, ok, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name:<{width}}  {detail}")
    passed += ok
print("=" * 86)
print(f"passed={passed} failed={len(results) - passed} total={len(results)}")
if passed != len(results):
    sys.exit(1)
print("模塊 #3 全部測試通過")

