"""Lightweight FastAPI-compatible interface for testing purposes."""

from .application import FastAPI
from .exceptions import HTTPException

__all__ = ["FastAPI", "HTTPException"]
