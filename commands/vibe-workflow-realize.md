---
name: vibe-workflow:realize
description: Realize a conceptual workflow, partial implementation, skillset, or design document into a working, runtime-grounded Mistral Vibe implementation.
---

Convert existing conceptual work into a working implementation.

## Inputs

Inspect the current repo and any artifacts the user points to:

- Existing skills, commands, hooks, tools, config files
- Design documents, READMEs, conceptual descriptions
- Partial implementations
- `VISION.md`, `PLAN.md`, `WORKFLOW_CONTRACT.json` if present

## Rules

- Do not start from blank intake. Start from what exists.
- Classify every conceptual claim against real Mistral Vibe runtime surfaces before writing any implementation.
- Do not implement a surface that cannot be grounded in `references/feasibility/`.
- Emit `REALIZATION_CONTRACT.json` before any implementation work begins.
- Preserve the stated intent of existing artifacts; do not silently reinterpret them.
- Record every surface that cannot be implemented as stated and explain why.

After realization, hand off to `/vibe-workflow-validate`.
