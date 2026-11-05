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
        raw_score = 0.0
        raw_breakdown: dict[str, float] = {}
        maximum_score = 0.0
        tradeoffs: list[str] = []

        if requirements.preferred_battery_hours is not None:
            maximum_score += 35
            if product.battery_hours is None:
                tradeoffs.append("Battery life is not reported")
            else:
                ratio = min(product.battery_hours / requirements.preferred_battery_hours, 1.25)
                raw_breakdown["battery"] = round(35 * ratio / 1.25, 2)
                raw_score += raw_breakdown["battery"]
                if product.battery_hours < requirements.preferred_battery_hours:
                    tradeoffs.append(
                        f"Battery life {product.battery_hours:g}h is below preferred {requirements.preferred_battery_hours:g}h"
                    )
        if requirements.preferred_max_weight_kg is not None:
            maximum_score += 25
            if product.weight_kg is None:
                tradeoffs.append("Weight is not reported")
            elif product.weight_kg <= requirements.preferred_max_weight_kg:
                raw_breakdown["weight"] = 25
                raw_score += raw_breakdown["weight"]
            else:
                raw_breakdown["weight"] = round(
                    max(0, 25 - (product.weight_kg - requirements.preferred_max_weight_kg) * 25), 2
                )
                raw_score += raw_breakdown["weight"]
                tradeoffs.append(
                    f"Weight {product.weight_kg:g}kg exceeds preferred {requirements.preferred_max_weight_kg:g}kg"
                )
        maximum_score += 25
        rating = reviews.get(product.product_id).average_rating if product.product_id in reviews else product.rating
        if rating is not None:
            raw_breakdown["rating"] = round(25 * max(0, min(rating, 5)) / 5, 2)
            raw_score += raw_breakdown["rating"]
        else:
            tradeoffs.append("No rating is available")

        if requirements.max_price and product.price is not None:
            maximum_score += 15
            headroom = max(0, requirements.max_price - product.price) / requirements.max_price
            raw_breakdown["price_headroom"] = round(15 * headroom, 2)
            raw_score += raw_breakdown["price_headroom"]

        scale = 100 / maximum_score if maximum_score else 0
        breakdown = {name: round(value * scale, 2) for name, value in raw_breakdown.items()}
        score = min(100.0, round(raw_score * scale, 2))

        ranked.append(
            RankedProduct(
                product=product,
                score=score,
                score_breakdown=breakdown,
                tradeoffs=tradeoffs,
            )
        )

    return sorted(ranked, key=lambda item: (-item.score, item.product.price or float("inf"), item.product.product_id))

