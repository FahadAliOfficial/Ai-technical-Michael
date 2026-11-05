from __future__ import annotations

from typing import Any

from .audit import AuditLogger
from .config import Settings
from .model_client import OpenAIModelClient, SchemaAwareModelClient
from .models import AgentState, Product, Recommendation, Requirements, ReviewSummary
from .ranking import rank_products
from .response import success_response
from .state import StateManager
from .tools.adapter import ArgumentAdapter
from .tools.mock_tools import MockToolEnvironment, ToolExecutionError, ToolExecutor, parse_product, parse_review
from .tools.registry import ToolRegistry
from .validation import validate_product


class ShoppingAgent:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        registry: ToolRegistry | None = None,
        environment: MockToolEnvironment | None = None,
        model_client: Any | None = None,
        logger: AuditLogger | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.registry = registry or ToolRegistry.from_file(self.settings.tool_manifest_path)
        self.environment = environment or MockToolEnvironment(
            self.settings.catalog_path,
            self.settings.inventory_path,
            self.settings.reviews_path,
        )
        self.executor = ToolExecutor(self.registry, self.environment, self.settings.max_retries)
        if model_client is not None:
            self.model = model_client
        elif self.settings.api_key:
            self.model = OpenAIModelClient(
                self.settings.api_key,
                self.settings.model,
                self.settings.timeout_seconds,
                self.settings.max_retries,
            )
        else:
            self.model = SchemaAwareModelClient()
        self.logger = logger or AuditLogger(self.settings.log_path)
        self.states = StateManager()
        self.adapter = ArgumentAdapter()

    @property
    def mode(self) -> str:
        return "openai" if isinstance(self.model, OpenAIModelClient) else "offline-schema-aware"

    def run(self, request: str, state: AgentState | None = None) -> AgentState:
        previous = state.requirements if state else None
        parsing_warning: str | None = None
        try:
            requirements = self.model.parse_requirements(request, previous)
        except Exception as exc:
            requirements = SchemaAwareModelClient().parse_requirements(request, previous)
            parsing_warning = f"Model parsing failed; deterministic fallback used: {exc}"

        if state is None:
            state = self.states.new(request, requirements)
        else:
            self.states.update(state, request, requirements)
        if parsing_warning:
            state.errors.append(parsing_warning)
            self.logger.log("model_parsing_fallback", state.run_id, error=str(parsing_warning))
        state.discovered_tools = [tool.name for tool in self.registry.list()]
        self.logger.log("requirements_parsed", state.run_id, requirements=requirements.model_dump())

        if requirements.conflicts:
            state.enter_phase("clarification")
            state.recommendation = Recommendation(
                status="clarification",
                message="I need one clarification before searching.",
                clarification_question=requirements.clarification_question,
            )
            self.logger.log(
                "clarification_required",
                state.run_id,
                conflicts=requirements.conflicts,
                question=requirements.clarification_question,
            )
            return state

        missing = requirements.missing_mandatory()
        if missing:
            state.enter_phase("clarification")
            question = requirements.question_for_missing()
            state.recommendation = Recommendation(
                status="clarification",
                message="I need the missing mandatory requirements before searching.",
                clarification_question=question,
            )
            self.logger.log(
                "clarification_required",
                state.run_id,
                missing_requirements=missing,
                question=question,
            )
            return state

        state.enter_phase("searching")
        search_context = self._context(state, include_unavailable=True)
        search = self._safe_select("search the product catalog", search_context, state)
        if search is None:
            return self._error(state, "No compatible product-search tool is available.")
        try:
            payload = self._call(state, *search)
        except ToolExecutionError as exc:
            return self._error(state, f"Product search failed safely: {exc}")

        state.candidate_ids = [item["product_id"] for item in payload.get("products", [])]
        self.logger.log("search_completed", state.run_id, candidate_count=len(state.candidate_ids))
        if not state.candidate_ids:
            return self._no_match(state, "No products were returned by the available search tool.")

        state.enter_phase("inspecting")
        details_tool = self._safe_select(
            "retrieve complete product details",
            self._context(state, product_id=state.candidate_ids[0]),
            state,
        )
        if details_tool is None:
            return self._error(state, "No compatible product-details tool is available.")

        for product_id in state.candidate_ids:
            try:
                arguments = self.adapter.bind(
                    self.registry.get(details_tool[0]).parameters,
                    self._context(state, product_id=product_id),
                )
                product = parse_product(self._call(state, details_tool[0], arguments)["product"])
                state.products[product_id] = product
            except (ToolExecutionError, ValueError, KeyError) as exc:
                state.rejected[product_id] = [f"Product details could not be verified: {exc}"]
                self.logger.log("product_rejected", state.run_id, product_id=product_id, reasons=state.rejected[product_id])

        state.enter_phase("validating")
        preliminary: list[Product] = []
        for product in state.products.values():
            result = validate_product(product, requirements)
            spec_reasons = [reason for reason in result.reasons if "availability" not in reason and "unavailable" not in reason]
            if spec_reasons:
                state.rejected[product.product_id] = spec_reasons
                self.logger.log("product_rejected", state.run_id, product_id=product.product_id, reasons=spec_reasons)
            else:
                preliminary.append(product)
        if not preliminary:
            return self._no_match(state, "No product satisfies every mandatory specification.")

        availability_tool = self._safe_select(
            "verify current product inventory availability",
            self._context(state, product_id=preliminary[0].product_id),
            state,
        )
        if availability_tool is None:
            return self._error(state, "Availability cannot be verified safely.")

        available: list[Product] = []
        state.pending_checks = [f"availability:{product.product_id}" for product in preliminary]
        for product in preliminary:
            try:
                arguments = self.adapter.bind(
                    self.registry.get(availability_tool[0]).parameters,
                    self._context(state, product_id=product.product_id),
                )
                result = self._call(state, availability_tool[0], arguments)
                product.availability = result.get("available")
            except (ToolExecutionError, ValueError) as exc:
                product.availability = None
                state.errors.append(f"Availability check failed for {product.product_id}: {exc}")
            validation = validate_product(product, requirements)
            check_name = f"availability:{product.product_id}"
            if check_name in state.pending_checks:
                state.pending_checks.remove(check_name)
            if validation.valid:
                available.append(product)
            else:
                state.rejected[product.product_id] = validation.reasons
                self.logger.log("product_rejected", state.run_id, product_id=product.product_id, reasons=validation.reasons)
        if not available:
            return self._no_match(state, "No fully verified in-stock product satisfies every mandatory constraint.")

        state.enter_phase("ranking")
        reviews = self._collect_reviews(state, available)
        initially_ranked = rank_products(available, requirements, reviews)

        state.enter_phase("verifying")
        final_products = self._final_verification(state, [item.product for item in initially_ranked], requirements)
        if not final_products:
            return self._no_match(state, "Candidates became invalid during final price or availability verification.")

        final_ranked = rank_products(final_products, requirements, reviews)
        compare_ids = [item.product.product_id for item in final_ranked[:3]]
        comparison_summary = self._model_comparison(state, final_ranked, requirements)
        if len(compare_ids) > 1 and comparison_summary is None:
            comparison = self._safe_select(
                "compare selected products",
                self._context(state, product_ids=compare_ids),
                state,
            )
            if comparison:
                try:
                    comparison_payload = self._call(state, *comparison)
                    comparison_summary = self._grounded_comparison_summary(
                        final_ranked,
                        comparison_payload,
                    )
                except ToolExecutionError as exc:
                    state.errors.append(f"Comparison tool failed; deterministic ranking retained: {exc}")

        state.enter_phase("responding")
        limitations = list(state.errors)
        state.recommendation = success_response(final_ranked, requirements, limitations, comparison_summary)
        self.logger.log(
            "recommendation_created",
            state.run_id,
            product_id=state.recommendation.recommended.product.product_id,
            score=state.recommendation.recommended.score,
        )
        state.enter_phase("completed")
        return state

    def _model_comparison(
        self,
        state: AgentState,
        ranked: list[Any],
        requirements: Requirements,
    ) -> str | None:
        run_tool_loop = getattr(self.model, "run_tool_loop", None)
        if run_tool_loop is None:
            return None
        try:
            comparison_tool = self.registry.find("compare selected products")
        except LookupError:
            return None
        comparison_tools = [comparison_tool.as_openai_tool()]
        candidate_ids = [item.product.product_id for item in ranked[:3]]
        prompt = (
            "Compare these already validated candidates and explain why the first-ranked option is recommended, "
            "including meaningful trade-offs for the alternatives. You must call the comparison tool before answering.\n"
            f"Mandatory requirements: {requirements.model_dump_json()}\n"
            f"Verified candidate IDs in deterministic rank order: {candidate_ids}"
        )
        try:
            result = run_tool_loop(
                prompt,
                comparison_tools,
                lambda name, arguments: self._call(state, name, arguments),
                max_steps=6,
            )
        except Exception as exc:
            state.errors.append(f"Model comparison failed; deterministic explanation retained: {exc}")
            return None
        if not result.calls:
            state.errors.append("Model comparison returned without using a verification tool.")
            return None
        state.model_metrics = dict(getattr(self.model, "usage_totals", result.usage))
        self.logger.log(
            "model_tool_loop_completed",
            state.run_id,
            steps=result.steps,
            calls=len(result.calls),
            usage=result.usage,
            request_ids=getattr(self.model, "request_ids", result.request_ids),
        )
        comparison_payload = result.calls[-1].get("result", {})
        return self._grounded_comparison_summary(ranked, comparison_payload)

    @staticmethod
    def _grounded_comparison_summary(ranked: list[Any], payload: dict[str, Any]) -> str:
        """Render comparison evidence only from validated rank data and tool output."""
        tool_products = {
            item.get("product_id"): item
            for item in payload.get("products", [])
            if isinstance(item, dict) and item.get("product_id")
        }
        lines: list[str] = []
        for index, item in enumerate(ranked[:3], start=1):
            product = item.product
            current = tool_products.get(product.product_id, {})
            name = current.get("name", product.name)
            price = current.get("price", product.price)
            battery = current.get("battery_hours", product.battery_hours)
            weight = current.get("weight_kg", product.weight_kg)
            details = [f"#{index} {name}", f"${price:,.2f}", f"score {item.score:.2f}/100"]
            if battery is not None:
                details.append(f"battery {battery:g}h")
            if weight is not None:
                details.append(f"weight {weight:g}kg")
            if item.tradeoffs:
                details.append("trade-offs: " + "; ".join(item.tradeoffs))
            lines.append(", ".join(details))
        return "Verified comparison: " + " | ".join(lines)

    def _collect_reviews(self, state: AgentState, products: list[Product]) -> dict[str, ReviewSummary]:
        selected = self._safe_select(
            "retrieve product customer reviews",
            self._context(state, product_id=products[0].product_id),
            state,
        )
        if selected is None:
            state.errors.append("No reviews tool was available; catalog ratings were used.")
            return {}
        reviews: dict[str, ReviewSummary] = {}
        for product in products:
            try:
                arguments = self.adapter.bind(
                    self.registry.get(selected[0]).parameters,
                    self._context(state, product_id=product.product_id),
                )
                review = parse_review(self._call(state, selected[0], arguments)["review"])
                reviews[product.product_id] = review
            except (ToolExecutionError, ValueError) as exc:
                state.errors.append(f"Reviews unavailable for {product.product_id}: {exc}")
        return reviews

    def _final_verification(
        self,
        state: AgentState,
        products: list[Product],
        requirements: Requirements,
    ) -> list[Product]:
        details = self.registry.find("retrieve complete product details")
        availability = self.registry.find("verify product inventory availability")
        verified: list[Product] = []
        state.pending_checks = [f"final_verification:{product.product_id}" for product in products]
        for prior in products:
            try:
                detail_args = self.adapter.bind(details.parameters, self._context(state, product_id=prior.product_id))
                current = parse_product(self._call(state, details.name, detail_args)["product"])
                availability_args = self.adapter.bind(
                    availability.parameters,
                    self._context(state, product_id=prior.product_id),
                )
                current.availability = self._call(state, availability.name, availability_args).get("available")
                result = validate_product(current, requirements)
                if result.valid:
                    state.products[current.product_id] = current
                    verified.append(current)
                else:
                    state.rejected[current.product_id] = result.reasons
                    self.logger.log(
                        "final_verification_rejected",
                        state.run_id,
                        product_id=current.product_id,
                        reasons=result.reasons,
                    )
            except (ToolExecutionError, ValueError, LookupError) as exc:
                state.rejected[prior.product_id] = [f"Final verification failed: {exc}"]
            finally:
                check_name = f"final_verification:{prior.product_id}"
                if check_name in state.pending_checks:
                    state.pending_checks.remove(check_name)
            if len(verified) >= 3:
                break
        state.pending_checks.clear()
        return verified

    def _safe_select(
        self,
        goal: str,
        context: dict[str, Any],
        state: AgentState,
    ) -> tuple[str, dict[str, Any]] | None:
        tools = self.registry.openai_tools()
        try:
            return self.model.select_tool(goal, tools, context)
        except Exception as exc:
            state.errors.append(f"Model tool selection failed for {goal!r}; schema fallback used: {exc}")
            try:
                tool = self.registry.find(goal)
                return tool.name, self.adapter.bind(tool.parameters, context)
            except (LookupError, ValueError, KeyError):
                return None

    def _call(self, state: AgentState, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            result, records = self.executor.call(tool_name, arguments)
        except ToolExecutionError as exc:
            for record in exc.records:
                record.request_version = state.request_version
            state.tool_calls.extend(exc.records)
            for record in exc.records:
                self.logger.log("tool_call", state.run_id, **record.model_dump())
            state.errors.append(str(exc))
            self.logger.log("tool_failed", state.run_id, tool_name=tool_name, error=str(exc))
            raise
        state.tool_calls.extend(records)
        for record in records:
            record.request_version = state.request_version
            self.logger.log("tool_call", state.run_id, **record.model_dump())
        return result

    @staticmethod
    def _context(state: AgentState, **overrides: Any) -> dict[str, Any]:
        requirements = state.requirements or Requirements()
        context = {
            "query": state.raw_request,
            "category": requirements.category,
            "max_price": requirements.max_price,
            "product_id": None,
            "product_ids": None,
            "region": "US",
            "quantity": 1,
            "include_unavailable": True,
        }
        context.update(overrides)
        return context

    def _no_match(self, state: AgentState, message: str) -> AgentState:
        state.enter_phase("completed")
        state.recommendation = Recommendation(status="no_match", message=message, limitations=list(state.errors))
        self.logger.log("no_match", state.run_id, message=message)
        return state

    def _error(self, state: AgentState, message: str) -> AgentState:
        state.enter_phase("failed")
        state.errors.append(message)
        state.recommendation = Recommendation(status="error", message=message, limitations=list(state.errors))
        self.logger.log("agent_error", state.run_id, message=message)
        return state

