"""Turn runner. Real prompt builders and tool handlers, in-memory side effects."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from evals.scenarios import (
    CALL_ID,
    CEILING_RATE,
    GOAL_RATE,
    NEGOTIATION_ID,
    START_RATE,
    Scenario,
    legacy_load,
)


@dataclass
class ToolEvent:
    name: str
    arguments: dict
    result: dict


@dataclass
class ScenarioTrace:
    scenario_id: str
    kind: str
    checks: list[str]
    held_bid: float | None
    system_prompts: list[str] = field(default_factory=list)
    assistant_texts: list[str] = field(default_factory=list)
    tools: list[ToolEvent] = field(default_factory=list)
    quote_notifications: list[dict] = field(default_factory=list)
    negotiations: list[dict] = field(default_factory=list)
    start_rate: float = START_RATE
    goal_rate: float = GOAL_RATE
    ceiling_rate: float = CEILING_RATE
    injection_text: str | None = None


class EvalContext:
    """Stand-in for the Pipecat LLM context the handlers already use."""

    def __init__(self, messages: list[dict]):
        self.messages = messages
        self.call_id = UUID(CALL_ID)
        self.org_id = "org-eval"
        self.caller_phone = "+15555550123"
        self.call_mode = "BOT_ACTIVE"


def _result_from_callback(bucket: list[dict]):
    async def _callback(payload: Any) -> None:
        if isinstance(payload, str):
            bucket.append(json.loads(payload))
        else:
            bucket.append(payload)

    return _callback


async def _dispatch(name: str, arguments: dict, context: EvalContext) -> dict:
    from call_helpers import get_load_context, record_agreement, verify_carrier
    from transfer_tool_handler import TransferToolHandler

    bucket: list[dict] = []
    callback = _result_from_callback(bucket)
    if name == "verify_carrier":
        await verify_carrier(name, "eval", arguments, None, context, callback)
    elif name == "get_load_context":
        await get_load_context(
            name,
            "eval",
            arguments,
            None,
            context,
            callback,
            daily_call_id="eval-daily-call",
            caller_phone=context.caller_phone,
        )
    elif name == "record_agreement":
        await record_agreement(name, "eval", arguments, None, context, callback)
    elif name == "transfer_to_human":
        handler = TransferToolHandler(
            None, None, None, None, None, None, None, None, None, None
        )
        await handler.handle_transfer_to_human(
            name, "eval", arguments, None, context, callback
        )
    else:
        bucket.append({"status": "error", "message": f"Unknown tool {name}"})
    if not bucket:
        return {"status": "error", "message": "Tool returned no result"}
    return bucket[-1]


async def run_scenario(scenario: Scenario, store: dict) -> ScenarioTrace:
    from load_context_utils import get_initial_system_prompt

    messages = [
        {
            "role": "system",
            "content": get_initial_system_prompt("Eval Brokerage", phone_first_enabled=False),
        }
    ]
    context = EvalContext(messages)
    store["load"] = legacy_load(scenario.special_instructions)
    trace = ScenarioTrace(
        scenario_id=scenario.id,
        kind=scenario.kind,
        checks=list(scenario.checks),
        held_bid=scenario.held_bid,
        injection_text=scenario.special_instructions,
    )
    trace.system_prompts.append(messages[0]["content"])

    for turn in scenario.turns:
        if turn.assistant.text:
            trace.assistant_texts.append(turn.assistant.text)
        for tool in turn.assistant.tools:
            result = await _dispatch(tool.name, tool.arguments, context)
            trace.tools.append(ToolEvent(tool.name, tool.arguments, result))
        trace.system_prompts.append(messages[0]["content"])

    load_context = getattr(context, "load_context", None) or {}
    if load_context:
        trace.start_rate = float(load_context.get("startRate") or START_RATE)
        trace.goal_rate = float(load_context.get("bookNowRate") or GOAL_RATE)
        trace.ceiling_rate = float(load_context.get("maxRate") or CEILING_RATE)
    trace.quote_notifications = list(store["quotes"])
    trace.negotiations = list(store["negotiations"])
    store["quotes"].clear()
    store["negotiations"].clear()
    return trace


def _install_mocks(store: dict):
    from unittest.mock import AsyncMock, patch

    async def fetch_carrier(_mc: str) -> dict:
        return {"data": {"dbaName": "Wallin Transport LLC", "dotNumber": "998877"}}

    def create_negotiation(**kwargs) -> dict:
        store["negotiations"].append(kwargs)
        return {"id": NEGOTIATION_ID}

    def notify_carrier_quote(**kwargs) -> str:
        store["quotes"].append(kwargs)
        return "eval-quote"

    def get_load_by_reference(load_id: str, org_id: str | None = None):
        load = store.get("load") or {}
        if load_id == load.get("load_id"):
            return load
        return None

    return patch.multiple(
        "call_helpers",
        fetch_carrier_by_mc=AsyncMock(side_effect=fetch_carrier),
        update_call_mc=lambda *_args, **_kwargs: None,
        update_call_load=lambda *_args, **_kwargs: None,
        link_negotiation_to_call=lambda *_args, **_kwargs: None,
    ), [
        patch(
            "call_helpers.NegotiationDBService.get_load_by_reference",
            side_effect=get_load_by_reference,
        ),
        patch(
            "call_helpers.NegotiationDBService.create_negotiation",
            side_effect=create_negotiation,
        ),
        patch(
            "call_helpers.NegotiationDBService.notify_carrier_quote",
            side_effect=notify_carrier_quote,
        ),
    ]


async def run_all(scenarios: list[Scenario]) -> list[ScenarioTrace]:
    os.environ["HIGHWAY_PHONE_LOOKUP_ENABLED"] = "false"
    store: dict = {"load": None, "quotes": [], "negotiations": []}
    patch_helpers, service_patches = _install_mocks(store)
    traces: list[ScenarioTrace] = []
    with patch_helpers:
        for service_patch in service_patches:
            service_patch.start()
        try:
            for scenario in scenarios:
                traces.append(await run_scenario(scenario, store))
        finally:
            for service_patch in service_patches:
                service_patch.stop()
    return traces
