from conftest import SAMPLE_REQUEST


def test_budget_change_updates_version_and_reruns(agent) -> None:
    state = agent.run(SAMPLE_REQUEST)
    original_run_id = state.run_id
    updated = agent.run("My maximum budget is $900 now", state)
    assert updated.run_id == original_run_id
    assert updated.request_version == 2
    assert updated.requirements.max_price == 900
    if updated.recommendation.recommended:
        assert updated.recommendation.recommended.product.price <= 900


def test_update_clears_stale_decision_state(agent) -> None:
    state = agent.run(SAMPLE_REQUEST)
    previous_recommendation = state.recommendation.recommended.product.product_id
    updated = agent.run("My maximum budget is $800 now", state)
    assert updated.requirements.max_price == 800
    assert updated.recommendation.status in {"success", "no_match"}
    if updated.recommendation.recommended:
        assert updated.recommendation.recommended.product.product_id != previous_recommendation


def test_tool_calls_are_attributed_to_request_versions(agent) -> None:
    state = agent.run(SAMPLE_REQUEST)
    first_count = len(state.tool_calls)
    assert all(record.request_version == 1 for record in state.tool_calls)
    updated = agent.run("My maximum budget is $900 now", state)
    assert all(record.request_version == 1 for record in updated.tool_calls[:first_count])
    assert all(record.request_version == 2 for record in updated.tool_calls[first_count:])

