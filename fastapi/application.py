from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, Dict, Tuple


class FastAPI:
    """A minimal subset of FastAPI used for unit testing."""

    def __init__(self, title: str, version: str):
        self.title = title
        self.version = version
        self.state = SimpleNamespace()
        self._routes: Dict[Tuple[str, str], Callable[..., Any]] = {}

    def _register(self, method: str, path: str, handler: Callable[..., Any]) -> Callable[..., Any]:
        self._routes[(method.upper(), path)] = handler
        return handler

    def get(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            return self._register("GET", path, func)

        return decorator

    def post(self, path: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            return self._register("POST", path, func)

        return decorator

    def resolve(self, method: str, path: str) -> Callable[..., Any] | None:
        return self._routes.get((method.upper(), path))
