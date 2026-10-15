# PR #1 review — request changes

**Do not merge.** The migration's ingress validation and transfer lifecycle are
well-considered, but three P1 call paths need correction.

## Required changes

1. **P1 — make webhook startup idempotent** (`server.py:112-129`)

   The event ID is checked, `start_agent()` is awaited, then recorded. An overlapping
   delivery passes the same check. With the single-slot BotRunner, the proven result is
   a spurious 503/retry for the second delivery; independently accepting runners can
   start duplicates. Reserve before the first await and add a concurrent-delivery test.

2. **P1 — align tenant context with the real caller ID** (`server.py:144-165`,
   `livekit_telephony_service.py:100-110`)

   Arbitrary `from_phone` selects organization context, but SIP always dials as the
   configured outbound number. Reject mismatches, or allowlist an ID and use that same
   effective caller ID for SIP and organization lookup.

3. **P1 — do not block an accepted outbound request on answer** (`server.py:148-176`,
   `livekit_telephony_service.py:100-110`)

   `/outbound-call` awaits `wait_until_answered=True` before returning `202`; ringing
   and no-answer therefore hold the HTTP request. Make answer waiting per-dial: retain
   it for broker consultation, but not asynchronous initiation.

## Follow-up

- Bound the process-local `seen_livekit_events` cache; use a shared atomic store for
  worker/replica deployments.
- Apply `20260907000000_add_livekit_call_attribution.sql` before voice rollout.
- Confirm participant-SID behavior after `MoveParticipant`, or handle disconnects by
  identity.
