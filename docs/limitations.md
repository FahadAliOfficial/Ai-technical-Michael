# Known limitations and proposed improvements

## Current limitations

1. The deterministic parser covers the assessment's laptop language, common synonyms, and follow-up budgets; arbitrary multilingual or highly implicit requests require OpenAI mode.
2. The schema adapter supports the JSON Schema subset used by the mock tools: objects, required fields, primitive values, arrays, enums, and `additionalProperties`.
3. Inventory uses one local region and does not model reservations or fulfillment time.
4. Preference weights are documented constants rather than learned from user feedback.
5. The system handles one product category in the supplied catalog, although its models are category-neutral.
6. GPT-4o Mini availability is controlled by OpenAI and the model is therefore configured through `OPENAI_MODEL`.
7. A live API smoke test requires the evaluator to provide `OPENAI_API_KEY`; the committed suite deliberately uses no secret or paid call.

## Proposed improvements

- Add multilingual structured-extraction evaluations.
- Implement the full JSON Schema vocabulary or use a dedicated validator.
- Add inventory reservation and regional shipping estimates.
- Calibrate ranking weights from explicit pairwise user feedback.
- Add contract tests against a real HTTP mock server.
- Run a small, opt-in live-model evaluation set and report token usage and cost separately.
- Add mutation testing for hard-constraint guardrails.

