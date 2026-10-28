# -*- coding: utf-8 -*-
"""ingest_run 對接層。

- `RunRecord`：同 schema `ingest_run` 一一對應（running → success/partial/failed）
- `InMemoryRepo`：測試 / 乾跑用，同時做 item 去重判斷（official_name 為鍵）
- `PostgresRepo`：真 DB 實作位置。**未接 DB 前會明確 raise，唔會靜默假裝成功。**

分流入庫規則（對應 module2 政策）：
  有 official_name           → staged（候選新增／更新）
  冇 official_name（預告）    → candidate（入 merge_candidate 隊列／預告看板）
  index_only / is_item=False → skipped（只做索引，唔入 item）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RunRecord:
    source_code: str
    started_at: datetime
    finished_at: datetime | None = None
    status: str = "running"          # running / success / partial / failed
    items_seen: int = 0
    items_new: int = 0
    items_updated: int = 0
    candidates: int = 0
    error_count: int = 0
    notes: str = ""

    def finish(self, status: str, finished_at: datetime, notes: str = "") -> "RunRecord":
        self.status = status
        self.finished_at = finished_at
        if notes:
            self.notes = notes
        return self

    def as_dict(self) -> dict:
        return {
            "source_code": self.source_code,
            "started_at": self.started_at.isoformat(timespec="seconds"),
            "finished_at": self.finished_at.isoformat(timespec="seconds") if self.finished_at else None,
            "status": self.status,
            "items_seen": self.items_seen,
            "items_new": self.items_new,
            "items_updated": self.items_updated,
            "candidates": self.candidates,
            "error_count": self.error_count,
            "notes": self.notes,
        }


@dataclass
class StagedItem:
    source_code: str
    url: str
    official_name: str
    raw_title: str
    payload: dict


@dataclass
class Candidate:
    source_code: str
    url: str
    raw_title: str
    reason: str
    payload: dict


class IngestRepo:
    """記憶體實作；同時係 repo 介面規格。"""

    def __init__(self):
        self.runs: list[RunRecord] = []
        self.staged: list[StagedItem] = []
        self.candidates: list[Candidate] = []
        self.skipped: list[dict] = []
        self._seen: set[str] = set()

    # ---- ingest_run 生命週期
    def start_run(self, source_code: str, now: datetime) -> RunRecord:
        run = RunRecord(source_code=source_code, started_at=now)
        self.runs.append(run)
        return run

    def finish_run(self, run: RunRecord) -> None:
        for i, existing in enumerate(self.runs):
            if existing is run:
                self.runs[i] = run
                return

    def history(self, source_code: str, limit: int = 20) -> list[RunRecord]:
        rows = [r for r in self.runs if r.source_code == source_code and r.status != "running"]
        return rows[-limit:]

    # ---- 分流入庫
    def stage(self, result: dict, source_code: str, url: str) -> str:
        """回傳 staged / updated / candidate / skipped。"""
        if result.get("is_item") is False or result.get("board") == "preview":
            self.skipped.append({"url": url, "why": "preview_board"})
            return "skipped"
        if result.get("status") == "index_only":
            self.skipped.append({"url": url, "why": "index_only"})
            return "skipped"

        official = (result.get("official_name") or "").strip()
        if not official:
            reason = next((w for w in result.get("warnings", []) if "official" in w or "spec" in w),
                          "no_official_name")
            self.candidates.append(Candidate(source_code, url,
                                             result.get("raw_title", ""), reason, result))
            return "candidate"

        key = official.lower()
        if key in self._seen:
            return "updated"
        self._seen.add(key)
        self.staged.append(StagedItem(source_code, url, official,
                                      result.get("raw_title", ""), result))
        return "staged"


class PostgresRepo(IngestRepo):
    """真 DB 實作位。未接 DB 時明確失敗，避免「以為寫咗」。"""

    def __init__(self, dsn: str):
        raise RuntimeError(
            "PostgresRepo 未啟用：本機未有可用 PostgreSQL（Docker engine 缺失／無網絡）。\n"
            "啟用步驟：\n"
            "  1) 裝 Docker Desktop（Linux containers）或原生 PostgreSQL\n"
            "  2) pwsh -File schema/run_local.ps1\n"
            "  3) pip install psycopg[binary] 之後喺呢個 class 補 cursor 實作\n"
            f"  dsn={dsn!r}"
        )
