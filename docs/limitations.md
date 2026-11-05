# Known limitations and proposed improvements

## Current limitations

1. The deterministic parser covers the assessment's laptop language, common synonyms, and follow-up budgets; arbitrary multilingual or highly implicit requests require OpenAI mode.
2. The local schema validator covers the assessment schemas and common nested constraints, but is not a complete implementation of every JSON Schema draft keyword.
3. Inventory uses one local region and does not model reservations or fulfillment time.
4. Preference weights are documented constants rather than learned from user feedback.
5. The system handles one product category in the supplied catalog, although its models are category-neutral.
6. GPT-4o Mini availability is controlled by OpenAI and the model is therefore configured through `OPENAI_MODEL`.
7. Live API tests are opt-in because they consume tokens and require the evaluator's local `OPENAI_API_KEY`; secrets remain excluded from Git.

## Proposed improvements

- Add multilingual structured-extraction evaluations.
- Implement the full JSON Schema vocabulary or use a dedicated validator.
- Add inventory reservation and regional shipping estimates.
- Calibrate ranking weights from explicit pairwise user feedback.
- Add contract tests against a real HTTP mock server.
- Expand live-model evaluation across repeated runs and report variance and estimated monetary cost.
- Add mutation testing for hard-constraint guardrails.

