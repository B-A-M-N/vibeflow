---
name: vibe-workflow-validate
description: "Run Phase 5 of VibeFlow: prove the implemented workflow works through deterministic checks and evidence, or report exactly why it does not."
version: 2.0.0
allowed-tools:
  - ReadFile
  - WriteFile
  - EditFile
  - Bash
  - Grep
  - Glob
user-invocable: true
---

You are running the `validate` phase of VibeFlow.

## Validation Stance

Validation must be evidence-bearing. If proof is incomplete, say exactly what is missing.

Validation is also an integration check. A workflow is not complete unless its generated manifest can be consumed by the required or generated tools and produce runnable evidence.

## Checks

Perform deterministic checks wherever possible:

- artifact agreement
- feasibility tier still matches implementation
- interface/contract compliance
- topology and convergence
- tooling contract completeness
- dry-run or sandbox behavior
- evidence report completeness
- tests or command output

Use `references/diagrams/diagram-index.json` as the lookup entry point, then load only the specific feasibility/runtime references needed for the implementation being validated.

Use scripts in `scripts/` when applicable:

- `validation-runner.py`
- `workflow-linter.py`
- `dry-run-simulator.py`
- `gate-engine.py`
- `state-invariant-checker.py`
- `design-contract-linter.py`
- `pattern-fit-linter.py`
- `drift-detector.py`
- `evidence-reporter.py`
- `failure-classifier.py`

All tools must consume the same executable workflow manifest schema from `references/workflow-manifest-schema.json`. YAML and JSON are both valid inputs. If tools report legacy alias normalization, treat that as a generator contract defect to fix.

Run validation serially and aggregate failures. Do not cancel later checks because an earlier check failed. Evidence must be written even on failure with `validation_started`, checks run, checks failed, blocking reason, failure domain, and safe next action.

Require this pass chain before reporting `READY`:

1. `validation-runner.py` runs the serial check chain.
2. `workflow-linter.py` validates `.vibe-workflow/workflow.yaml`.
3. `dry-run-simulator.py` parses and executes that same manifest.
4. `state-invariant-checker.py` verifies `currentPhase`, `retryCounts`, `evidence`, and `gateDecisions`.
5. `design-contract-linter.py` verifies requirement-to-surface traceability and selected surface proof without requiring rejected/not-applicable surfaces to be implemented.
6. `pattern-fit-linter.py` checks selected runtime patterns for known-invalid or risky combinations.
7. `drift-detector.py` compares manifest execution against the approved `WORKFLOW_CONTRACT.json` surfaces/components when present.
8. `convergence-scorer.py` scores retry and exit behavior from the actual dry-run trace.
9. Evidence is written to `.vibe-workflow/evidence/latest.json` or the manifest's declared evidence output.
10. `evidence-reporter.py` generates the report from that actual evidence.
11. No parser/schema mismatch appears between generated workflow and required tools.

Classify failures as `plugin_tooling`, `generated_workflow`, `user_spec`, `environment`, or `external_dependency`. Parser/schema incompatibility should direct repair toward the harness or generated artifact before any redesign.

## Report

Produce a validation report with:

- verdict: `READY`, `NEEDS_REWORK`, or `FAILED`
- checks run
- evidence collected
- exact failures
- whether the implementation still matches approved intent and design
- recommended rework
