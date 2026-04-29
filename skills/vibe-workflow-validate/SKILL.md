---
name: vibe-workflow-validate
description: "Run Phase 5 of VibeFlow: prove the implemented workflow works through deterministic checks and evidence, or report exactly why it does not."
version: 2.0.0
---

You are running the `validate` phase of VibeFlow.

## Validation Stance

Validation must be evidence-bearing. If proof is incomplete, say exactly what is missing.

## Checks

Perform deterministic checks wherever possible:

- artifact agreement
- feasibility tier still matches implementation
- interface/contract compliance
- topology and convergence
- dry-run or sandbox behavior
- evidence report completeness
- tests or command output

Use `references/diagrams/diagram-index.json` as the lookup entry point, then load only the specific feasibility/runtime references needed for the implementation being validated.

Use scripts in `scripts/` when applicable:

- `workflow-linter.py`
- `dry-run-simulator.py`
- `gate-engine.py`
- `state-invariant-checker.py`
- `evidence-reporter.py`
- `failure-classifier.py`

## Report

Produce a validation report with:

- verdict: `READY`, `NEEDS_REWORK`, or `FAILED`
- checks run
- evidence collected
- exact failures
- whether the implementation still matches approved intent and design
- recommended rework
