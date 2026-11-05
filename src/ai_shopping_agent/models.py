from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Requirements(StrictModel):
    category: str | None = None
    max_price: float | None = Field(default=None, gt=0)
    min_ram_gb: int | None = Field(default=None, gt=0)
    min_storage_gb: int | None = Field(default=None, gt=0)
    storage_type: str | None = None
    preferred_battery_hours: float | None = Field(default=None, gt=0)
    preferred_max_weight_kg: float | None = Field(default=None, gt=0)
    purpose: str | None = None
    conflicts: list[str] = Field(default_factory=list)
    clarification_question: str | None = None


class Product(StrictModel):
    product_id: str
    name: str
    category: str | None = None
    price: float | None = None
    ram_gb: int | None = None
    storage_gb: int | None = None
    storage_type: str | None = None
    battery_hours: float | None = None
    weight_kg: float | None = None
    rating: float | None = None
    availability: bool | None = None
    description: str = ""


class ReviewSummary(StrictModel):
    product_id: str
    average_rating: float | None = None
    review_count: int = 0
    highlights: list[str] = Field(default_factory=list)


class ValidationResult(StrictModel):
    product_id: str
    valid: bool
    reasons: list[str] = Field(default_factory=list)


class RankedProduct(StrictModel):
    product: Product
    score: float
    tradeoffs: list[str] = Field(default_factory=list)


class ToolCallRecord(StrictModel):
    tool_name: str
    arguments: dict[str, Any]
    status: Literal["success", "error"]
    attempt: int = 1
    error: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Recommendation(StrictModel):
    status: Literal["success", "no_match", "clarification", "error"]
    message: str
    recommended: RankedProduct | None = None
    alternatives: list[RankedProduct] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    clarification_question: str | None = None


class AgentState(StrictModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    request_version: int = 1
    raw_request: str
    requirements: Requirements | None = None
    discovered_tools: list[str] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list)
    products: dict[str, Product] = Field(default_factory=dict)
    rejected: dict[str, list[str]] = Field(default_factory=dict)
    pending_checks: list[str] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    recommendation: Recommendation | None = None

    def apply_request_update(self, raw_request: str, requirements: Requirements) -> None:
        self.request_version += 1
        self.raw_request = raw_request
        self.requirements = requirements
        self.candidate_ids.clear()
        self.products.clear()
        self.rejected.clear()
        self.pending_checks.clear()
        self.errors.clear()
        self.recommendation = None
