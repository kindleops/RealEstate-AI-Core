from __future__ import annotations

import inspect
from dataclasses import is_dataclass
from typing import Any, Dict, get_type_hints

from .application import FastAPI
from .exceptions import HTTPException


class Response:
    def __init__(self, data: Any, status_code: int = 200):
        self._data = data
        self.status_code = status_code

    def json(self) -> Any:
        return self._data


class TestClient:
    """Very small subset of FastAPI's TestClient for unit tests."""

    def __init__(self, app: FastAPI):
        self.app = app

    def get(self, path: str) -> Response:
        handler = self.app.resolve("GET", path)
        if handler is None:
            return Response({"detail": "Not Found"}, status_code=404)

        try:
            result = handler()
            return Response(result, status_code=200)
        except HTTPException as exc:
            return Response({"detail": exc.detail}, status_code=exc.status_code)

    def post(self, path: str, json: Dict[str, Any] | None = None) -> Response:
        handler = self.app.resolve("POST", path)
        if handler is None:
            return Response({"detail": "Not Found"}, status_code=404)

        json_payload = json or {}
        try:
            arguments = self._build_arguments(handler, json_payload)
            result = handler(*arguments)
            return Response(result, status_code=200)
        except HTTPException as exc:
            return Response({"detail": exc.detail}, status_code=exc.status_code)

    def _build_arguments(self, handler, payload: Dict[str, Any]) -> tuple[Any, ...]:
        signature = inspect.signature(handler)
        params = list(signature.parameters.values())
        if not params:
            return tuple()

        param = params[0]
        hints = get_type_hints(handler)
        annotation = hints.get(param.name, param.annotation)
        if annotation is inspect._empty:
            return (payload,)

        if is_dataclass(annotation):
            return (annotation(**payload),)

        if hasattr(annotation, "__annotations__"):
            return (annotation(**payload),)

        return (payload,)
