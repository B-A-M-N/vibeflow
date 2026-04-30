---
name: vibe-workflow-plan
description: "Run Phase 3 of VibeFlow: turn an approved runtime design into an evidence-grounded implementation plan with source research, file targets, contracts, tests, and validation gates."
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
- runtime patterns in `references/feasibility/runtime-pattern-catalog.md`

Also verify that `DESIGN.md` contains an architecture sanity check. The plan must preserve the approved selected/rejected runtime surfaces and must not reintroduce rejected middleware, tool, hook, agent/profile, config, event, session, or source-change approaches without recording a scoped design deviation.

Verify the design decision contract before planning:

- Each runtime requirement maps to at least one selected surface, or is explicitly prompt-only, non-runtime, or out-of-scope.
- Each selected surface has required capabilities, runtime contracts, implementation targets, and validation proof expectations.
- Each rejected or not-applicable surface has a rationale and does not create implementation work.
- The plan must not require every Mistral Vibe extension surface; it must require only surfaces selected by the approved design decision contract.
- The selected pattern is valid for Mistral Vibe: middleware is `before_turn` only, skills can constrain via `allowed_tools`, tools can use config/state/prompt/result-extra/profile-switch mechanisms, MCP and connectors are distinct, and reasoning-event designs verify backend support.

For every targeted component type, include contract verification:

- Skills: discovery path plus `name`, `description`, `allowed-tools`, and `user-invocable` frontmatter
- Tools: `BaseTool[TArgs, TRes, TConfig, TState]` with `ToolArgs`, `ToolResult`, and `BaseToolConfig`
- Middleware: `async before_turn(self, messages: MessageList) -> MiddlewareAction`
- MCP servers: `[[mcp_servers]]` with `name`, `command` or `url`, and transport type
- Workflow manifests: all executable sections required by `references/workflow-manifest-schema.json`

Use progressive disclosure. Start from `references/diagrams/diagram-index.json` and read only the reference/source files relevant to the approved surfaces. Do not dump all references into context.

Correct stale or unsupported assumptions before writing the implementation plan.

## Output

Update `PLAN.md` with:

- implementation phases
- target files
- contracts each file must obey
- canonical executable workflow manifest fields when generating `.vibe-workflow/workflow.yaml` or `.vibe-workflow/workflow.json`
- tooling contract requirements when generating runnable workflows
- validation scripts or commands
- evidence requirements
- failure modes
- rollback/rework notes
- acceptance criteria

Executable workflow manifests must follow `references/workflow-manifest-schema.json`: `phase.id`, `phase.entry`, `phase.exit`, `phase.retryLimit`, optional `phase.tools`, and top-level `tooling` with required tools, inputs, outputs, entrypoint, evidence output, and failure semantics. Do not generate `phase.name`, `phase.exit_criteria`, or `phase.retry_budget` as canonical fields.

Update `WORKFLOW_CONTRACT.json` with plan status, file targets, validation gates, and unresolved risks.

Do not edit implementation files in this phase.
