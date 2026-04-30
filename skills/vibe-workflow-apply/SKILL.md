---
name: vibe-workflow-apply
description: "Run Phase 4 of VibeFlow: implement the approved plan, generate or repair required workflow tooling, and record implementation evidence."
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

You are running the `apply` phase of VibeFlow. Apply must produce a complete working workflow, not just plausible documents.

Read the approved `PLAN.md`, `DESIGN.md`, `ARCHITECTURE.md`, and `WORKFLOW_CONTRACT.json`.

## Rules

- Edit only the files named in the approved plan unless a scoped deviation is necessary.
- Explain and record any deviation before continuing.
- Preserve the approved feasibility tier and runtime surfaces.
- Preserve the approved design decision contract. A selected surface must receive implementation evidence during apply; a rejected or not-applicable surface must not be implemented unless you record a scoped design deviation first.
- Keep implementation as small as the design allows.
- Do not introduce subagent orchestration or persona systems unless explicitly approved as part of real Mistral Vibe agent profile behavior.
- Generate or repair `.vibe-workflow/workflow.yaml` or `.vibe-workflow/workflow.json` so it follows `references/workflow-manifest-schema.json`.
- Include a top-level tooling contract: required tools, inputs, outputs, execution entrypoint, evidence output, and failure semantics.
- Include all executable contract sections: `name`, `goal`, `phases`, `tooling`, `state`, `middleware`, `approval_gates`, `evidence`, `failure_policy`, `commands`, and `validation`.
- Verify component-level compliance before reporting complete:
  - Generated skills use a discoverable path and frontmatter with `name`, `description`, `allowed-tools`, and `user-invocable`.
  - Generated tool classes inherit `BaseTool` with `ToolArgs`, `ToolResult`, `BaseToolConfig`, and state typing.
  - Generated middleware implements `async before_turn(self, context: ConversationContext) -> MiddlewareResult` and `reset(self, reset_reason: ResetReason = ResetReason.STOP) -> None`, returns `MiddlewareResult()` as the CONTINUE fallback, and does not claim pre-tool/post-tool hooks.
  - MCP server entries use `[[mcp_servers]]` with `name`, `command` or `url`, and transport type.
  - Plans and applied artifacts preserve selected runtime surfaces from `WORKFLOW_CONTRACT.json`; run drift detection when a manifest/evidence pair exists.
- Set validation to serial, evidence-bearing, and non-mutating: `serial: true`, `evidenceRequired: true`, `mutatesWorkflow: false`.
- Ensure the generated workflow can be consumed by its generated or required tools with no parser/schema mismatch.
- If validation tooling would fail because the workflow/tooling contract is incomplete, fix that during apply.
- Apply is not complete unless the generated manifest parses through `workflow_manifest.py` and passes `workflow-linter.py`. If full validation cannot run, mark implementation attempted, not complete.
- Apply is not complete unless `design-contract-linter.py` passes or reports only that `WORKFLOW_CONTRACT.json` is unavailable for a standalone manifest check.

## Evidence

Record:

- files changed
- commands run
- tests/checks run
- failures found
- unresolved risks

After implementation, hand off to `vibe-workflow:validate`.
