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
- verify runtime pattern fit using `references/feasibility/runtime-pattern-catalog.md`
- verify native workflow tool fit: `ask_user_question`, `exit_plan_mode`, `todo`, `task`, scratchpad, `webfetch`, `websearch`, AGENTS.md, hooks, and programmatic output
- verify that `DESIGN.md` includes the Architecture Sanity Check decisions for selected, rejected, and assumption-based runtime surfaces
- verify that `WORKFLOW_CONTRACT.json` includes a design decision contract: runtime requirements map to selected surfaces, selected surfaces include capability/contract/proof expectations, and rejected surfaces have rationale
- verify that selected patterns are source-grounded: middleware uses `before_turn`, skill enforcement claims use `allowed_tools` or another runtime control, tool permission needs consider BaseToolConfig/resolve_permission, MCP and connectors are not conflated, and reasoning-event requirements verify backend/model support
- verify that hooks are `POST_AGENT_TURN` only, subagents do not own file writes, MCP `sampling_enabled` is justified, and CI-style validation uses machine-readable output
- preserve the approved component placement for skills/prompts, config, tools/MCP, middleware, agents/profiles, events/session/state, hooks, and source changes
- correct stale assumptions before planning

Do not reintroduce a rejected middleware, tool, hook, agent/profile, config, event, session, or source-change approach unless you record it as a scoped design deviation and explain why the approved design no longer works.

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
