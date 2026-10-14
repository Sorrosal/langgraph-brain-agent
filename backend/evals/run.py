"""Run the eval suites and print one scorecard (a JSON report is saved under evals/reports/).

    uv run python -m evals.run                         # context-static only: free, no network
    uv run python -m evals.run --suite all             # everything (real model: a few cents)
    uv run python -m evals.run --suite behaviour -k email

Suites:
  context-static  what reaches the model, on the real graph with a scripted model (also in CI)
  context-model   memory extraction, summary retention, grounding, recall with real embeddings
  behaviour       end-to-end decisions: approvals, blocks, dates, prompt injection
Nothing is written to PostgreSQL and no cloud resource is created.
"""

import argparse
import asyncio
import sys

from brain_agent.config import Settings
from evals.behaviour import run_behaviour_evals
from evals.context_model import run_model_context_evals
from evals.context_static import run_static_context_evals
from evals.scorecard import Metric, print_scorecard, save_report

SUITES = ("context-static", "context-model", "behaviour")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Brain Agent evals")
    parser.add_argument("--suite", choices=[*SUITES, "all"], default="context-static")
    parser.add_argument("-k", default="", help="behaviour: only cases whose id contains this")
    args = parser.parse_args()
    chosen = SUITES if args.suite == "all" else (args.suite,)
    metrics: list[Metric] = []
    if "context-static" in chosen:
        metrics += await run_static_context_evals()
    if "context-model" in chosen or "behaviour" in chosen:
        settings = Settings()
        if "context-model" in chosen:
            metrics += await run_model_context_evals(settings)
        if "behaviour" in chosen:
            metrics += await run_behaviour_evals(settings, args.k)
    print_scorecard(metrics)
    print(f"report: {save_report(metrics)}")
    return 0 if all(m.passed for m in metrics) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
