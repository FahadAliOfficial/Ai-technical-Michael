# Evaluation report

## Method

The project uses a cycle-based acceptance process:

1. implement a bounded capability;
2. run focused tests;
3. run the full suite;
4. score five quality gates;
5. improve any failed gate without removing completed behavior;
6. repeat until all gates pass.

The five gates are requirements/state, dynamic tools, validation/ranking, resilience/auditability, and tests/documentation.

## Final result

The authoritative machine-readable result is `evidence/evaluation-results.json`. It records test totals, success rate, gate status, catalog size, scenario count, and any captured failure analysis.

- Automated tests: 58 passed, 0 failed, 0 errors
- Automated success rate: 100%
- Quality gates: 5/5
- Documented scenarios: 40
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

These defects were corrected before the final evaluation. No hard constraint was relaxed to make a test pass.

