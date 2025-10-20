"""Lightweight scheduler for orchestrating recurring agent tasks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, List


@dataclass
class ScheduledJob:
    func: Callable[[], None]
    interval: timedelta
    next_run: datetime
    name: str

    def tick(self, now: datetime) -> None:
        if now >= self.next_run:
            self.func()
            self.next_run = now + self.interval


class ScheduleManager:
    def __init__(self) -> None:
        self.jobs: List[ScheduledJob] = []

    def add_cron_job(self, name: str, func: Callable[[], None], *, hours: int = 0, minutes: int = 0) -> None:
        interval = timedelta(hours=hours, minutes=minutes)
        if interval <= timedelta(0):
            raise ValueError("Interval must be positive")
        self.jobs.append(
            ScheduledJob(func=func, interval=interval, next_run=datetime.utcnow() + interval, name=name)
        )

    def run_pending(self) -> None:
        now = datetime.utcnow()
        for job in self.jobs:
            job.tick(now)


__all__ = ["ScheduleManager"]

