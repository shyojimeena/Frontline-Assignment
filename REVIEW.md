# PR #1 review — do not merge

**Recommendation: do not merge.** The LiveKit/Telnyx migration keeps the single-prompt agent, and the warm-transfer design is careful. Inbound call start is not safe under LiveKit's at-least-once webhook delivery.

Reviewed pinned head [`f93f7a5f79efdf08c18c583a6a6f7167084b93ae`](https://github.com/e3-solutions/Frontline-Assignment/commit/f93f7a5f79efdf08c18c583a6a6f7167084b93ae) against base `5a98a66274322954a0a6255f54650eec6e50c41d`. Neither branch was modified. No production credentials were used and no live call was placed.

## Findings

### 1. Duplicate webhooks can start two agents

Verified. In [`voice-agent/server.py`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/server.py#L123-L141) the event id is checked, then the bot is started, and only then is the id recorded:

```python
if event.event_id in app.state.seen_livekit_events:
    return {"status": "duplicate", "event_id": event.event_id}
# ...
await start_agent(agent_request, request.app.state.http_session)
app.state.seen_livekit_events.add(event.event_id)
```

Nothing holds a lock across the check and the add. LiveKit retries when the handler is still inside `start_agent`, or when two deliveries overlap. Both requests pass the membership check and both join the caller's room.

`test_verified_webhook_starts_bot_once` in `voice-agent/tests/test_server_livekit.py` posts the duplicate only after the first response returns, so it never hits this window.

Claim the event id before starting the bot, under one lock, and add a test where the first start is still in progress when the second request arrives. If start fails before the agent joins, release the claim so a retry can recover. If the agent may already have joined, a retry must not start a second one.

### 2. The dedupe set grows for the life of the process

Verified, secondary. `app.state.seen_livekit_events` is a process-local set with no expiry. Every accepted `participant_joined` stays there. That matches the PR's own limit that transfer state is process-local, and it will not dedupe across replicas. It is still a leak on the one process this server runs. Bound it, or store the claim somewhere that survives a restart if more than one replica will serve `/livekit-webhook`.

## What held up

- Webhook bodies are verified before parsing, and a trunk or dispatch-rule mismatch is rejected (`voice-agent/livekit_ingress.py`).
- The broker briefing waits for `wait_until_answered` and a subscribed audio track before the Room2 prompt runs (`voice-agent/room2_pipeline_service.py`).
- A move that cannot be reconciled raises `ParticipantMoveOutcomeUnknown` and is not retried (`voice-agent/livekit_telephony_service.py`, `move_participant_verified`).
- Slack failures are swallowed and do not abort the dial (`orchestrator._notify_best_effort`).
- Historical Daily call ids still display: `providerCallId` falls back to `daily_call_id`.

## Assumptions and open questions

- Assumed one Uvicorn process. The race exists even then. More than one replica makes the in-memory set insufficient.
- Did not run the PR's 127 voice tests. The local checkout used for inspection was still on the Daily dependency set, and the review did not switch onto the PR branch. Token grants were checked against current `livekit-api` `VideoGrants`: `room_join=True` still defaults `can_publish` and `can_subscribe` to true, so the bot token is not missing publish permission.
- Could not confirm whether LiveKit keeps the same participant SID after `move_participant`. Disconnect handling compares that SID (`bot.py` and `on_handoff_ended`). If the SID changes in Room1, the broker hanging up will not match `human_participant_id`, and Room1 will not be torn down until the carrier leaves. That is an unresolved behavior risk, not a defect proved from this tree.
- `calls.telephony_provider` is written on every new call. The voice service has to deploy after `web/supabase/migrations/20260907000000_add_livekit_call_attribution.sql`. That migration was not applied.
