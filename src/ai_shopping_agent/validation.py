from __future__ import annotations

from .models import Product, Requirements, ValidationResult


def validate_product(product: Product, requirements: Requirements) -> ValidationResult:
    reasons: list[str] = []

    checks = (
        (requirements.category, product.category, "category is missing"),
        (requirements.max_price, product.price, "price is missing"),
        (requirements.min_ram_gb, product.ram_gb, "RAM specification is missing"),
        (requirements.min_storage_gb, product.storage_gb, "storage specification is missing"),
        (requirements.storage_type, product.storage_type, "storage type is missing"),
    )
    for required, actual, missing_reason in checks:
        if required is not None and actual is None:
            reasons.append(missing_reason)

    if requirements.category and product.category and product.category.lower() != requirements.category.lower():
        reasons.append(f"category {product.category!r} does not match {requirements.category!r}")
    if requirements.max_price is not None and product.price is not None and product.price > requirements.max_price:
        reasons.append(f"price {product.price:.2f} exceeds budget {requirements.max_price:.2f}")
    if requirements.min_ram_gb is not None and product.ram_gb is not None and product.ram_gb < requirements.min_ram_gb:
        reasons.append(f"RAM {product.ram_gb}GB is below required {requirements.min_ram_gb}GB")
    if requirements.min_storage_gb is not None and product.storage_gb is not None and product.storage_gb < requirements.min_storage_gb:
        reasons.append(f"storage {product.storage_gb}GB is below required {requirements.min_storage_gb}GB")
    if requirements.storage_type and product.storage_type and product.storage_type.upper() != requirements.storage_type.upper():
        reasons.append(f"storage type {product.storage_type} does not match required {requirements.storage_type}")
    if product.availability is not True:
        reasons.append("product is unavailable" if product.availability is False else "availability is unknown")

    return ValidationResult(product_id=product.product_id, valid=not reasons, reasons=reasons)

