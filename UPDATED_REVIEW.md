# PR #1 review — request changes

**Do not merge.** The migration's LiveKit ingress validation, warm-transfer answer/audio
gating, and ambiguous-move handling are sound in the paths reviewed. Three P1 issues
remain:

1. **Webhook idempotency is not atomic** (`voice-agent/server.py:112-129`). The event
   is marked only after awaited startup; the supplied sequential test cannot cover
   overlap. Reserve before awaiting and release only when retry is safe. With this
   repository's single-slot runner, the proven same-process outcome is a spurious 503
   and retry for the second delivery—not necessarily two active bots. Multiple
   independently accepting runners can start duplicates. Both require a fix.

2. **`from_phone` selects a different tenant from the real caller ID**
   (`server.py:144-165`, `livekit_telephony_service.py:100-110`). The request's
   unvalidated value becomes `bot_phone`; `bot.py:230-233` uses it for organization
   lookup, while the SIP request always places the configured outbound number in
   `sip_number`. Reject mismatches or validate an allowlisted ID and use that exact
   effective caller ID for SIP and tenant lookup.

3. **`/outbound-call` waits for an answer before returning `202`** (`server.py:148-176`,
   `livekit_telephony_service.py:100-110`). The shared SIP request hard-codes
   `wait_until_answered=True`; a ringing or unanswered carrier request blocks until the
   provider resolves it. Make the wait an explicit dial option, retain it for broker
   consultation, and do not wait for the public initiation endpoint (or explicitly
   define and bound a synchronous contract).

Secondary: `seen_livekit_events` is unbounded and process-local; introduce a bounded
TTL cache and a shared atomic idempotency store where replicas are possible.
