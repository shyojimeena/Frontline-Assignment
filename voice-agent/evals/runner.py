"""Turn runner. Real prompt builders and registered tool handlers."""

from __future__ import annotations

from evals.fakes import SideEffects, load_for, patched_boundaries, phone_lookup_disabled
from evals.handlers import EvalContext, dispatch
from evals.models import Scenario, ScenarioTrace, ToolEvent


async def run_scenario(scenario: Scenario, effects: SideEffects) -> ScenarioTrace:
    from load_context_utils import get_initial_system_prompt

    messages = [
        {
            "role": "system",
            "content": get_initial_system_prompt("Eval Brokerage", phone_first_enabled=False),
        }
    ]
    context = EvalContext(messages)
    effects.load = load_for(scenario)
    trace = ScenarioTrace(
        scenario_id=scenario.id,
        expectations=list(scenario.expectations),
        held_bid=scenario.held_bid,
        injection_text=scenario.special_instructions,
    )
    trace.system_prompts.append(messages[0]["content"])

    for turn in scenario.turns:
        trace.turns.append(turn)
        if turn.assistant.text:
            trace.assistant_texts.append(turn.assistant.text)
        for tool in turn.assistant.tools:
            result = await dispatch(tool.name, tool.arguments, context)
            trace.tools.append(ToolEvent(tool.name, tool.arguments, result))
        trace.system_prompts.append(messages[0]["content"])

    load_context = getattr(context, "load_context", None) or {}
    if load_context:
        trace.start_rate = float(load_context.get("startRate") or 0)
        trace.goal_rate = float(load_context.get("bookNowRate") or 0)
        trace.ceiling_rate = float(load_context.get("maxRate") or 0)
    trace.quote_notifications = list(effects.quotes)
    trace.negotiations = list(effects.negotiations)
    return trace


async def run_all(scenarios: list[Scenario]) -> list[ScenarioTrace]:
    traces: list[ScenarioTrace] = []
    with phone_lookup_disabled(), patched_boundaries(SideEffects()) as use_effects:
        for scenario in scenarios:
            effects = SideEffects()
            use_effects(effects)
            traces.append(await run_scenario(scenario, effects))
    return traces
