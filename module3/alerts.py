# -*- coding: utf-8 -*-
"""斷鏈告警：連續失敗、零產出（版面改咗）、產量大跌。

三個規則（對應模塊 #3 要求「斷鏈告警」）：
  1. `broken_link`   連續 N 次抓取失敗（N=3）→ 源頭可能死咗／封 IP
  2. `zero_items`    今次成功但 items_seen = 0 → 版面結構改咗，selector 要修
  3. `big_drop`      對比 baseline 跌超過 50%（baseline ≥ 10）→ 靜靜哋少咗貨
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

RULES = {
    "consecutive_failures": 3,
    "drop_ratio": 0.5,
    "min_baseline": 10,
}


@dataclass
class Alert:
    code: str
    level: str          # warning / critical
    source_code: str
    message: str
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"code": self.code, "level": self.level,
                "source_code": self.source_code, "message": self.message,
                "detail": self.detail}


class AlertEvaluator:
    def __init__(self, rules: dict | None = None):
        self.rules = {**RULES, **(rules or {})}

    def evaluate(self, run, history: list, baseline: int | None) -> list[Alert]:
        alerts: list[Alert] = []

        # 1) 連續失敗（history 可能已包含 current run，要跳過自己避免重複計）
        if run.status != "success":
            streak = 1
            for prev in reversed(history):
                if prev is run:
                    continue
                if prev.status == "success":
                    break
                streak += 1
            if streak >= self.rules["consecutive_failures"]:
                alerts.append(Alert(
                    "broken_link", "critical", run.source_code,
                    f"連續 {streak} 次抓取失敗（{run.notes or 'unknown'}）",
                    {"streak": streak, "notes": run.notes}))

        # 2) 零產出
        if run.status == "success" and run.items_seen == 0:
            alerts.append(Alert(
                "zero_items", "warning", run.source_code,
                "抓取成功但 0 筆資料 → 版面可能改咗，要修 selector",
                {"url": run.notes}))

        # 3) 產量大跌
        if (run.status == "success" and baseline
                and baseline >= self.rules["min_baseline"]
                and run.items_seen < baseline * self.rules["drop_ratio"]):
            alerts.append(Alert(
                "big_drop", "warning", run.source_code,
                f"產量由 {baseline} 跌到 {run.items_seen}（>50%）",
                {"baseline": baseline, "seen": run.items_seen}))

        return alerts


class AlertSink:
    def __init__(self, path: str | Path | None = None):
        self.alerts: list[Alert] = []
        self.path = Path(path) if path else None

    def emit(self, alerts: list[Alert]) -> int:
        self.alerts.extend(alerts)
        if self.path and alerts:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                for a in alerts:
                    fh.write(json.dumps(a.as_dict(), ensure_ascii=False) + "\n")
        return len(alerts)

    def drain(self) -> list[Alert]:
        out, self.alerts = self.alerts, []
        return out
