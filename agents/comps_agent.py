"""Agent that generates comparable sales data."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List

from logger import get_logger
from utils.model_selector import ModelSelector

LOGGER = get_logger()


@dataclass
class Comp:
    address: str
    sale_price: float
    sale_date: str
    beds: int
    baths: float
    sqft: int


class CompsAgent:
    """Produce mock comparable sales and estimated ARV."""

    def __init__(self, model_selector: ModelSelector | None = None) -> None:
        self.model_selector = model_selector or ModelSelector()

    def generate_comps(self, payload: Dict[str, object]) -> Dict[str, Any]:
        address = payload.get("address", "Unknown Property")
        zip_code = payload.get("zip", "00000")
        beds = int(payload.get("beds", 3) or 3)
        baths = float(payload.get("baths", 2) or 2)
        sqft = int(payload.get("sqft", 1500) or 1500)

        model_choice = self.model_selector.choose()
        LOGGER.info(
            "Generating comps for %s using %s provider", address, model_choice.provider_type
        )

        comps = self._mock_comps(address, zip_code, beds, baths, sqft)
        average_price = sum(comp.sale_price for comp in comps) / len(comps)
        return {
            "address": address,
            "zip": zip_code,
            "comps": [comp.__dict__ for comp in comps],
            "arv": round(average_price, 2),
            "model_used": model_choice.name,
            "provider_type": model_choice.provider_type,
        }

    @staticmethod
    def _mock_comps(address: str, zip_code: str, beds: int, baths: float, sqft: int) -> List[Comp]:
        base_price = 120 * sqft
        adjustments = [(-15000, -0.05), (5000, 0.02), (20000, 0.07)]
        base_date = date.today()
        comps: List[Comp] = []
        for idx, (price_adj, ratio) in enumerate(adjustments, start=1):
            sale_price = max(base_price + price_adj + (beds * 5000) + (baths * 3500), 50000)
            sale_date = base_date - timedelta(days=idx * 17)
            comp_address = f"{address.split()[0]} Comp {idx}, {zip_code}"
            comps.append(
                Comp(
                    address=comp_address,
                    sale_price=round(sale_price * (1 + ratio), 2),
                    sale_date=sale_date.isoformat(),
                    beds=beds,
                    baths=baths,
                    sqft=sqft + idx * 50,
                )
            )
        return comps


__all__ = ["CompsAgent", "Comp"]
