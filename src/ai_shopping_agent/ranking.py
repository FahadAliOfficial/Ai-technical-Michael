from __future__ import annotations

from .models import Product, RankedProduct, Requirements, ReviewSummary


def rank_products(
    products: list[Product],
    requirements: Requirements,
    reviews: dict[str, ReviewSummary] | None = None,
) -> list[RankedProduct]:
    reviews = reviews or {}
    ranked: list[RankedProduct] = []

    for product in products:
        score = 0.0
        breakdown: dict[str, float] = {}
        tradeoffs: list[str] = []

        if requirements.preferred_battery_hours is not None:
            if product.battery_hours is None:
                tradeoffs.append("Battery life is not reported")
            else:
                ratio = min(product.battery_hours / requirements.preferred_battery_hours, 1.25)
                breakdown["battery"] = round(35 * ratio / 1.25, 2)
                score += breakdown["battery"]
                if product.battery_hours < requirements.preferred_battery_hours:
                    tradeoffs.append(
                        f"Battery life {product.battery_hours:g}h is below preferred {requirements.preferred_battery_hours:g}h"
                    )
        else:
            breakdown["battery"] = 20
            score += breakdown["battery"]

        if requirements.preferred_max_weight_kg is not None:
            if product.weight_kg is None:
                tradeoffs.append("Weight is not reported")
            elif product.weight_kg <= requirements.preferred_max_weight_kg:
                breakdown["weight"] = 25
                score += breakdown["weight"]
            else:
                breakdown["weight"] = round(
                    max(0, 25 - (product.weight_kg - requirements.preferred_max_weight_kg) * 25), 2
                )
                score += breakdown["weight"]
                tradeoffs.append(
                    f"Weight {product.weight_kg:g}kg exceeds preferred {requirements.preferred_max_weight_kg:g}kg"
                )
        else:
            breakdown["weight"] = 15
            score += breakdown["weight"]

        rating = reviews.get(product.product_id).average_rating if product.product_id in reviews else product.rating
        if rating is not None:
            breakdown["rating"] = round(25 * max(0, min(rating, 5)) / 5, 2)
            score += breakdown["rating"]
        else:
            tradeoffs.append("No rating is available")

        if requirements.max_price and product.price is not None:
            headroom = max(0, requirements.max_price - product.price) / requirements.max_price
            breakdown["price_headroom"] = round(15 * headroom, 2)
            score += breakdown["price_headroom"]

        ranked.append(
            RankedProduct(
                product=product,
                score=round(score, 2),
                score_breakdown=breakdown,
                tradeoffs=tradeoffs,
            )
        )

    return sorted(ranked, key=lambda item: (-item.score, item.product.price or float("inf"), item.product.product_id))

