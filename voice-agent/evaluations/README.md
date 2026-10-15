# Voice-agent contract evaluations

Run from the repository root:

```bash
python3 voice-agent/evaluations/run_evaluations.py
python3 voice-agent/evaluations/run_evaluations.py --json
```

The runner uses only Python's standard library and synthetic data. It makes no
network calls and does not read environment variables, so it is safe in CI and
requires no Daily, OpenAI, Supabase, carrier-verification, or speech-provider
credentials.

It has three complementary checks:

1. Prompt-contract checks render the real greeting and negotiation prompts and
   assert the high-risk instructions are present: identity before load lookup,
   three-strike MC handling, identity replacement, confidential-rate rules,
   agreement recording, and transfer prerequisites.
2. Stateful trace checks validate tool-call traces against the same safety
   invariants. The included unsafe traces are *negative controls*: they are
   expected to produce findings, proving the evaluator is able to fail.
3. Handler-boundary checks execute the production `call_helpers.py` handler
   with provider/database boundaries replaced by in-memory fakes.

`N/N evaluation cases passed` means enforced gates behaved as expected and
known findings were reproduced exactly. A non-zero exit means an enforced gate
regressed or the evaluator result changed unexpectedly. Findings do not fail
CI because this change exposes gaps without changing production behavior. For
a captured model transcript, replace or add a case in
`trace_cases.json`; never include production caller data.

This is a regression gate, not a claim that an LLM will follow every prompt
instruction. It cannot evaluate speech recognition, spoken naturalness, tool
execution, provider behavior, or real calls. See
[`docs/VOICE_AGENT_EVALUATIONS.md`](../../docs/VOICE_AGENT_EVALUATIONS.md) for
scope, success criteria, and the separate development-call qualification plan.
