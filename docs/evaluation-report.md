# Evaluation report

## Method

The project uses a cycle-based acceptance process:

1. implement a bounded capability;
2. run focused tests;
3. run the full suite;
4. score five quality gates;
5. improve any failed gate without removing completed behavior;
6. repeat until all gates pass.

The five gates are requirements/state, dynamic tools, validation/ranking, resilience/auditability, and tests/documentation. Each gate runs its own targeted behavioral test set; file presence alone cannot pass a gate. The tests/documentation gate also requires at least 85% branch-aware coverage. The optional `--live` evaluation additionally exercises structured parsing, unfamiliar runtime tools, function-call outputs, follow-up state preservation, and the complete OpenAI-backed workflow.

## Final result

The authoritative machine-readable result is `evidence/evaluation-results.json`. It records test totals, success rate, gate status, catalog size, scenario count, and any captured failure analysis.

- Offline automated tests: 83 passed, 0 failed, 0 errors
- Branch-aware coverage: 88% (85% minimum)
- Live OpenAI integration tests: 3 passed, 0 failed, 0 errors
- Automated success rate: 100%
- Quality gates: 5/5
- Documented scenarios: 52
- Catalog products: 35
- Dependency check: no broken requirements

This score is the project's repeatable internal acceptance rubric, not a guarantee of the employer's independent score. A paid live-model smoke test remains opt-in because no API key is stored in the repository.

## Failures found during implementation

| Cycle | Failure | Root cause | Improvement |
|---|---|---|---|
| 1 | Weight interpreted as budget | The word "under" was accepted without currency context | Require currency for generic under/below budget phrases |
| 1 | Reversed battery phrase missed | Parser only supported "battery ... 10 hours" | Add support for "10 hours of battery" |
| 1 | Test collection stopped | Pytest 9 reserves the parameter name `request` | Rename the parameterized test variable |
| 2 | Evaluator parsed zero tests as a clean run | Duplicate quiet flags suppressed the Pytest summary | Override configured flags, require a positive test count, and add regression tests |
| 3 | RAM-only text could populate storage | Storage expression did not require an SSD/HDD/storage qualifier | Require explicit storage context and add a negative regression test |
| 4 | Live model placed the use case in category | Structured field semantics were too terse | Add field descriptions, explicit category/purpose instructions, and deterministic normalization |
| 4 | Synonym-only stock tool tied with catalog search | Tool discovery considered words but not parameter roles | Score semantic synonyms together with schema roles |
| 4 | Top-five invalidation returned false no-match | Final verification stopped after a fixed slice | Verify the full ranked queue until three valid candidates survive |
| 5 | Nested stock schema failed only during final verification | A shorter final-verification goal tied the stock capability with product details | Recursively inspect parameter roles and weight region/quantity-bearing inventory tools |
| 5 | Model parsing fallback warning disappeared on follow-up | State invalidation cleared the warning immediately after it was recorded | Append and log fallback evidence after state creation or update |
| 5 | Preference score denominator changed when preferences were absent | Raw component points were always displayed as a score out of 100 | Normalize active ranking components to a true 0-100 scale |
| 6 | PowerShell request lost `$1` from `$1,000` | PowerShell expands dollar expressions inside double-quoted arguments | Use single-quoted examples, detect the mangled pattern, and print a precise clarification |
| 6 | One OpenAI outage produced repeated connection limitations | Every orchestration step retried the unavailable model independently | Add a per-run circuit breaker and report the actual fallback execution mode |

These defects were corrected before the final evaluation. No hard constraint was relaxed to make a test pass.

