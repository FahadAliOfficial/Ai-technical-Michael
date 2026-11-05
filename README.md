# AI Shopping Agent

A reliable single-agent shopping system that separates language understanding from deterministic product validation. It discovers mock tools from runtime JSON schemas, records decisions, survives controlled failures, and rechecks volatile price and inventory data immediately before recommending.

## Assessment coverage

- Natural-language requirements are split into mandatory constraints, preferences, and context.
- The OpenAI Responses API provides structured extraction and function calling when an API key is configured.
- A schema-aware offline model substitute keeps the evaluator workflow and tests free of API cost.
- Tool names and parameters are loaded from `data/tool_manifest.json`; the agent never reads the catalog directly.
- Hard constraints are enforced by Python, never by model judgment.
- Typed state tracks request versions, candidates, rejection reasons, pending checks, errors, tool calls, and results.
- Price and availability are queried again before the final decision.
- Fifty documented scenarios, 81 offline tests, and three opt-in live OpenAI tests cover happy paths, adversarial data, nested schema changes, failures, state updates, and the real API boundary.

## Requirements

- Python 3.11 or newer
- An OpenAI API key only for live model mode; offline mode needs no key

## Installation

PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
```

Do not commit `.env`. To enable OpenAI mode, set the key locally:

```env
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=gpt-4o-mini
```

`OPENAI_MODEL` is configurable because model availability changes over time. Without `OPENAI_API_KEY`, the CLI clearly reports `offline-schema-aware` mode.

## Run

```powershell
shopping-agent
shopping-agent "I need a development laptop under $1,000 with 32GB RAM and 1TB SSD"
shopping-agent --json
```

Without installing the package first:

```powershell
$env:PYTHONPATH = "src"
python -m ai_shopping_agent
```

The default request is the assessment's laptop scenario. Runtime logs are written to `logs/agent.jsonl` unless `SHOPPING_AGENT_LOG_PATH` is changed.

## Test and evaluate

```powershell
python -m pytest
shopping-agent-eval
shopping-agent-eval --live
```

Or without package installation:

```powershell
$env:PYTHONPATH = "src"
python -m ai_shopping_agent.evaluation.runner
```

The evaluation command writes `evidence/evaluation-results.json` and exits unsuccessfully unless all tests, at least 85% branch-aware coverage, and all five behavior-specific quality gates pass. `--live` also runs paid OpenAI integration tests using the key from `.env`.

## How the agent works

1. Parse the customer request into `Requirements`.
2. Ask the configured model to select a tool from the current runtime definitions.
3. Validate tool arguments locally against the supplied JSON Schema.
4. Execute only through `ToolExecutor` and record each attempt.
5. Retrieve complete product details and reject missing or invalid mandatory data.
6. Verify inventory, retrieve reviews, and rank only valid products.
7. Re-fetch current details and inventory in rank order until three current valid candidates survive.
8. Run a bounded Responses function-call continuation loop: execute comparison calls, return each result with its `call_id`, and obtain a grounded explanation.
9. Return the best valid product, mandatory checks, score breakdown, alternatives, trade-offs, and limitations.

If model parsing or tool selection fails, the deterministic schema-aware fallback attempts safe recovery. Hard validation never falls back to an LLM.

## Repository map

```text
src/ai_shopping_agent/       agent, models, parsing, validation, ranking
src/ai_shopping_agent/tools/ runtime schemas, adapters, executor, mock tools
src/ai_shopping_agent/evaluation/ five-gate evaluation runner
data/                        35-product catalog, inventory, reviews, tools
tests/                       automated tests and 50 expected scenarios
docs/                        architecture, decisions, limitations, defense guide
evidence/                    committed sample log and evaluation result
```

## Documentation

- `docs/architecture.md` - components and execution flow
- `docs/decisions.md` - major architectural decisions and trade-offs
- `docs/evaluation-report.md` - test results and failure analysis
- `docs/limitations.md` - known limitations and proposed improvements
- `docs/live-defense-runbook.md` - rehearsed assessment modifications

## Security and privacy

- Secrets are loaded from the environment and excluded by `.gitignore`.
- Tool and decision logs contain no API keys.
- API responses are created with `store=False`; tool-loop output items are replayed locally with matching `call_id` values.
- The mock environment is local and performs no external product calls.

