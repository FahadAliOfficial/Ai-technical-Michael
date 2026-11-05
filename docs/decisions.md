# Architectural decisions

## ADR-001: Official OpenAI SDK and Responses API

**Decision:** Use the official `openai` Python package directly.

**Reason:** Runtime function schemas are central to the assessment. Direct Responses API calls expose exactly what the model receives and returns, making schema changes easy to test and defend.

**Trade-off:** The project implements a concise agent loop rather than relying on a framework runner. That additional code is intentional evidence for orchestration, state management, recovery, and logging criteria.

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

**Decision:** Re-fetch full details and inventory for the five strongest candidates before recommending.

**Reason:** Search results and early snapshots may become stale. Final validation uses current price and availability.

