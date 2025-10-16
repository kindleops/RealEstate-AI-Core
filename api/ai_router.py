"""AI Router with task queue orchestration."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional


@dataclass
class AgentTask:
    agent: str
    payload: Dict[str, Any]
    next_tasks: List["AgentTask"] = field(default_factory=list)


class TaskQueue:
    def __init__(self) -> None:
        self._queue: Deque[AgentTask] = deque()

    def add(self, task: AgentTask) -> None:
        self._queue.append(task)

    def extend(self, tasks: Iterable[AgentTask]) -> None:
        for task in tasks:
            self.add(task)

    def pop(self) -> Optional[AgentTask]:
        if self._queue:
            return self._queue.popleft()
        return None

    def __bool__(self) -> bool:  # pragma: no cover - simple delegation
        return bool(self._queue)


TriggerPredicate = Callable[[Dict[str, Any]], bool]
TaskFactory = Callable[[Dict[str, Any]], AgentTask]


class AIRouter:
    def __init__(self) -> None:
        self.registry: Dict[str, Callable[[Dict[str, Any]], Optional[Iterable[AgentTask]]]] = {}
        self.triggers: List[tuple[TriggerPredicate, List[TaskFactory]]] = []
        self.queue = TaskQueue()

    def register_agent(
        self, name: str, handler: Callable[[Dict[str, Any]], Optional[Iterable[AgentTask]]]
    ) -> None:
        self.registry[name] = handler

    def register_trigger(self, predicate: TriggerPredicate, tasks: List[TaskFactory]) -> None:
        self.triggers.append((predicate, tasks))

    def submit_event(self, event: Dict[str, Any]) -> None:
        for predicate, tasks in self.triggers:
            if predicate(event):
                for factory in tasks:
                    self.queue.add(factory(event))

    def run(self) -> None:
        while task := self.queue.pop():
            handler = self.registry.get(task.agent)
            if not handler:
                continue
            result = handler(task.payload) or []
            for produced in result:
                self.queue.add(produced)
            for next_task in task.next_tasks:
                self.queue.add(next_task)


def build_chain(tasks: List[AgentTask]) -> AgentTask:
    for current, nxt in zip(tasks, tasks[1:]):
        current.next_tasks.append(nxt)
    return tasks[0]


__all__ = ["AIRouter", "AgentTask", "TaskQueue", "build_chain"]

