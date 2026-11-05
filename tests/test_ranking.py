from ai_shopping_agent.models import Product, Requirements
from ai_shopping_agent.ranking import rank_products


def product(product_id: str, price: float, battery: float, weight: float, rating: float) -> Product:
    return Product(
        product_id=product_id,
        name=product_id,
        category="laptop",
        price=price,
        ram_gb=32,
        storage_gb=1024,
        storage_type="SSD",
        battery_hours=battery,
        weight_kg=weight,
        rating=rating,
        availability=True,
    )


def test_preferences_rank_without_changing_validity() -> None:
    requirements = Requirements(max_price=1200, preferred_battery_hours=10, preferred_max_weight_kg=1.6)
    better = product("BETTER", 1050, 13, 1.3, 4.6)
    worse = product("WORSE", 1150, 8, 2.0, 4.2)
    ranked = rank_products([worse, better], requirements)
    assert ranked[0].product.product_id == "BETTER"
    assert ranked[1].tradeoffs


def test_ranking_is_deterministic_on_ties() -> None:
    requirements = Requirements(max_price=1200)
    a = product("A", 1000, 10, 1.5, 4.0)
    b = product("B", 1000, 10, 1.5, 4.0)
    assert [item.product.product_id for item in rank_products([b, a], requirements)] == ["A", "B"]

