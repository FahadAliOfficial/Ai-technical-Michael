from ai_shopping_agent.agent import ShoppingAgent
from ai_shopping_agent.audit import AuditLogger
from ai_shopping_agent.model_client import SchemaAwareModelClient, ToolLoopResult
from conftest import SAMPLE_REQUEST


def test_normal_request_returns_valid_recommendation(agent) -> None:
    state = agent.run(SAMPLE_REQUEST)
    assert state.recommendation.status == "success"
    product = state.recommendation.recommended.product
    assert product.price <= 1200
    assert product.ram_gb >= 32
    assert product.storage_gb >= 1024
    assert product.storage_type == "SSD"
    assert product.availability is True


def test_invalid_high_rated_products_are_rejected(agent) -> None:
    state = agent.run(SAMPLE_REQUEST)
    assert "LAPTOP_011" in state.rejected
    assert "LAPTOP_018" in state.rejected
    assert state.recommendation.recommended.product.product_id not in {"LAPTOP_011", "LAPTOP_018"}


def test_out_of_stock_products_are_not_recommended(agent) -> None:
    state = agent.run(SAMPLE_REQUEST)
    assert "LAPTOP_008" in state.rejected
    assert "LAPTOP_030" in state.rejected


def test_no_match_never_invents_product(agent) -> None:
    state = agent.run("I need a laptop under $1,200 with at least 128GB RAM and 8TB SSD storage")
    assert state.recommendation.status == "no_match"
    assert state.recommendation.recommended is None


def test_all_required_tools_are_invoked(agent) -> None:
    state = agent.run(SAMPLE_REQUEST)
    called = {record.tool_name for record in state.tool_calls}
    assert {"search_products", "get_product_details", "check_availability", "get_reviews", "compare_products"} <= called


def test_audit_log_records_decisions(agent) -> None:
    state = agent.run(SAMPLE_REQUEST)
    events = {event["event"] for event in agent.logger.events}
    assert {"requirements_parsed", "search_completed", "product_rejected", "tool_call", "recommendation_created"} <= events
    assert all(event["run_id"] == state.run_id for event in agent.logger.events)


def test_missing_mandatory_requirement_asks_targeted_clarification(agent) -> None:
    state = agent.run("I need a laptop with at least 32GB RAM and 1TB SSD storage")
    assert state.recommendation.status == "clarification"
    assert "budget" in (state.recommendation.clarification_question or "")
    assert not state.tool_calls


def test_final_verification_continues_past_invalidated_top_five(agent, environment) -> None:
    changed = {
        "LAPTOP_001": 1099,
        "LAPTOP_002": 1149,
        "LAPTOP_026": 1125,
        "LAPTOP_015": 1025,
        "LAPTOP_017": 925,
    }
    for product_id, price in changed.items():
        environment.queue_prices(product_id, [price, price, 1300])
    state = agent.run(SAMPLE_REQUEST)
    assert state.recommendation.status == "success"
    assert state.recommendation.recommended.product.product_id not in changed
    assert state.pending_checks == []


def test_response_exposes_constraints_scores_and_comparison(agent) -> None:
    state = agent.run(SAMPLE_REQUEST)
    result = state.recommendation
    assert len(result.constraint_checks) == 4
    assert result.recommended.score_breakdown
    assert result.comparison_summary
    assert "Alternatives:" in result.message


def test_model_parsing_fallback_is_disclosed_on_initial_and_follow_up_runs(
    settings,
    registry,
    environment,
) -> None:
    class FailingParserModel(SchemaAwareModelClient):
        def parse_requirements(self, request, previous=None):
            raise RuntimeError("structured extraction unavailable")

    logger = AuditLogger()
    fallback_agent = ShoppingAgent(
        settings,
        registry=registry,
        environment=environment,
        model_client=FailingParserModel(),
        logger=logger,
    )
    state = fallback_agent.run(SAMPLE_REQUEST)
    assert any("deterministic fallback used" in error for error in state.errors)
    updated = fallback_agent.run("My maximum budget is $900 now", state)
    assert any("deterministic fallback used" in error for error in updated.errors)
    assert len([event for event in logger.events if event["event"] == "model_parsing_fallback"]) == 2


def test_user_facing_comparison_is_rendered_from_tool_evidence(
    settings,
    registry,
    environment,
) -> None:
    class UntrustedNarrativeModel(SchemaAwareModelClient):
        def run_tool_loop(self, prompt, tools, execute, *, max_steps=8):
            arguments = {"product_ids": ["LAPTOP_001", "LAPTOP_002"]}
            result = execute(tools[0]["name"], arguments)
            return ToolLoopResult(
                final_text="INVENTED PRODUCT with unsupported specifications",
                steps=2,
                calls=[{"name": tools[0]["name"], "arguments": arguments, "call_id": "test", "result": result}],
            )

    grounded_agent = ShoppingAgent(
        settings,
        registry=registry,
        environment=environment,
        model_client=UntrustedNarrativeModel(),
        logger=AuditLogger(),
    )
    state = grounded_agent.run(SAMPLE_REQUEST)
    assert state.recommendation.status == "success"
    assert state.recommendation.comparison_summary.startswith("Verified comparison:")
    assert "INVENTED PRODUCT" not in state.recommendation.comparison_summary
    compare_calls = [call for call in state.tool_calls if call.tool_name == "compare_products"]
    assert len(compare_calls) == 1

