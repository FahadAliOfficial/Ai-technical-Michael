# Live technical defense runbook

The goal is to understand the change path, not memorize code.

## 1. Change the search schema

1. Edit or replace the search entry in `data/tool_manifest.json`.
2. Keep parameter descriptions semantically clear.
3. Run `python -m pytest tests/test_dynamic_tools.py`.
4. Explain that orchestration never references the original search parameter names.

The automated example renames both the tool and every parameter in `test_adapts_to_renamed_search_tool_and_parameters`.

## 2. Add an invalid product

1. Add a catalog entry that meets every requirement except RAM.
2. Add inventory for it.
3. Run `python -m pytest tests/test_validation.py tests/test_agent_workflow.py`.
4. Inspect `state.rejected[product_id]` for the deterministic reason.

The critical code is `validate_product`; ratings and descriptions never participate in hard validation.

## 3. Simulate availability failure

1. Call `environment.queue_failure("check_availability", "service unavailable", count=100)`.
2. Run the request.
3. Confirm the result is `no_match`, not a recommendation.
4. Inspect the failed attempts in `state.tool_calls` and the audit log.

## 4. Change the budget during conversation

```python
state = agent.run(original_request)
state = agent.run("My maximum budget is $900 now", state)
```

Confirm `request_version == 2`, the run ID is stable, stale decision state was invalidated, and any recommendation is at most $900.

## 5. Diagnose a failed evaluation

1. Run the smallest failing test with `-vv`.
2. Identify whether the defect belongs to interpretation, schema binding, tool execution, validation, ranking, or response generation.
3. Fix the responsible layer without weakening a hard constraint.
4. Run the focused test, then `python -m pytest`, then the five-gate evaluation runner.

## Useful commands

```powershell
python -m pytest -vv
python -m pytest tests/test_dynamic_tools.py -vv
python -m pytest tests/test_error_recovery.py -vv
$env:PYTHONPATH = "src"
python -m ai_shopping_agent.evaluation.runner
```

