---
name: vibe-workflow-apply
description: "Run Phase 4 of VibeFlow: implement the approved plan by writing or patching scoped files and recording implementation evidence."
version: 2.0.0
---

You are running the `apply` phase of VibeFlow.

Read the approved `PLAN.md`, `DESIGN.md`, `ARCHITECTURE.md`, and `WORKFLOW_CONTRACT.json`.

## Rules

- Edit only the files named in the approved plan unless a scoped deviation is necessary.
- Explain and record any deviation before continuing.
- Preserve the approved feasibility tier and runtime surfaces.
- Keep implementation as small as the design allows.
- Do not introduce subagent orchestration or persona systems unless explicitly approved as part of real Mistral Vibe agent profile behavior.

## Evidence

Record:

- files changed
- commands run
- tests/checks run
- failures found
- unresolved risks

After implementation, hand off to `vibe-workflow:validate`.
