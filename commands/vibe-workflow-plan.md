---
name: vibe-workflow:plan
description: Convert an approved VibeFlow design into an implementation plan with research notes, file targets, contracts, tests, and validation gates.
---

Plan implementation from the approved design.

## Inputs

Read:

- `VISION.md`
- `PLAN.md`
- `WORKFLOW_CONTRACT.json`
- `DESIGN.md`
- `ARCHITECTURE.md`
- `references/diagrams/diagram-index.json`
- relevant DeepWiki captures or source files when available

Use feasibility references with progressive disclosure. Load only the specific feasibility docs, diagram docs, DeepWiki captures, or source files needed for the approved runtime surfaces and file targets.

If the design artifacts are missing or unapproved, stop and tell the user to run `/vibe-workflow-design`.

## Research Pass

Ground the plan in evidence:

- inspect relevant Mistral Vibe source files
- consult DeepWiki/source captures when present
- verify real class names, config keys, event types, middleware actions, tool contracts, and session/logging behavior
- correct stale assumptions before planning

## Output

Update `PLAN.md` into an implementation plan containing:

- target files to create or patch
- exact runtime surfaces involved
- source contracts each change must obey
- executable workflow manifest target, if needed, using `references/workflow-manifest-schema.json`
- tooling contract requirements: required tools, inputs, outputs, entrypoint, evidence output, and failure semantics
- validation commands/checkers
- failure modes to watch for
- rollback/rework strategy
- acceptance criteria

If generating `.vibe-workflow/workflow.yaml` or `.vibe-workflow/workflow.json`, use the canonical executable workflow manifest schema:

- `phase.id`
- `phase.entry`
- `phase.exit`
- `phase.retryLimit`
- `phase.tools`
- top-level `tooling.requiredTools`
- top-level `tooling.entrypoint`
- top-level `tooling.inputs`
- top-level `tooling.outputs`
- top-level `tooling.evidenceOutput`
- top-level `tooling.failureSemantics`

Do not emit `phase.name`, `phase.exit_criteria`, or `phase.retry_budget` unless explicitly documenting legacy input that the tooling will normalize.

Update `WORKFLOW_CONTRACT.json` with plan status, file targets, and validation gates.

Do not apply code changes in this phase. Tell the user the next step is `/vibe-workflow-apply`.
