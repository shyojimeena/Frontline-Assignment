# Voice agent evaluations

Offline checks for negotiation price integrity and the tool gates that already exist. No API keys are read. Nothing is dialed and nothing is written to Supabase.

## Run

From `voice-agent/`, with the voice-agent dependencies installed (Python 3.11 and `pip install -r requirements.txt`):

```bash
python -m evals
```

Exit code 0 means the regression checks passed. The command still prints findings. Exit code 1 means a regression or the scorer self-check failed.

The scorecard is written to `evals/results/scorecard.txt` and `evals/results/scorecard.json`.

## How to read the result

- **Passed check.** The handler or the scripted compliant reply behaved as the current product requires.
- **Finding.** Current behavior the suite is meant to show. A finding does not fail the run. On this code, a scripted `record_agreement` above the ceiling is accepted, and load special instructions are copied into the system prompt.
- **Failure.** A gate the code already enforces has stopped working, or a compliant script leaked the goal or the ceiling.

Probe scenarios use a scripted assistant. They do not call gpt-4.1. A finding that the tool accepted $4,500 does not prove the live model would ask for that. It proves the tool would book it.

## What is mocked

- Carrier lookup returns one fixed carrier.
- The load is an in-memory legacy row: opening $2,000, goal $2,500, ceiling $2,800.
- Negotiation insert, call-record updates, and quote notification are recorded in memory.

## What a green run does not prove

Live model compliance, phone audio, a transfer after the load is confirmed, or delivery of a quote to the carrier quote API.

## Adding a case

A new conversation is a JSON file in `voice-agent/evals/cases/`. Set `include` to `verified_load` when the case starts after the carrier and the load are already on the call. Each expectation names a check from `evals/checks.py`.

- `on_violation: "fail"` means the run exits 1 if the check does not hold.
- `on_violation: "finding"` means a miss is reported and the run still exits 0. Change it to `fail` when that behavior should start blocking merges.

A new tool is a function added to `TOOLS` in `evals/handlers.py`. A new check is a function added to `CHECKS` in `evals/checks.py`. Neither requires a change to the runner.

