# Follow-up validation of supplied webhook findings

The supplied evidence is substantially correct, with one scope correction.

## Verified

1. **The webhook idempotency race is real and merge-blocking.** In `server.py`, the
   event ID is checked, `start_agent()` is awaited, and only afterwards is the ID added
   to `seen_livekit_events`. `test_verified_webhook_starts_bot_once` submits its second
   POST only after the first returned, so it does not exercise overlapping delivery.
   Reserve before the first await, release only when it is safe for a retry, and add a
   concurrency test which blocks the first starter.

   Scope correction: with the repository's one-slot BotRunner, the normal one-process
   result is one start plus a 503 rejection for the second request, not proven duplicate
   bot execution. It remains a production failure under at-least-once delivery;
   independently accepting runners can also create duplicate sessions.

2. **The set is process-local and unbounded.** Every accepted event ID is retained for
   the lifetime of the server. A TTL/size bound is required; use a shared atomic store
   if workers or replicas serve the webhook.

3. **Migration ordering is a release prerequisite.** `create_call_record` now writes
   `telephony_provider` and `provider_call_id`, while the PR adds those columns only in
   `web/supabase/migrations/20260907000000_add_livekit_call_attribution.sql`. Apply the
   migration before rolling out the voice service. This is not a code defect if the
   deployment process applies migrations first.

## Confirmed as non-findings / risks

- Pipecat 0.0.95's `BaseInputTransport` inherits `FrameProcessor`; the alleged missing
  pause/resume methods are present.
- The participant-SID-after-move concern is unresolved provider behavior, not a proven
  defect. Add a provider-backed different-SID test or resolve disconnects by identity.
- The bot token includes `VideoGrants(room_join=True)`; no missing publish-permission
  defect was established.
