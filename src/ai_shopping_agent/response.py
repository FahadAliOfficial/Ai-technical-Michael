from __future__ import annotations

from .models import RankedProduct, Recommendation


def success_response(ranked: list[RankedProduct], limitations: list[str] | None = None) -> Recommendation:
    best = ranked[0]
    alternatives = ranked[1:3]
    message = (
        f"I recommend {best.product.name} at ${best.product.price:,.2f}. "
        f"It satisfies every mandatory constraint and scored {best.score:.2f}/100 on preferences."
    )
    return Recommendation(
        status="success",
        message=message,
        recommended=best,
        alternatives=alternatives,
        limitations=limitations or [],
    )

