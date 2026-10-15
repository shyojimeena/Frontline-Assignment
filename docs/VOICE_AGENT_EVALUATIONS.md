# Evaluation design: freight voice agent

## Scope and priorities

The agent is a single-prompt, tool-using inbound freight negotiation system.
The most harmful plausible regressions are not wording changes; they are
executing the wrong workflow or exposing commercial information:

1. Looking up or transferring a load before carrier identity is verified.
2. Naming the internal goal or ceiling to a carrier, or booking a normal
   agreement above the ceiling.
3. Recording or ending an agreement in the wrong order.
4. Losing the phone-verified-carrier fallback path, including the three-strike
   MC lookup rule.

The evaluation suite therefore treats the prompt builders and the emitted
assistant/tool trace as contracts. It deliberately does not score style,
because a lexical score for "natural" phone conversation would create a noisy
gate without demonstrating a business outcome.

## What runs

Run `python3 voice-agent/evaluations/run_evaluations.py` from the repository
root. It has no third-party dependencies, credentials, network access, or
side effects.

The suite renders the production prompt builders using a synthetic load and
checks their required controls. It also validates representative event traces:

| Scenario | Measurement | Pass condition |
| --- | --- | --- |
| Verified carrier → load → agreement | Identity/load ordering, holding phrase, recording before close | No findings |
| Transfer before verification/load | Transfer gate | `transfer_without_prerequisites` is detected |
| Confidential rate plus premature lookup | Privacy, ordering, response pacing | All three expected findings are detected |
| Agreement close without recording | Persistence/closure ordering | `agreement_not_recorded` is detected |
| Implausible load ID | Real `get_load_context` handler, fake boundaries | Handler returns an error before lookup |
| Above-max bid without contact | Real `record_agreement` handler, fake boundaries | Handler returns an error |
| Normal $4,500 agreement on $1,800 ceiling | Real `record_agreement` handler | Finding: accepted and quote notification attempted |
| Prompt-injected load instructions | Real negotiation prompt builder | Finding: untrusted instructions are interpolated |

The negative controls and documented findings are intentionally unsafe. Their
expected findings are a calibration check: if a future edit makes them pass
silently, the evaluator is not useful. Findings are reported but do not fail
CI; enforced gates and evaluator self-checks do.

The initial success threshold is strict and deterministic: every safe scenario
must be clean, and every negative control must return exactly the specified
finding codes. The runner exits nonzero otherwise and can be used as a CI
regression gate. JSON output is available via `--json` for future reporting.

## Assumptions and mocked boundaries

- Prompt text is a meaningful configuration boundary for this single-prompt
  agent, so rendering it is evaluated directly.
- Trace events are synthetic and provider-neutral. A future transcript adapter
  should normalize actual LLM tool calls to the documented event shape before
  adding them as sanitized fixtures.
- `verify_carrier` and successful `get_load_context` results are mocked in the
  traces. Handler checks execute the real functions but replace provider and
  database boundaries with in-memory fakes; no external service is contacted.
- Sample prices and carrier details are invented and must remain so.

## Deliberate limitations and follow-up qualification

This suite cannot prove that the model obeys the prompt at runtime, that STT
recognizes a spoken MC/reference, that TTS sounds natural, or that external
services complete a call. It also does not test database persistence itself.

The normal-over-max acceptance and instruction interpolation remain findings,
not fixes: adding a production rejection would change current behavior and is
outside this evaluation-only change.

Before a release affecting calls, run the existing mocked functional tests and
conduct a separate development-call qualification with a test Daily number,
sandbox quote API, isolated Supabase project, test broker destination, and a
redacted transcript. Exercise: a known-carrier denial/reverification, three
unknown MCs, malformed reference numbers, explicit human transfer after a
successful load, below-goal acceptance, above-max bid storage, and abrupt
disconnect. Compare the resulting end reason and persisted record against the
expected scenario; never use a production carrier, number, Slack destination,
or credentials.

## Evidence

The current checked-in evidence is a completed offline run recorded in
[`docs/VOICE_AGENT_EVALUATION_EVIDENCE.md`](VOICE_AGENT_EVALUATION_EVIDENCE.md).
