"""Tool handlers the runner can call. Register a new tool in TOOLS."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from evals.fakes import CALL_ID


class EvalContext:
    """Stand-in for the Pipecat LLM context the handlers already use."""

    def __init__(self, messages: list[dict[str, Any]]):
        self.messages = messages
        self.call_id = UUID(CALL_ID)
        self.org_id = "org-eval"
        self.caller_phone = "+15555550123"
        self.call_mode = "BOT_ACTIVE"


ToolHandler = Callable[[dict[str, Any], EvalContext], Awaitable[dict[str, Any]]]


def _callback(bucket: list[dict[str, Any]]):
    async def _store(payload: Any) -> None:
        if isinstance(payload, str):
            bucket.append(json.loads(payload))
        else:
            bucket.append(payload)

    return _store


async def _invoke(handler: Callable[..., Awaitable[None]], arguments: dict[str, Any], context: EvalContext, **extra: Any) -> dict[str, Any]:
    bucket: list[dict[str, Any]] = []
    await handler("eval", "eval", arguments, None, context, _callback(bucket), **extra)
    if not bucket:
        return {"status": "error", "message": "Tool returned no result"}
    return bucket[-1]


async def _verify_carrier(arguments: dict[str, Any], context: EvalContext) -> dict[str, Any]:
    from call_helpers import verify_carrier

    return await _invoke(verify_carrier, arguments, context)


async def _get_load_context(arguments: dict[str, Any], context: EvalContext) -> dict[str, Any]:
    from call_helpers import get_load_context

    return await _invoke(
        get_load_context,
        arguments,
        context,
        daily_call_id="eval-daily-call",
        caller_phone=context.caller_phone,
    )


async def _record_agreement(arguments: dict[str, Any], context: EvalContext) -> dict[str, Any]:
    from call_helpers import record_agreement

    return await _invoke(record_agreement, arguments, context)


async def _transfer_to_human(arguments: dict[str, Any], context: EvalContext) -> dict[str, Any]:
    from transfer_tool_handler import TransferToolHandler

    handler = TransferToolHandler(*(None,) * 10)
    return await _invoke(handler.handle_transfer_to_human, arguments, context)


TOOLS: dict[str, ToolHandler] = {
    "verify_carrier": _verify_carrier,
    "get_load_context": _get_load_context,
    "record_agreement": _record_agreement,
    "transfer_to_human": _transfer_to_human,
}


async def dispatch(name: str, arguments: dict[str, Any], context: EvalContext) -> dict[str, Any]:
    handler = TOOLS.get(name)
    if handler is None:
        return {"status": "error", "message": f"Unknown tool {name}"}
    return await handler(arguments, context)
