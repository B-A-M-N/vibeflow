---
name: vibe-workflow-apply
description: "Run Phase 4 of VibeFlow: implement the approved plan, generate or repair required workflow tooling, and record implementation evidence."
version: 2.0.0
---

You are running the `apply` phase of VibeFlow. Apply must produce a complete working workflow, not just plausible documents.

Read the approved `PLAN.md`, `DESIGN.md`, `ARCHITECTURE.md`, and `WORKFLOW_CONTRACT.json`.

## Rules

- Edit only the files named in the approved plan unless a scoped deviation is necessary.
- Explain and record any deviation before continuing.
- Preserve the approved feasibility tier and runtime surfaces.
- Keep implementation as small as the design allows.
- Do not introduce subagent orchestration or persona systems unless explicitly approved as part of real Mistral Vibe agent profile behavior.
- Generate or repair `.vibe-workflow/workflow.yaml` or `.vibe-workflow/workflow.json` so it follows `references/workflow-manifest-schema.json`.
- Include a top-level tooling contract: required tools, inputs, outputs, execution entrypoint, evidence output, and failure semantics.
- Ensure the generated workflow can be consumed by its generated or required tools with no parser/schema mismatch.
- If validation tooling would fail because the workflow/tooling contract is incomplete, fix that during apply.
- Apply is not complete unless the generated manifest parses through `workflow_manifest.py` and passes `workflow-linter.py`. If full validation cannot run, mark implementation attempted, not complete.

## Evidence

Record:

- files changed
- commands run
- tests/checks run
- failures found
- unresolved risks

After implementation, hand off to `vibe-workflow:validate`.
