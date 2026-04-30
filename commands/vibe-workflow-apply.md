---
name: vibe-workflow:apply
description: Apply an approved VibeFlow plan by writing or patching files, preserving scope, and recording implementation evidence.
---

Implement the approved plan and make the generated workflow runnable.

## Inputs

Read:

- `PLAN.md`
- `WORKFLOW_CONTRACT.json`
- `DESIGN.md`
- `ARCHITECTURE.md`

If the plan is missing or unapproved, stop and tell the user to run `/vibe-workflow-plan`.

## Apply Rules

- Modify only files named by the approved plan unless a blocker requires a scoped deviation.
- If a deviation is required, explain it before editing and record it in `PLAN.md`.
- Preserve the agreed feasibility tier. Do not silently turn a skill/config design into source modification.
- Keep implementation minimal enough to satisfy the signed design.
- Do not introduce multi-agent orchestration unless the approved design explicitly requires Mistral Vibe agent profile behavior.
- Do not stop at artifact writing. The result must be a complete working workflow with a runnable manifest and compatible tooling.

## Tooling Generation Or Repair

Generate or repair the workflow tooling surface when missing, inconsistent, or broken:

- `.vibe-workflow/workflow.yaml` or `.vibe-workflow/workflow.json` using `references/workflow-manifest-schema.json`
- one canonical schema only; do not mix `phase.name`/`phase.exit_criteria`/`phase.retry_budget` with `phase.id`/`phase.exit`/`phase.retryLimit`
- top-level `tooling` contract with required tools, expected inputs, expected outputs, execution entrypoint, evidence output location, and failure semantics
- required scripts, config, hooks, or adapters named by the approved plan
- compatibility between the generated workflow and every generated or required tool

Before handing off, run or prepare the deterministic commands that `validate` will execute:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validation-runner.py" .vibe-workflow/workflow.yaml
```

If any command cannot run yet, fix the tooling contract or generated files during apply. Only defer when the blocker is external and record the exact missing dependency.

Apply is not complete unless the generated manifest can be parsed by `workflow_manifest.py` and `workflow-linter.py` succeeds. If full validation is not possible during apply, mark the phase as implementation attempted rather than complete.

## Evidence

Record:

- files changed
- why each file changed
- commands run
- checks performed
- unresolved risks

After implementation, tell the user the next step is `/vibe-workflow-validate`.
