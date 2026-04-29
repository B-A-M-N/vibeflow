---
name: vibe-workflow-plan
description: "Run Phase 3 of VibeFlow: turn an approved runtime design into an evidence-grounded implementation plan with source research, file targets, contracts, tests, and validation gates."
version: 2.0.0
---

You are running the `plan` phase of VibeFlow.

## Inputs

Require:

- `VISION.md`
- `PLAN.md`
- `WORKFLOW_CONTRACT.json`
- `DESIGN.md`
- `ARCHITECTURE.md`

If design artifacts are missing or unapproved, stop and tell the user to run `vibe-workflow:design`.

## Research Requirement

Before planning edits, verify the approved design against available DeepWiki captures and Mistral Vibe source code. Check real names and contracts for:

- AgentLoop behavior
- middleware execution points and `MiddlewareAction`
- tools and `BaseTool` / `InvokeContext`
- event types and handlers
- skill discovery and activation
- session logging and persistence
- config keys
- backend boundaries

Use progressive disclosure. Start from `references/diagrams/diagram-index.json` and read only the reference/source files relevant to the approved surfaces. Do not dump all references into context.

Correct stale or unsupported assumptions before writing the implementation plan.

## Output

Update `PLAN.md` with:

- implementation phases
- target files
- contracts each file must obey
- validation scripts or commands
- evidence requirements
- failure modes
- rollback/rework notes
- acceptance criteria

Update `WORKFLOW_CONTRACT.json` with plan status, file targets, validation gates, and unresolved risks.

Do not edit implementation files in this phase.
