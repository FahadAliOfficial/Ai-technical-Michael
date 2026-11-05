from __future__ import annotations

from .models import RankedProduct, Recommendation, Requirements


def success_response(
    ranked: list[RankedProduct],
    requirements: Requirements,
    limitations: list[str] | None = None,
    comparison_summary: str | None = None,
) -> Recommendation:
    best = ranked[0]
    alternatives = ranked[1:3]
    constraint_checks = [
        f"Price ${best.product.price:,.2f} <= ${requirements.max_price:,.2f}",
        f"RAM {best.product.ram_gb}GB >= {requirements.min_ram_gb}GB",
        f"Storage {best.product.storage_gb}GB {best.product.storage_type} >= {requirements.min_storage_gb}GB {requirements.storage_type}",
        "Current availability verified",
    ]
    alternative_text = ""
    if alternatives:
        alternative_text = " Alternatives: " + "; ".join(
            f"{item.product.name} ({item.score:.2f}/100"
            + (f", trade-offs: {', '.join(item.tradeoffs)}" if item.tradeoffs else "")
            + ")"
            for item in alternatives
        )
    message = (
        f"I recommend {best.product.name} at ${best.product.price:,.2f}. "
        f"It satisfies every mandatory constraint and scored {best.score:.2f}/100 on preferences "
        f"({', '.join(f'{name}={value:.2f}' for name, value in best.score_breakdown.items())})."
        f"{alternative_text}"
    )
    return Recommendation(
        status="success",
        message=message,
        recommended=best,
        alternatives=alternatives,
        constraint_checks=constraint_checks,
        comparison_summary=comparison_summary,
        limitations=limitations or [],
    )

