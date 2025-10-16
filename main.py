"""FastAPI application wiring agent endpoints together."""

from __future__ import annotations

from fastapi import FastAPI

from agents import (
    cash_offer_generator_agent,
    creative_finance_agent,
    inbound_leads_agent,
    multifamily_score_agent,
    repair_cost_estimator_agent,
    skiptrace_quality_agent,
    tax_lien_agent,
    vacancy_check_agent,
)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    app = FastAPI(title="Real Estate AI Core", version="0.1.0")

    app.include_router(inbound_leads_agent.router, prefix="/agents", tags=["inbound"])
    app.include_router(tax_lien_agent.router, prefix="/agents", tags=["tax-lien"])
    app.include_router(vacancy_check_agent.router, prefix="/agents", tags=["vacancy"])
    app.include_router(multifamily_score_agent.router, prefix="/agents", tags=["multifamily"])
    app.include_router(creative_finance_agent.router, prefix="/agents", tags=["creative-finance"])
    app.include_router(cash_offer_generator_agent.router, prefix="/agents", tags=["cash-offer"])
    app.include_router(skiptrace_quality_agent.router, prefix="/agents", tags=["skiptrace"])
    app.include_router(repair_cost_estimator_agent.router, prefix="/agents", tags=["repairs"])

    return app


app = create_app()
