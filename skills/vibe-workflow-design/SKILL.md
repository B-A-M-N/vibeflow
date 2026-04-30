---
name: vibe-workflow-design
description: "Run Phase 2 of VibeFlow: map approved intent onto real Mistral Vibe runtime topology with feasibility checks, component explanations, plain-English diagrams, blunt critique, and user approval."
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

You are running the `design` phase of VibeFlow.

Your job is to help the user understand what is possible, what is not possible, and what architecture is most grounded for the workflow they signed off during init.

## Inputs

Read `VISION.md`, `PLAN.md`, and `WORKFLOW_CONTRACT.json`.

Run environment preflight before claiming a grounded runtime topology:

- detect target repo/path/version
- distinguish installed package from source checkout
- detect plugin profile path and command/skill loader shape where relevant
- identify whether source/docs were actually available

If source/docs are unavailable, label the design assumption-based and record verification tasks for plan/validate.

Then use the feasibility substrate with progressive disclosure. Start with `references/diagrams/diagram-index.json`, identify relevant runtime surfaces, and read only the matching reference files needed to sanity-check the current design.

Do not load every reference file by default. Do not make consulting references part of the user-facing workflow. Use the references internally when they help verify a concrete design claim.

Available feasibility substrate:

- Extension Point Taxonomy
- Key Interfaces & Contracts
- Runtime Pattern Catalog
- Workflow Pattern Library
- Event System Reference
- Configuration Keys for Workflow Control
- Tier Composition Patterns
- Diagnostic & Observability

Reference citations are optional. Include them only when a feasibility claim is risky, surprising, disputed, or helpful for explaining why something is or is not possible.

If init artifacts are missing or unapproved, stop and tell the user to run `vibe-workflow:init`.

## Design Behavior

Open with a recommendation:

```md
Based on what you told me, this is what I would recommend.
```

Then explain:

- components in plain English
- which Mistral Vibe runtime surface each component uses
- why that surface fits
- feasibility tier
- required contracts
- tradeoffs
- likely failure modes
- what needs source modification, if anything

Use simple diagrams when they make the design easier to understand.

## Architecture Sanity Check

Before asking for approval or writing design artifacts, run a blocking sanity check over the proposed architecture. The purpose is to maximize workflow success by choosing the right runtime surfaces, not just the first plausible implementation.

Use `references/feasibility/runtime-pattern-catalog.md` to choose valid patterns and reject invalid ones. The catalog is a selector and anti-pattern guard, not a requirement to include every surface.

Create an internal component matrix with one row per applicable surface:

- skills/prompts: when the behavior is guidance, sequencing, or user-facing workflow instructions
- config: when existing runtime behavior only needs to be enabled, disabled, routed, or constrained
- tools/MCP: when the workflow needs a new executable action, external system call, or structured capability
- middleware: when behavior must inspect, halt, compact, or inject context before LLM turns
- agents/profiles: when the runtime supports delegated behavior through a real profile/agent/tool surface, not invented persona orchestration
- events/session/state: when the workflow needs durable trace, replay, audit, or lifecycle state
- hooks: when behavior belongs at a supported lifecycle boundary; do not use hooks as a substitute for core workflow logic unless the runtime actually calls them there
- source changes: when the desired behavior changes AgentLoop, tool selection, middleware timing, event schema, persistence, or permission semantics

For each applicable surface, decide:

- selected, rejected, or not applicable
- why it does or does not fit this workflow
- what contract it must obey
- what failure mode it introduces
- what simpler alternative could satisfy the same requirement
- what evidence/source/docs ground the claim

Record these decisions as a design decision contract in `WORKFLOW_CONTRACT.json`. This contract preserves creative freedom: it does not prescribe the exact component shape, but every selected surface must name the capability it provides, why it is necessary, the runtime contract it obeys, planned implementation evidence, and validation proof. Rejected or not-applicable surfaces need rationale and when to reconsider, not implementation.

Specific checks:

- Middleware only has `before_turn(context)` active behavior plus reset. It fires before each LLM call in the multi-step loop. Do not use middleware for behavior that must happen during tool execution, after tool results, or on arbitrary events.
- Treat `MiddlewareAction.COMPACT` as a distinct action and account for pipeline short-circuiting: `INJECT_MESSAGE` results compose, while `STOP` and `COMPACT` stop later middleware.
- If a design proposes a skill, verify discoverability: it must live in `.vibe/skills/`, `~/.config/vibe/skills/`, or a project `skills/` directory, and its frontmatter must include `name`, `description`, `allowed-tools`, and `user-invocable`.
- If a design uses skill `allowed-tools` / `allowed_tools`, verify it does not conflict with required tools.
- Do not use a tool when the requirement is to change how tools are selected, authorized, sequenced, or interpreted by AgentLoop.
- Prefer tool-level mechanisms where they fit: `BaseToolConfig` permission/allowlist/denylist/sensitive_patterns, `resolve_permission()`, `get_result_extra()`, `BaseToolState`, `get_tool_prompt()` / `prompt_path`, and `switch_agent_callback`.
- Do not model agents as autonomous collaborators unless the runtime has a concrete agent/profile/tool mechanism that supports that role.
- Treat Mistral Connectors as a distinct remote tool surface from MCP; do not collapse connector semantics into MCP config.
- Do not depend on visible reasoning traces unless the selected backend/model emits `ReasoningEvent`.
- Do not use hooks for control flow unless their invocation point is verified.
- Prefer the smallest runtime surface that satisfies the success criteria, but include every required surface when the workflow genuinely needs a cohesive multi-surface design.
- If two surfaces could solve the same problem, compare them explicitly and choose one with rationale.

The recommendation must include a short "Architecture Sanity Check" section before the approval question. If a surface is applicable but rejected, include the reason. If a surface is required but unverified, mark the design assumption-based and add verification tasks for plan/validate. Do not write `DESIGN.md` or `ARCHITECTURE.md` until this sanity check has no blocking gaps or the user explicitly approves the known assumptions.

## Blunt Critique

Do not oversimplify and do not over-engineer.

If a proposed design uses excessive agents, phases, tools, middleware, or source patches for a simple outcome, say that it is over-engineered and propose the smaller design. If the user asks for something impossible, say it is not feasible and explain the runtime boundary. If the idea is feasible but should be implemented differently, offer the amended workflow freely.

## User Revision Loop

If the user rejects the recommendation or proposes an alternative:

1. Restate their alternative.
2. Classify feasibility.
3. Explain how it would actually work.
4. Identify impossible or expensive parts.
5. Offer a corrected version if one exists.
6. Ask whether to adopt the amended design.

Do not advance until the user approves a design.

## Outputs

After approval:

- write `DESIGN.md`, including the architecture sanity check decisions and selected/rejected runtime surfaces
- write `ARCHITECTURE.md`, including component placement, middleware/hook/tool/agent boundaries, and data/control flow
- update `WORKFLOW_CONTRACT.json` with design status, selected runtime surfaces, feasibility tier, approved components, `design.requirements`, and `design.surfaceDecisions`

Then hand off to `vibe-workflow:plan`.
