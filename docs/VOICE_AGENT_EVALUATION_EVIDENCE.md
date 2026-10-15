# Voice-agent evaluation evidence

Run date: 2026-10-15 (offline, synthetic fixtures only)

Command:

```bash
python3 voice-agent/evaluations/run_evaluations.py
```

Result:

```text
PASS prompt_contracts: expected=[] actual=[]
PASS happy_path_verified_load_agreement: expected=[] actual=[]
PASS negative_control_transfer_before_verification: expected=['transfer_without_prerequisites'] actual=['transfer_without_prerequisites']
PASS negative_control_confidentiality_and_ordering: expected=['confidentiality_leak', 'load_before_identity', 'missing_holding_phrase'] actual=['confidentiality_leak', 'missing_holding_phrase', 'load_before_identity']
PASS negative_control_unrecorded_agreement: expected=['agreement_not_recorded'] actual=['agreement_not_recorded']
PASS real_handler_rejects_implausible_load_id: expected=[] actual=[]
PASS real_handler_rejects_above_max_without_contact: expected=[] actual=[]
PASS finding_normal_above_max_is_accepted: expected=['over_max_normal_agreement_accepted', 'quote_notified'] actual=['over_max_normal_agreement_accepted', 'quote_notified']
PASS finding_untrusted_special_instructions_are_interpolated: expected=['untrusted_special_instructions_in_system_prompt'] actual=['untrusted_special_instructions_in_system_prompt']

9/9 evaluation cases passed
```

The negative-control and documented implementation findings are expected;
their successful detection calibrates the evaluator. This is evidence for
deterministic prompt, trace, and isolated-handler behavior only—not for live
speech, provider integrations, or real LLM behavior.
