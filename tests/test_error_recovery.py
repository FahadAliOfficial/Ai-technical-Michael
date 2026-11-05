from conftest import SAMPLE_REQUEST


def test_transient_search_timeout_is_retried(agent, environment) -> None:
    environment.queue_failure("search_products", "timeout", count=1)
    state = agent.run(SAMPLE_REQUEST)
    assert state.recommendation.status == "success"
    search_calls = [record for record in state.tool_calls if record.tool_name == "search_products"]
    assert [record.status for record in search_calls[:2]] == ["error", "success"]


def test_permanent_search_failure_reports_error(agent, environment) -> None:
    environment.queue_failure("search_products", "timeout", count=3)
    state = agent.run(SAMPLE_REQUEST)
    assert state.recommendation.status == "error"
    assert state.recommendation.recommended is None
    assert "failed safely" in state.recommendation.message
    assert len([record for record in state.tool_calls if record.tool_name == "search_products"]) == 3


def test_availability_failure_fails_closed(agent, environment) -> None:
    environment.queue_failure("check_availability", "service unavailable", count=100)
    state = agent.run(SAMPLE_REQUEST)
    assert state.recommendation.status == "no_match"
    assert state.recommendation.recommended is None


def test_price_change_is_detected_before_recommendation(agent, environment) -> None:
    environment.queue_prices("LAPTOP_001", [1099, 1099, 1300])
    state = agent.run(SAMPLE_REQUEST)
    assert state.recommendation.status == "success"
    assert state.recommendation.recommended.product.product_id != "LAPTOP_001"
    assert any("exceeds budget" in reason for reason in state.rejected["LAPTOP_001"])


def test_review_failure_does_not_override_hard_validation(agent, environment) -> None:
    environment.queue_failure("get_reviews", "service unavailable", count=100)
    state = agent.run(SAMPLE_REQUEST)
    assert state.recommendation.status == "success"
    assert state.recommendation.limitations

