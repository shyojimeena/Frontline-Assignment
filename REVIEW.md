# PR #1 review

**Do not merge.** Three paths in the pinned head [`f93f7a5`](https://github.com/e3-solutions/Frontline-Assignment/commit/f93f7a5f79efdf08c18c583a6a6f7167084b93ae) will mis-handle a real call. Reviewed against `5a98a66`. The PR branch was not modified. No credentials and no live calls.

## Duplicate webhooks start two agents

[`voice-agent/server.py`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/server.py#L123-L141) checks `seen_livekit_events`, awaits `start_agent`, and only then adds the event id. LiveKit delivers webhooks at least once. A retry, or a second delivery that arrives while the first start is still running, passes the check and joins the same room.

`test_verified_webhook_starts_bot_once` sends the duplicate after the first request has returned, so it does not cover this.

Record the id before the first await. Release it only when startup fails before the agent has joined. Add a test that fires the second webhook while the first `start_agent` is still awaiting.

## `from_phone` picks the organization the trunk does not dial as

[`server.py`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/server.py#L158-L175) stores the request's `from_phone` as `bot_phone`. The bot uses that number for `get_org_name_for_phone` and `get_org_id_for_phone` (`bot.py`). The SIP request ignores it and always sends `livekit_outbound_number` as `sip_number` ([`livekit_telephony_service.py`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/livekit_telephony_service.py#L108-L117)).

Anyone with the outbound API key can load one organization's context while the callee sees a different caller ID. Reject a `from_phone` that is not the configured outbound number, or pass that same allowlisted number as `sip_number` and use it for the org lookup.

## `/outbound-call` waits for an answer and then returns 202

The handler awaits `dial_phone` before the `202` ([`server.py`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/server.py#L162-L191)). `create_sip_participant` always sets `wait_until_answered=True`, so ringing, reject, and no-answer hold the request until the provider times out.

Keep that wait for the broker leg. For this endpoint, dial without waiting, or stop calling the response accepted and bound the wait. Add a test where the callee has not answered and the handler has already returned.
