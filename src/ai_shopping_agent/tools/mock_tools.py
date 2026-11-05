from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from ..models import Product, ReviewSummary, ToolCallRecord
from .adapter import SchemaValidationError, normalize_arguments, validate_arguments
from .registry import ToolDefinition, ToolRegistry


class ToolExecutionError(RuntimeError):
    def __init__(
        self,
        message: str,
        records: list[ToolCallRecord] | None = None,
        *,
        retryable: bool = False,
        code: str = "tool_error",
    ) -> None:
        super().__init__(message)
        self.records = records or []
        self.retryable = retryable
        self.code = code


@dataclass(frozen=True, slots=True)
class QueuedFailure:
    message: str
    retryable: bool
    code: str


class MockToolEnvironment:
    def __init__(
        self,
        catalog_path: str | Path,
        inventory_path: str | Path,
        reviews_path: str | Path,
    ) -> None:
        self.catalog = {
            item["product_id"]: item
            for item in json.loads(Path(catalog_path).read_text(encoding="utf-8"))
        }
        self.inventory = json.loads(Path(inventory_path).read_text(encoding="utf-8"))
        self.reviews = json.loads(Path(reviews_path).read_text(encoding="utf-8"))
        self.failures: dict[str, list[QueuedFailure]] = {}
        self.price_sequences: dict[str, list[float]] = {}

    def queue_failure(
        self,
        tool_name: str,
        error: str = "timeout",
        count: int = 1,
        *,
        retryable: bool | None = None,
        code: str | None = None,
    ) -> None:
        if retryable is None:
            retryable = any(token in error.lower() for token in ("timeout", "unavailable", "connection", "rate limit"))
        failure = QueuedFailure(
            message=error,
            retryable=retryable,
            code=code or ("transient" if retryable else "tool_error"),
        )
        self.failures.setdefault(tool_name, []).extend([failure] * count)

    def queue_prices(self, product_id: str, prices: list[float]) -> None:
        self.price_sequences[product_id] = list(prices)

    def execute(self, tool: ToolDefinition, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.failures.get(tool.name):
            failure = self.failures[tool.name].pop(0)
            raise ToolExecutionError(
                failure.message,
                retryable=failure.retryable,
                code=failure.code,
            )
        validate_arguments(tool.parameters, arguments)
        args = normalize_arguments(tool.parameters, arguments)
        handler = getattr(self, f"_handle_{tool.handler}", None)
        if handler is None:
            raise ToolExecutionError(f"No implementation for handler {tool.handler!r}")
        return handler(args)

    def _current_product(self, product_id: str) -> dict[str, Any]:
        if product_id not in self.catalog:
            raise ToolExecutionError(f"Unknown product {product_id}")
        item = deepcopy(self.catalog[product_id])
        sequence = self.price_sequences.get(product_id)
        if sequence:
            item["price"] = sequence.pop(0) if len(sequence) > 1 else sequence[0]
        inventory = self.inventory.get(product_id, {})
        if inventory:
            item["availability"] = inventory.get("quantity", 0) > 0
        return item

    def _handle_search(self, args: dict[str, Any]) -> dict[str, Any]:
        products = []
        for product_id in sorted(self.catalog):
            item = self._current_product(product_id)
            if args.get("category") and (item.get("category") or "").lower() != str(args["category"]).lower():
                continue
            if args.get("max_price") is not None and item.get("price") is not None and item["price"] > args["max_price"]:
                continue
            if not args.get("include_unavailable", False) and item.get("availability") is False:
                continue
            products.append({key: item.get(key) for key in ("product_id", "name", "category", "price")})
        return {"products": products}

    def _handle_details(self, args: dict[str, Any]) -> dict[str, Any]:
        return {"product": self._current_product(str(args["product_id"]))}

    def _handle_availability(self, args: dict[str, Any]) -> dict[str, Any]:
        product_id = str(args["product_id"])
        inventory = self.inventory.get(product_id)
        if inventory is None:
            return {"product_id": product_id, "available": None, "quantity": None}
        quantity = int(inventory.get("quantity", 0))
        requested = int(args.get("quantity", 1))
        requested_region = str(args.get("region", inventory.get("region", "US")))
        inventory_region = str(inventory.get("region", "US"))
        if requested_region.casefold() != inventory_region.casefold():
            return {
                "product_id": product_id,
                "available": False,
                "quantity": 0,
                "region": requested_region,
                "reason": f"No inventory snapshot is available for region {requested_region}",
            }
        return {
            "product_id": product_id,
            "available": quantity >= requested,
            "quantity": quantity,
            "region": requested_region,
        }

    def _handle_compare(self, args: dict[str, Any]) -> dict[str, Any]:
        products = [self._current_product(str(product_id)) for product_id in args["product_ids"]]
        return {"products": products}

    def _handle_reviews(self, args: dict[str, Any]) -> dict[str, Any]:
        product_id = str(args["product_id"])
        payload = self.reviews.get(product_id, {"average_rating": None, "review_count": 0, "highlights": []})
        return {"review": {"product_id": product_id, **payload}}


class ToolExecutor:
    def __init__(self, registry: ToolRegistry, environment: MockToolEnvironment, max_retries: int = 2) -> None:
        self.registry = registry
        self.environment = environment
        self.max_retries = max_retries

    def call(self, tool_name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], list[ToolCallRecord]]:
        tool = self.registry.get(tool_name)
        records: list[ToolCallRecord] = []
        for attempt in range(1, self.max_retries + 2):
            started = perf_counter()
            try:
                result = self.environment.execute(tool, arguments)
                records.append(
                    ToolCallRecord(
                        tool_name=tool_name,
                        arguments=arguments,
                        status="success",
                        attempt=attempt,
                        duration_ms=round((perf_counter() - started) * 1000, 3),
                    )
                )
                return result, records
            except (SchemaValidationError, ValueError) as exc:
                records.append(
                    ToolCallRecord(
                        tool_name=tool_name,
                        arguments=arguments,
                        status="error",
                        attempt=attempt,
                        error=str(exc),
                        error_code="invalid_arguments",
                        duration_ms=round((perf_counter() - started) * 1000, 3),
                    )
                )
                raise ToolExecutionError(
                    f"{tool_name} rejected non-retryable arguments: {exc}",
                    records=records,
                    retryable=False,
                    code="invalid_arguments",
                ) from exc
            except ToolExecutionError as exc:
                records.append(
                    ToolCallRecord(
                        tool_name=tool_name,
                        arguments=arguments,
                        status="error",
                        attempt=attempt,
                        error=str(exc),
                        error_code=exc.code,
                        duration_ms=round((perf_counter() - started) * 1000, 3),
                    )
                )
                if not exc.retryable or attempt > self.max_retries:
                    raise ToolExecutionError(
                        f"{tool_name} failed after {attempt} attempts: {exc}",
                        records=records,
                        retryable=False,
                        code=exc.code,
                    ) from exc
        raise AssertionError("unreachable")


def parse_product(payload: dict[str, Any]) -> Product:
    return Product.model_validate(payload)


def parse_review(payload: dict[str, Any]) -> ReviewSummary:
    return ReviewSummary.model_validate(payload)
