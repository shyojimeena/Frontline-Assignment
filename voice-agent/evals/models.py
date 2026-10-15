"""Data the runner, checks, and scorecard share."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class AssistantTurn:
    text: str | None = None
    tools: list[ToolCall] = field(default_factory=list)


@dataclass
class Turn:
    user: str
    assistant: AssistantTurn


@dataclass
class Expectation:
    """One check applied to a scenario trace.

    on_violation is "fail" when the check must hold for the run to pass.
    It is "finding" when a violation is current behavior the suite should show.
    """

    check: str
    on_violation: str
    tool: str | None = None


@dataclass
class Scenario:
    id: str
    title: str
    purpose: str
    expectations: list[Expectation]
    turns: list[Turn]
    special_instructions: str | None = None
    held_bid: float | None = None


@dataclass
class ToolEvent:
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


@dataclass
class ScenarioTrace:
    scenario_id: str
    expectations: list[Expectation]
    held_bid: float | None
    turns: list[Turn] = field(default_factory=list)
    system_prompts: list[str] = field(default_factory=list)
    assistant_texts: list[str] = field(default_factory=list)
    tools: list[ToolEvent] = field(default_factory=list)
    quote_notifications: list[dict[str, Any]] = field(default_factory=list)
    negotiations: list[dict[str, Any]] = field(default_factory=list)
    start_rate: float = 0
    goal_rate: float = 0
    ceiling_rate: float = 0
    injection_text: str | None = None


@dataclass
class CheckResult:
    scenario_id: str
    name: str
    status: str
    detail: str
