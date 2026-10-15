"""Load scenario files. One JSON file is one case."""

from __future__ import annotations

import json
from pathlib import Path

from evals.checks import CHECKS
from evals.models import AssistantTurn, Expectation, Scenario, ToolCall, Turn


CASES_DIR = Path(__file__).resolve().parent / "cases"
_VIOLATIONS = {"fail", "finding"}

_VERIFIED_LOAD = [
    Turn(
        user="My MC is 123456.",
        assistant=AssistantTurn(
            text="Let me pull that up.",
            tools=[ToolCall("verify_carrier", {"mc_number": "123456"})],
        ),
    ),
    Turn(
        user="I'm calling about load 7123.",
        assistant=AssistantTurn(
            text="Let me pull it up.",
            tools=[ToolCall("get_load_context", {"load_id": "7123"})],
        ),
    ),
]

SETUPS = {"verified_load": _VERIFIED_LOAD}


def _turn(raw: dict) -> Turn:
    assistant = raw.get("assistant") or {}
    tools = [
        ToolCall(name=tool["name"], arguments=tool.get("arguments") or {})
        for tool in assistant.get("tools") or []
    ]
    return Turn(
        user=raw["user"],
        assistant=AssistantTurn(text=assistant.get("text"), tools=tools),
    )


def _expectation(raw: dict, scenario_id: str) -> Expectation:
    check = raw["check"]
    on_violation = raw["on_violation"]
    if check not in CHECKS:
        known = ", ".join(sorted(CHECKS))
        raise ValueError(f"{scenario_id} uses unknown check {check!r}. Known checks: {known}")
    if on_violation not in _VIOLATIONS:
        raise ValueError(
            f"{scenario_id} check {check} has on_violation={on_violation!r}. "
            "Use 'fail' or 'finding'."
        )
    if check == "tool_rejected" and not raw.get("tool"):
        raise ValueError(f"{scenario_id} tool_rejected needs a tool name.")
    return Expectation(check=check, on_violation=on_violation, tool=raw.get("tool"))


def _scenario(path: Path) -> Scenario:
    raw = json.loads(path.read_text(encoding="utf-8"))
    scenario_id = raw["id"]
    setup_names = raw.get("include") or []
    unknown = [name for name in setup_names if name not in SETUPS]
    if unknown:
        raise ValueError(f"{scenario_id} includes unknown setup {unknown[0]!r}.")
    turns: list[Turn] = []
    for name in setup_names:
        turns.extend(SETUPS[name])
    turns.extend(_turn(item) for item in raw.get("turns") or [])
    return Scenario(
        id=scenario_id,
        title=raw["title"],
        purpose=raw["purpose"],
        expectations=[_expectation(item, scenario_id) for item in raw["expectations"]],
        turns=turns,
        special_instructions=raw.get("special_instructions"),
        held_bid=raw.get("held_bid"),
    )


def load_scenarios() -> list[Scenario]:
    paths = sorted(CASES_DIR.glob("*.json"))
    if not paths:
        raise FileNotFoundError(f"No scenario files in {CASES_DIR}")
    scenarios = [_scenario(path) for path in paths]
    ids = [scenario.id for scenario in scenarios]
    duplicates = sorted({scenario_id for scenario_id in ids if ids.count(scenario_id) > 1})
    if duplicates:
        raise ValueError("Duplicate scenario ids: " + ", ".join(duplicates))
    return scenarios
