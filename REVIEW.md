# PR #1 — request changes

Thank you for tackling a substantial provider migration. The separation between ingress,
LiveKit telephony operations, and Room1/Room2 transfer orchestration is a solid base.
In particular, webhook signatures are verified before parsing, the expected trunk and
dispatch rule are checked, and the transfer waits for both an answered broker and
subscribed broker audio before beginning the consultation.

I recommend **not merging yet** because the three issues below affect ordinary call
delivery and outbound-call behavior. This review covers pinned head
[`f93f7a5`](https://github.com/e3-solutions/Frontline-Assignment/commit/f93f7a5f79efdf08c18c583a6a6f7167084b93ae)
against base `5a98a66`. No branch was changed and no live call was placed.

## Required changes

### P1 — reserve the webhook event before starting the bot

[`voice-agent/server.py:112-129`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/server.py#L112-L129)

The handler checks `seen_livekit_events`, awaits `start_agent()`, and only then records
the event ID. Thus, two overlapping deliveries of the same valid event both pass the
check. In the repository's fixed, single-slot BotRunner, the observed consequence is
one start followed by a 503 for the second delivery; with independently accepting
runners, duplicate sessions are possible. Neither behavior is idempotent for a
provider webhook.

Please atomically reserve the event ID before the first await. Release that reservation
only if startup is known to have failed before the agent joined; otherwise a retry must
be treated as already accepted. Add a concurrent test that holds the first starter at an
await point before submitting the second request. The existing
[`test_verified_webhook_starts_bot_once`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/tests/test_server_livekit.py#L50-L71)
is sequential, so it cannot exercise this interleaving.

### P1 — use one validated number for caller ID and tenant selection

[`voice-agent/server.py:144-165`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/server.py#L144-L165),
[`voice-agent/livekit_telephony_service.py:100-110`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/livekit_telephony_service.py#L100-L110),
[`voice-agent/bot.py:226-233`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/bot.py#L226-L233)

`/outbound-call` accepts `from_phone` and forwards it as `bot_phone`, which selects the
organization context. The actual SIP request, however, always sends the configured
`LIVEKIT_SIP_OUTBOUND_NUMBER` as `sip_number`. An API-key holder can therefore select
organization A while presenting caller ID B to the carrier. That risks incorrect tenant
context and inconsistent call attribution.

Reject a request whose `from_phone` differs from the configured number, or validate it
against an explicit caller-ID allowlist and pass that same validated value to LiveKit and
the organization lookup. Add mismatch and allowed-alias tests. LiveKit documents
[`sip_number` as the outbound calling number](https://docs.livekit.io/reference/telephony/sip-api/#createsipparticipant)
and notes that stored trunks otherwise use an associated number.

### P1 — do not advertise asynchronous acceptance while waiting for answer

[`voice-agent/server.py:148-176`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/server.py#L148-L176),
[`voice-agent/livekit_telephony_service.py:100-110`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/voice-agent/livekit_telephony_service.py#L100-L110)

The endpoint waits for `dial_phone()` before returning `202`, while the shared SIP
adapter hard-codes `wait_until_answered=True`. Ringing, rejection, and no-answer can
therefore hold the HTTP request until the provider resolves the call. That is appropriate
for the broker consultation, which genuinely requires an answered leg, but surprising
for an endpoint whose response means the call was accepted for processing.

Make answer waiting an explicit per-dial option. Keep it enabled for the broker flow and
disable it for `/outbound-call`, or rename/document the endpoint as synchronous and set
a deliberate timeout. Add delayed-answer, rejected-call, and no-answer tests. LiveKit's
[`CreateSIPParticipant` reference](https://docs.livekit.io/reference/telephony/sip-api/#createsipparticipant)
states that `wait_until_answered` returns after the call is answered.

## Follow-up items

- `seen_livekit_events` retains every event for the process lifetime. Bound it with a
  TTL/maximum size; use a shared atomic idempotency record if the webhook will run in
  multiple workers or replicas.
- Roll out
  [`20260907000000_add_livekit_call_attribution.sql`](https://github.com/e3-solutions/Frontline-Assignment/blob/f93f7a5f79efdf08c18c583a6a6f7167084b93ae/web/supabase/migrations/20260907000000_add_livekit_call_attribution.sql)
  before the voice service, because it writes the new attribution columns. This is a
  deployment-order prerequisite, not a defect in the migration.
- Please confirm, with a provider-backed test, whether LiveKit preserves a participant
  SID after `MoveParticipant`; post-handoff disconnect handling currently compares the
  captured SID. Resolving by identity would avoid dependence on that behavior.

## Verification note

I checked the claimed Pipecat pause/resume API mismatch and do **not** consider it a
finding: in the pinned Pipecat 0.0.95 source, `BaseInputTransport` inherits
`FrameProcessor`, which provides the methods used here. The workspace did not contain a
Git checkout, so local PR tests could not be run; the evidence above is source tracing
and primary LiveKit/Pipecat documentation.
