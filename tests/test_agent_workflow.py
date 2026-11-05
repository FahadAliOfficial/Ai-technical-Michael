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

