---
name: vibe-workflow:validate
description: Validate an implemented VibeFlow workflow with deterministic checks, evidence reports, and exact failure explanations.
---

Prove the implemented workflow works, or report exactly why it does not.

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
5. Execution/dry-run check: scripts or mock runs prove expected transitions.
6. Evidence check: commands, files, tests, and failures are recorded.

Use references on demand. Start from `references/diagrams/diagram-index.json` when checking runtime surfaces, then read only the specific feasibility/interface/event/config/session references needed to validate the implementation.

Use scripts in `scripts/` when applicable:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/workflow-linter.py" .vibe-workflow/workflow.yaml
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/dry-run-simulator.py" .vibe-workflow/workflow.yaml
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/evidence-reporter.py" .vibe-workflow/evidence/latest.json
```

## Report

Write a validation report with:

- overall verdict: `READY`, `NEEDS_REWORK`, or `FAILED`
- checks run
- evidence found
- failures and exact causes
- whether the implementation still matches approved intent/design
- recommended rework if needed

Do not hand-wave validation. If proof is incomplete, say what proof is missing.
