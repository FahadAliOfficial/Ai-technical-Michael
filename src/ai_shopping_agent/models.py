from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Requirements(StrictModel):
    category: str | None = Field(
        default=None,
        description="Physical product category requested by the customer, such as laptop; never the intended purpose.",
    )
    max_price: float | None = Field(default=None, gt=0, description="Mandatory maximum purchase price in USD.")
    min_ram_gb: int | None = Field(default=None, gt=0, description="Mandatory minimum RAM capacity in GB.")
    min_storage_gb: int | None = Field(
        default=None,
        gt=0,
        description="Mandatory minimum storage capacity normalized to GB, where 1TB equals 1024GB.",
    )
    storage_type: str | None = Field(default=None, description="Mandatory storage technology, such as SSD or HDD.")
    preferred_battery_hours: float | None = Field(
        default=None,
        gt=0,
        description="Soft preference for minimum battery life in hours.",
    )
    preferred_max_weight_kg: float | None = Field(
        default=None,
        gt=0,
        description="Soft preference for maximum product weight in kilograms.",
    )
    purpose: str | None = Field(
        default=None,
        description="Customer use case or context, such as software development; never the product category.",
    )
    conflicts: list[str] = Field(
        default_factory=list,
        description="Concrete contradictions in the customer's mandatory requirements; empty when none exist.",
    )
    clarification_question: str | None = Field(
        default=None,
        description="One targeted question that resolves identified conflicts; null when no conflict exists.",
    )

    def missing_mandatory(self) -> list[str]:
        fields = {
            "category": self.category,
            "maximum budget": self.max_price,
            "minimum RAM": self.min_ram_gb,
            "minimum storage": self.min_storage_gb,
            "storage type": self.storage_type,
        }
        return [label for label, value in fields.items() if value is None]

    def question_for_missing(self) -> str | None:
        missing = self.missing_mandatory()
        if not missing:
            return None
        if len(missing) == 1:
            return f"What is your {missing[0]}?"
        return f"Please provide your {', '.join(missing[:-1])}, and {missing[-1]}."


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
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    tradeoffs: list[str] = Field(default_factory=list)


class ToolCallRecord(StrictModel):
    tool_name: str
    arguments: dict[str, Any]
    status: Literal["success", "error"]
    attempt: int = 1
    request_version: int = 1
    error: str | None = None
    error_code: str | None = None
    duration_ms: float = Field(default=0, ge=0)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Recommendation(StrictModel):
    status: Literal["success", "no_match", "clarification", "error"]
    message: str
    recommended: RankedProduct | None = None
    alternatives: list[RankedProduct] = Field(default_factory=list)
    constraint_checks: list[str] = Field(default_factory=list)
    comparison_summary: str | None = None
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
    current_phase: Literal[
        "parsing",
        "clarification",
        "searching",
        "inspecting",
        "validating",
        "ranking",
        "verifying",
        "responding",
        "completed",
        "failed",
    ] = "parsing"
    completed_steps: list[str] = Field(default_factory=list)
    model_metrics: dict[str, int] = Field(default_factory=dict)

    def enter_phase(self, phase: str) -> None:
        if self.current_phase not in {"completed", "failed"} and self.current_phase not in self.completed_steps:
            self.completed_steps.append(self.current_phase)
        self.current_phase = phase  # type: ignore[assignment]

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
        self.current_phase = "parsing"
        self.completed_steps.clear()
        self.model_metrics.clear()
