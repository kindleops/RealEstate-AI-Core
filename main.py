"""Entry point for the FastAPI application."""
from __future__ import annotations

from fastapi import FastAPI

from api.routes import router as agent_router

app = FastAPI(title="Real Estate AI Core")
app.include_router(agent_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
