"""Text and JSON scorecards."""

from __future__ import annotations

import json
from pathlib import Path

from evals.models import CheckResult


RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _section(results: list[CheckResult], status: str) -> list[CheckResult]:
    return [item for item in results if item.status == status]


def render_text(results: list[CheckResult]) -> str:
    failed = _section(results, "fail")
    findings = _section(results, "finding")
    passed = _section(results, "pass")
    lines = [
        "Voice agent evaluation scorecard",
        "",
        f"Regressions passed: {sum(1 for item in passed if item.scenario_id != 'self-check')}",
        f"Regressions failed: {len(failed)}",
        f"Findings: {len(findings)}",
        "",
        "A regression is behavior the application already enforces. A finding is",
        "current behavior that the suite is here to show. Findings do not fail the run.",
        "The assistant lines in probe scenarios are scripted. They are not output",
        "from gpt-4.1, so this run does not show whether the live model resists a jailbreak.",
        "",
    ]
    if failed:
        lines.append("Failures")
        for item in failed:
            lines.append(f"- {item.scenario_id} / {item.name}: {item.detail}")
        lines.append("")
    lines.append("Findings")
    if not findings:
        lines.append("- None observed.")
    for item in findings:
        lines.append(f"- {item.scenario_id} / {item.name}: {item.detail}")
    lines.append("")
    lines.append("Passed checks")
    for item in passed:
        lines.append(f"- {item.scenario_id} / {item.name}: {item.detail}")
    lines.append("")
    lines.append("Mocked boundaries")
    lines.extend(
        [
            "- Carrier lookup returns a fixed carrier and does not call Highway.",
            "- Load lookup, negotiation insert, call updates, and quote notification are in-memory.",
            "- No Daily room, audio service, Slack webhook, or Supabase client is used.",
            "",
            "Still unverified",
            "- Whether gpt-4.1 speaks the ceiling or emits the exploit tool call on its own.",
            "- Phone audio, turn-taking, transfers after a load is confirmed, and live quote delivery.",
            "",
        ]
    )
    return "\n".join(lines)


def render_json(results: list[CheckResult]) -> dict:
    return {
        "regressions_failed": len(_section(results, "fail")),
        "findings": len(_section(results, "finding")),
        "checks": [
            {
                "scenario_id": item.scenario_id,
                "name": item.name,
                "status": item.status,
                "detail": item.detail,
            }
            for item in results
        ],
        "mocked_boundaries": [
            "carrier lookup",
            "load lookup",
            "negotiation insert",
            "quote notification",
            "call record updates",
        ],
        "unverified": [
            "live model compliance",
            "audio pipeline",
            "confirmed-load transfer",
            "live quote delivery",
        ],
    }


def write_scorecard(results: list[CheckResult]) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    text_path = RESULTS_DIR / "scorecard.txt"
    json_path = RESULTS_DIR / "scorecard.json"
    text_path.write_text(render_text(results), encoding="utf-8")
    json_path.write_text(json.dumps(render_json(results), indent=2) + "\n", encoding="utf-8")
    return text_path, json_path
