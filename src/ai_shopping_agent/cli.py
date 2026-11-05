from __future__ import annotations

import argparse
import json

from .agent import ShoppingAgent
from .config import Settings


DEFAULT_REQUEST = (
    "I need a laptop for software development. My maximum budget is $1,200. "
    "It must have at least 32GB RAM and 1TB SSD storage. I prefer 10+ hours "
    "of battery life and a weight under 1.6kg. Compare the best options and recommend one."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the AI shopping agent")
    parser.add_argument("request", nargs="?", default=DEFAULT_REQUEST)
    parser.add_argument("--json", action="store_true", help="Print complete state as JSON")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    agent = ShoppingAgent(Settings.from_env())
    state = agent.run(args.request)
    if args.json:
        print(state.model_dump_json(indent=2))
        return
    recommendation = state.recommendation
    print(f"Mode: {agent.execution_mode}")
    print(recommendation.message if recommendation else "The agent did not produce a result.")
    if recommendation and recommendation.clarification_question:
        print("Clarification:")
        print(recommendation.clarification_question)
    if recommendation and recommendation.constraint_checks:
        print("Mandatory checks:")
        for check in recommendation.constraint_checks:
            print(f"- {check}")
    if recommendation and recommendation.comparison_summary:
        print("Comparison:")
        print(recommendation.comparison_summary)
    if recommendation and recommendation.alternatives:
        print("Alternatives:")
        for item in recommendation.alternatives:
            print(f"- {item.product.name}: ${item.product.price:,.2f} (score {item.score:.2f})")
    if recommendation and recommendation.limitations:
        print("Limitations:")
        print(json.dumps(recommendation.limitations, indent=2))


if __name__ == "__main__":
    main()
