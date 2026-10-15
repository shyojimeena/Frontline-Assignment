# Validation notes

- **Webhook race: verified.** `server.py` records an event ID only after awaiting bot
  startup. The existing duplicate-webhook test is sequential and does not cover an
  overlapping delivery. In the fixed one-slot runner, the demonstrated effect is a
  spurious 503/retry for the second delivery; independently accepting runners can
  duplicate a session.
- **Retention: verified.** `seen_livekit_events` is unbounded and process-local.
- **Outbound tenant/caller-ID divergence: verified.** `from_phone` drives `bot_phone`
  organization lookup while the SIP adapter always uses the configured outbound number.
- **Outbound answer wait: verified.** `/outbound-call` awaits a SIP request with
  `wait_until_answered=True` before returning `202`.
- **Not a finding.** Pipecat 0.0.95 input transport inherits the frame pause/resume
  methods used by transfer media.
- **Unresolved risk.** Confirm whether LiveKit preserves participant SID across a move,
  or use identity for post-handoff disconnect handling.
