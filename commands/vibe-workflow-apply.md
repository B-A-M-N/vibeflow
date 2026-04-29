---
name: vibe-workflow:apply
description: Apply an approved VibeFlow plan by writing or patching files, preserving scope, and recording implementation evidence.
---

Implement the approved plan.

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

## Evidence

Record:

- files changed
- why each file changed
- commands run
- checks performed
- unresolved risks

After implementation, tell the user the next step is `/vibe-workflow-validate`.
