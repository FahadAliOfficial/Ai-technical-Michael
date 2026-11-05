from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_shopping_agent.models import Product, Requirements
from ai_shopping_agent.validation import validate_product


REQUIREMENTS = Requirements(
    category="laptop",
    max_price=1200,
    min_ram_gb=32,
    min_storage_gb=1024,
    storage_type="SSD",
)


def load_product(product_id: str) -> Product:
    items = json.loads(Path("data/catalog.json").read_text(encoding="utf-8"))
    return Product.model_validate(next(item for item in items if item["product_id"] == product_id))


@pytest.mark.parametrize(
    ("product_id", "reason"),
    [
        ("LAPTOP_004", "exceeds budget"),
        ("LAPTOP_005", "RAM"),
        ("LAPTOP_006", "storage 512GB"),
        ("LAPTOP_007", "storage type"),
        ("LAPTOP_008", "unavailable"),
        ("LAPTOP_009", "RAM specification is missing"),
        ("LAPTOP_010", "price is missing"),
        ("LAPTOP_019", "storage specification is missing"),
        ("LAPTOP_034", "category"),
        ("LAPTOP_035", "availability is unknown"),
    ],
)
def test_rejects_invalid_products(product_id: str, reason: str) -> None:
    result = validate_product(load_product(product_id), REQUIREMENTS)
    assert not result.valid
    assert any(reason in item for item in result.reasons)


@pytest.mark.parametrize("product_id", ["LAPTOP_001", "LAPTOP_012", "LAPTOP_031", "LAPTOP_032", "LAPTOP_033"])
def test_accepts_products_at_or_within_boundaries(product_id: str) -> None:
    assert validate_product(load_product(product_id), REQUIREMENTS).valid


def test_structured_ram_overrides_marketing_description() -> None:
    product = load_product("LAPTOP_011")
    assert "claims 32GB" in product.description
    assert not validate_product(product, REQUIREMENTS).valid

