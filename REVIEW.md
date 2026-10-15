# PR #1 review — request changes

**Recommendation: do not merge yet.** The Daily-to-LiveKit/Telnyx boundaries and the
warm-transfer state machine are thoughtfully separated, but three verified paths can
either create duplicate agents, select the wrong tenant for a call, or make the public
outbound endpoint wait for a human pickup despite reporting `202 Accepted`.

## Context and method

I compared the pinned PR head `f93f7a5f79efdf08c18c583a6a6f7167084b93ae` with the
specified base `5a98a66274322954a0a6255f54650eec6e50c41d`, concentrating on provider
ingress, caller/organization attribution, SIP dialing semantics, and the Room1/Room2
handoff lifecycle. I inspected the PR source and its focused tests and checked the
provider behavior against [LiveKit's SIP API documentation](https://docs.livekit.io/reference/telephony/sip-api/).

The supplied workspace contained no Git checkout, so I could not run the advertised
test suite locally. No credentials or real calls were used. Line numbers below refer
to the pinned head.

## Required review comments

### P1 — reserve inbound webhook IDs before yielding

[`voice-agent/server.py:112-129`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/server.py#L112-L129)

`event_id` is tested for membership, then the handler awaits `start_agent()`, and only
after it returns adds the ID to `seen_livekit_events`. Two deliveries of the same signed
LiveKit event can both reach line 128 before either reaches line 129. In the stated
single-BotRunner deployment, one will normally start and the other will be rejected by
that runner with a 503; with independently accepting runners, both can start a session
for the same carrier. Either result is unsafe under normal webhook retries: a delivery
that should have been idempotently acknowledged becomes an error/retry or a duplicate
call. The current `test_verified_webhook_starts_bot_once` is sequential: it submits the
second request only after the first response returns, so it cannot cover this window.

Reserve the ID atomically before the first await, release it if startup fails, and make
the duplicate response deterministic. A process-local set is also unbounded and cannot
deduplicate across restarts/workers; use a bounded, shared idempotency store if this
service is deployed with more than one worker. Add a concurrent-delivery test that
holds the starter at its first await and asserts exactly one start.

### P2 — bound the process-local event-id retention

[`voice-agent/server.py:48`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/server.py#L48),
[`voice-agent/server.py:112-129`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/server.py#L112-L129)

Every accepted event id remains in `seen_livekit_events` for the process lifetime. This
is unbounded memory retention even in the declared one-process deployment, and it loses
the idempotency record on restart and cannot coordinate replicas. Bound the local cache
with a TTL/maximum size at minimum; use a shared, atomic idempotency record if the
endpoint can be served by more than one worker or replica.

### P1 — do not let `from_phone` choose tenant context when it is not the SIP caller ID

[`voice-agent/server.py:144-165`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/server.py#L144-L165),
[`voice-agent/livekit_telephony_service.py:100-110`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/livekit_telephony_service.py#L100-L110)

The authenticated `/outbound-call` payload accepts arbitrary normalized `from_phone`
and passes it to `AgentRequest.bot_phone`; the bot later uses `bot_phone` for the
organization/call record. But every actual SIP request uses only
`LIVEKIT_SIP_OUTBOUND_NUMBER` as `sip_number`. Consequently a caller holding this API
key can request the organization context for number A while the PSTN leg presents
number B. This breaks tenant attribution and may expose the wrong load/negotiation
context. LiveKit documents `sip_number` as the outbound calling number and notes that
stored trunks otherwise select a trunk-associated number.

Either reject payload values that differ from the configured/authorized outbound number,
or validate an allowlisted caller ID and pass that same value as `sip_number`. Ensure the
tenant lookup derives from that validated effective caller ID; add mismatch and
authorized-alias tests.

### P1 — make answer-waiting explicit; the asynchronous endpoint currently blocks

[`voice-agent/server.py:148-176`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/server.py#L148-L176),
[`voice-agent/livekit_telephony_service.py:100-110`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/livekit_telephony_service.py#L100-L110)

`/outbound-call` awaits `dial_phone()` before returning its `202`, while the shared SIP
adapter always supplies `wait_until_answered=True`. LiveKit specifies that this setting
returns only after answer (including voicemail); ringing, reject, and no-answer can
therefore hold the HTTP request until the carrier/provider timeout, then enter the
exception cleanup path rather than promptly acknowledging initiation. Waiting is useful
for the Room2 broker consultation, but it is an unsuitable hidden behavior for an API
whose response means "accepted."

Make `wait_until_answered` an explicit per-dial option. Keep it true for the broker
flow, and use false for `/outbound-call` (or rename/document the endpoint as synchronous
and impose a deliberate bounded timeout). Add delayed-answer, reject, and no-answer
tests.

## Evidence and non-findings

- `LiveKitWebhookService` verifies the raw-body signature before parsing and validates
  trunk and dispatch-rule IDs. The issue above is after successful verification, in
  application idempotency.
- The warm-transfer orchestrator gates primary media, starts a separate hold publisher,
  waits for broker answer plus subscribed audio, and verifies broker presence in Room1
  before recording transfer success. I found no additional verified lifecycle defect in
  the inspected error/cleanup paths.
- I specifically checked the claim that `gate_primary_media()` calls nonexistent Pipecat
  APIs. It is **not a valid finding**: the pinned `pipecat-ai==0.0.95`
  `BaseInputTransport` inherits `FrameProcessor`, which defines
  `pause_processing_frames()` and `resume_processing_frames()`.

## Assumptions and follow-up questions

- The PR explicitly scopes transfer state to a fixed single-call runner. I treat that as
  an intentional capacity constraint, not a new blocking correctness finding; confirm
  deployment supplies one isolated runner per concurrent call before production rollout.
- LiveKit's move API identifies participants by identity. Confirm with a provider-backed
  test whether the participant SID is preserved after `MoveParticipant`; the disconnect
  observer currently compares the Room2-captured SID. If it can change, reconcile the
  destination SID or compare by identity so a broker hangup cannot leak the observer.
- The PR adds `calls.telephony_provider` and `calls.provider_call_id`; deployment must
  apply `web/supabase/migrations/20260907000000_add_livekit_call_attribution.sql` before
  voice-service rollout. This is a release-order prerequisite, not a defect in the
  migration itself.
- Run the focused voice tests after the three fixes and conduct an isolated LiveKit/Telnyx
  qualification call covering answer, no-answer, duplicate webhook delivery, transfer,
  and both post-handoff disconnect orders.
