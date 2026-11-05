# Architectural decisions

## ADR-001: Official OpenAI SDK and Responses API

**Decision:** Use the official `openai` Python package directly.

**Reason:** Runtime function schemas are central to the assessment. Direct Responses API calls expose exactly what the model receives and returns, making schema changes easy to test and defend.

**Trade-off:** The project implements a concise agent loop rather than relying on a framework runner. That additional code is intentional evidence for orchestration, state management, recovery, and logging criteria.

The final comparison uses a real stateless Responses continuation loop. Tool outputs are returned with their `call_id`; the loop has a maximum-step guard and cannot change the deterministic valid-candidate set.

The model's final narrative is retained only as execution evidence. Customer-facing comparison text is rendered from the validated ranking and comparison tool payload, preventing unsupported model claims.

## ADR-002: Single agent

**Decision:** Use one shopping agent with normal Python components.

**Reason:** Parsing, searching, validation, ranking, and response generation share one bounded state. Multiple agents would add cost and synchronization failure modes without an evaluation benefit.

## ADR-003: Deterministic hard validation

**Decision:** Mandatory constraints are evaluated only by `validation.py`.

**Reason:** Language models are useful for interpretation but are not a safe authority for numeric or availability constraints. Missing mandatory data fails closed.

## ADR-004: Runtime schemas, not fixed tool signatures

**Decision:** Load tools from a manifest and bind arguments using names plus descriptions.

**Reason:** The live assessment changes tool schemas. The agent must inspect what exists now instead of assuming known names and parameters.

## ADR-005: Offline evaluation mode

**Decision:** Provide `SchemaAwareModelClient` for tests and no-key demonstrations.

**Reason:** Repeatable evaluation must not depend on network access, model variance, rate limits, or API cost. Live OpenAI mode uses the same public model-client contract.

## ADR-006: Recheck volatile data

**Decision:** Re-fetch full details and inventory in rank order until three valid candidates survive or the candidate set is exhausted.

**Reason:** Search results and early snapshots may become stale. Final validation uses current price and availability without incorrectly returning no match when only the first-ranked candidates changed.

## ADR-007: Requirement completeness before tools

**Decision:** Do not call search until category, maximum budget, minimum RAM, minimum storage, and storage type are known.

**Reason:** An absent mandatory value is a customer clarification need, not a tool-compatibility failure.

## ADR-008: Measured quality gates

**Decision:** Require targeted behavioral tests for every quality gate and at least 85% branch-aware coverage for the full offline suite.

**Reason:** File presence and a generic green test run do not prove that each assessment capability works.

## ADR-009: Per-run model circuit breaker

**Decision:** After an OpenAI connection or selection failure, use deterministic parsing and schema-aware selection for the remainder of that run.

**Reason:** Repeating the same unavailable external call adds latency and duplicate limitations without improving the result. A later customer request starts a new run attempt and may use OpenAI again.

