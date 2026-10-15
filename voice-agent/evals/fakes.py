"""In-memory stand-ins for carrier, load, negotiation, and quote side effects."""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, patch

from evals.models import Scenario

LOAD_REF = "7123"
LOAD_UUID = "11111111-1111-1111-1111-111111111111"
NEGOTIATION_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
CALL_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

START_RATE = 2000.0
GOAL_RATE = 2500.0
CEILING_RATE = 2800.0


@dataclass
class SideEffects:
    """What one scenario wrote. A new instance is used for every scenario."""

    load: dict[str, Any] | None = None
    quotes: list[dict[str, Any]] = field(default_factory=list)
    negotiations: list[dict[str, Any]] = field(default_factory=list)


def legacy_load(special_instructions: str | None = None) -> dict[str, Any]:
    """Legacy loads row so the opening offer and the goal stay distinct.

    A KCH row copies offer_rate into both, which collapses the zone checks.
    """
    return {
        "id": LOAD_UUID,
        "load_id": LOAD_REF,
        "origin_city": "Los Angeles",
        "origin_state": "CA",
        "destination_city": "Dallas",
        "destination_state": "TX",
        "pickup_time": "January 15th, 2026",
        "dropoff_time": "January 17th, 2026",
        "equipment": "Van",
        "commodity": "Packaged food",
        "special_instructions": special_instructions,
        "start_rate": START_RATE,
        "book_now_rate": GOAL_RATE,
        "max_rate": CEILING_RATE,
        "transfer_call_to": "5550100",
        "transfer_country_code": "+1",
    }


def load_for(scenario: Scenario) -> dict[str, Any]:
    return legacy_load(scenario.special_instructions)


@contextmanager
def phone_lookup_disabled():
    key = "HIGHWAY_PHONE_LOOKUP_ENABLED"
    previous = os.environ.get(key)
    os.environ[key] = "false"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous


@contextmanager
def patched_boundaries(effects: SideEffects):
    """Patch the handler module for the whole run.

    Handlers read `effects` on each call, and the runner swaps in a fresh
    SideEffects before every scenario. Patches stay up so scenarios do not
    pay import and patch cost, and one scenario cannot leak quotes into the next.
    """

    async def fetch_carrier(_mc: str) -> dict[str, Any]:
        return {"data": {"dbaName": "Wallin Transport LLC", "dotNumber": "998877"}}

    def create_negotiation(**kwargs: Any) -> dict[str, str]:
        effects_box["current"].negotiations.append(kwargs)
        return {"id": NEGOTIATION_ID}

    def notify_carrier_quote(**kwargs: Any) -> str:
        effects_box["current"].quotes.append(kwargs)
        return "eval-quote"

    def get_load_by_reference(load_id: str, org_id: str | None = None):
        load = effects_box["current"].load or {}
        if load_id == load.get("load_id"):
            return load
        return None

    effects_box = {"current": effects}

    def use(next_effects: SideEffects) -> None:
        effects_box["current"] = next_effects

    with (
        patch.multiple(
            "call_helpers",
            fetch_carrier_by_mc=AsyncMock(side_effect=fetch_carrier),
            update_call_mc=lambda *_args, **_kwargs: None,
            update_call_load=lambda *_args, **_kwargs: None,
            link_negotiation_to_call=lambda *_args, **_kwargs: None,
        ),
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
    ):
        yield use
