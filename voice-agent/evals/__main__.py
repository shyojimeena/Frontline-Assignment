"""Run the offline evaluation suite.

Usage, from voice-agent/:

    python -m evals
"""

from __future__ import annotations

import asyncio
import sys

from loguru import logger

from evals.report import render_text, write_scorecard
from evals.runner import run_all
from evals.scenarios import scenarios
from evals.scorers import score_trace, self_check


def main() -> int:
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    results = [self_check()]
    traces = asyncio.run(run_all(scenarios()))
    for trace in traces:
        results.extend(score_trace(trace))
    text_path, json_path = write_scorecard(results)
    print(render_text(results))
    print(f"Wrote {text_path}")
    print(f"Wrote {json_path}")
    if any(item.status == "fail" for item in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
