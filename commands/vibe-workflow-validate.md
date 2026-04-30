---
name: vibe-workflow:validate
description: Validate an implemented VibeFlow workflow with deterministic checks, evidence reports, and exact failure explanations.
---

Prove the implemented workflow works, or report exactly why it does not.

Validation is a runnable integration check. Do not treat design artifacts as complete unless the generated workflow can be consumed by its required tooling without parser or schema mismatch.

## Inputs

Read:

- `VISION.md`
- `PLAN.md`
- `WORKFLOW_CONTRACT.json`
- `DESIGN.md`
- `ARCHITECTURE.md`
- implementation evidence from `/vibe-workflow-apply`

## Validation Stages

Run deterministic checks wherever possible:

1. Static artifact check: required artifacts exist and agree.
2. Feasibility check: selected runtime surfaces match the implementation.
3. Contract check: tools, middleware, config, events, sessions, and source changes obey known interfaces.
4. Topology check: phases have entry/exit criteria and bounded convergence.
5. Tooling contract check: required tools, expected inputs, expected outputs, execution entrypoint, evidence output location, and failure semantics are present.
6. Execution/dry-run check: `dry-run-simulator.py` parses and executes generated `workflow.yaml`.
7. State invariant check: `currentPhase`, `retryCounts`, `evidence`, and `gateDecisions` survive the dry run.
8. Design decision contract check: selected surfaces have proof, rejected/not-applicable surfaces are not required, and runtime requirements trace to selected surfaces.
9. Drift check: manifest execution still matches approved `WORKFLOW_CONTRACT.json` runtime surfaces/components when present.
10. Evidence check: simulator writes `.vibe-workflow/evidence/latest.json` or the manifest's declared evidence output.
11. Report check: validation report is generated from actual runnable evidence.

Use references on demand. Start from `references/diagrams/diagram-index.json` when checking runtime surfaces, then read only the specific feasibility/interface/event/config/session references needed to validate the implementation.

Use the serial validation runner by default:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validation-runner.py" .vibe-workflow/workflow.yaml
```

The runner must execute checks serially, capture every result, and aggregate failures. Do not cancel later checks just because an earlier check failed. The runner must always write `.vibe-workflow/evidence/latest.json` or the manifest's declared evidence output, even for failed validation.

Individual scripts remain available for targeted debugging:

- `workflow-linter.py`
- `dry-run-simulator.py`
- `gate-engine.py`
- `state-invariant-checker.py`
- `design-contract-linter.py`
- `pattern-fit-linter.py`
- `drift-detector.py`
- `convergence-scorer.py`
- `evidence-reporter.py`
- `failure-classifier.py`

All validation tools consume the same canonical executable workflow manifest schema in `references/workflow-manifest-schema.json`. YAML and JSON are both allowed. Legacy aliases are normalized with warnings:

- `phase.name` -> `phase.id`
- `phase.exit_criteria` -> `phase.exit`
- `phase.retry_budget` -> `phase.retryLimit`

Treat normalization warnings as rework signals for generated artifacts.

## Completion Definition

A workflow is not complete unless all of these pass:

- required artifacts exist
- canonical workflow schema validates
- tooling contract validates
- dry-run executes against the generated workflow manifest
- evidence is produced at the declared evidence output
- validation report verdict is `READY`

If any item fails, return `NEEDS_REWORK` or `FAILED`; do not call the workflow complete.

## Failure Domain

Classify every failure before recommending action:

```json
{
  "failure_domain": "plugin_tooling | generated_workflow | user_spec | environment | external_dependency",
  "is_design_flaw": false,
  "is_validation_harness_bug": false,
  "safe_next_action": "repair generated manifest/tooling contract"
}
```

Parser/schema incompatibility is a plugin tooling or generated artifact problem, not permission to redesign the user's workflow.

## Report

Write a validation report with:

- overall verdict: `READY`, `NEEDS_REWORK`, or `FAILED`
- checks run
- evidence found
- failures and exact causes
- whether the implementation still matches approved intent/design
- recommended rework if needed

Do not hand-wave validation. If proof is incomplete, say what proof is missing.
