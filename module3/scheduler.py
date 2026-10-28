# -*- coding: utf-8 -*-
"""排程器 + 單源執行器。

排程規則（對應 `source.crawl_mode`）：
  auto_daily    每日一次（由外部 cron 觸發；呢度負責「今日要跑邊啲源」）
  weekly        逢星期一
  event_driven  只在 force=True（プライズフェア 年 4 回，人手觸發）
  link_only / manual / skip  唔產生 job
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from alerts import AlertEvaluator, AlertSink
from fetcher import HttpFetcher
from ingest import IngestRepo, RunRecord


@dataclass
class Job:
    source_code: str
    crawl_mode: str
    priority: int
    url: str


def plan_jobs(sources: list[dict], now: datetime) -> list[Job]:
    jobs: list[Job] = []
    for s in sources:
        mode = s.get("crawl_mode") or "skip"
        url = s.get("url")
        if not url:
            continue
        if mode == "auto_daily":
            due = True
        elif mode == "weekly":
            due = now.weekday() == 0
        elif mode == "event_driven":
            due = bool(s.get("force"))
        else:
            due = False
        if due:
            jobs.append(Job(s["code"], mode, int(s.get("priority", 2)), url))
    jobs.sort(key=lambda j: (j.priority, j.source_code))
    return jobs


class SourceRunner:
    """單一源頭：抓 → 解析 → 分流入庫 → 寫 ingest_run → 評估告警。"""

    def __init__(self, fetcher: HttpFetcher, repo: IngestRepo,
                 sink: AlertSink | None = None,
                 evaluator: AlertEvaluator | None = None,
                 now_fn=datetime.now):
        self.fetcher = fetcher
        self.repo = repo
        self.sink = sink or AlertSink()
        self.evaluator = evaluator or AlertEvaluator()
        self._now = now_fn

    def _baseline(self, source_code: str) -> int | None:
        for run in reversed(self.repo.history(source_code, limit=30)):
            if run.status == "success" and run.items_seen > 0:
                return run.items_seen
        return None

    def run(self, job: Job, parse_fn) -> RunRecord:
        run = self.repo.start_run(job.source_code, self._now())

        fetch = self.fetcher.get(job.url)
        if not fetch.ok:
            run.error_count += 1
            run.finish("failed", self._now(),
                       notes=f"{fetch.status}: {fetch.error or ''}".strip(": "))
            self.repo.finish_run(run)
            self.sink.emit(self.evaluator.evaluate(
                run, self.repo.history(job.source_code), None))
            return run

        baseline = self._baseline(job.source_code)
        try:
            rows = parse_fn(fetch.html) or []
        except Exception as e:                        # noqa: BLE001 - 解析器爆咗要記落 run
            run.error_count += 1
            run.finish("partial", self._now(), notes=f"parse_error: {type(e).__name__}: {e}")
            self.repo.finish_run(run)
            self.sink.emit(self.evaluator.evaluate(run, self.repo.history(job.source_code), baseline))
            return run

        run.items_seen = len(rows)
        for row in rows:
            outcome = self.repo.stage(row, job.source_code, job.url)
            if outcome == "staged":
                run.items_new += 1
            elif outcome == "updated":
                run.items_updated += 1
            elif outcome == "candidate":
                run.candidates += 1

        status = "success" if run.error_count == 0 else "partial"
        run.finish(status, self._now(), notes=f"attempts={fetch.attempts}")
        self.repo.finish_run(run)

        self.sink.emit(self.evaluator.evaluate(
            run, self.repo.history(job.source_code), baseline))
        return run
