---
name: vibe-workflow:design
description: Map signed VibeFlow intent to real Mistral Vibe runtime topology with feasibility checks, plain-English components, diagrams, blunt design critique, and user approval gates.
---

Design the workflow described by `VISION.md`, `PLAN.md`, and `WORKFLOW_CONTRACT.json`.

This phase exists because the user may know what they want conceptually but not what Mistral Vibe can actually support or how the pieces should fit together.

## Inputs

Read:

- `VISION.md`
- `PLAN.md`
- `WORKFLOW_CONTRACT.json`
- `references/diagrams/diagram-index.json`

## Environment Preflight

Before marking runtime topology as grounded, verify what runtime evidence is actually available:

- target Mistral Vibe repo, source checkout, package, or version
- installed package versus local source path
- Claude plugin profile path and command/skill loader shape when relevant
- available source/docs/DeepWiki material for the runtime surfaces being claimed

If source or docs are unavailable, classify the design as assumption-based and list exactly what must be verified later. Do not present runtime topology as grounded unless it was checked against available source or authoritative docs.

Use references with progressive disclosure:

1. Read `references/diagrams/diagram-index.json` first.
2. Use the index to identify only the feasibility/runtime surfaces relevant to the proposed design.
3. Read the matching feasibility and diagram files only when needed to sanity-check a concrete design claim.
4. Do not load every reference file by default.
5. Do not tell the user to consult the references unless they ask; use them internally to ground the design.

Available feasibility substrate:

- Extension Point Taxonomy / Tiers A-E
- Key Interfaces & Contracts
- Runtime Pattern Catalog
- Workflow Pattern Library
- Event System Reference
- Configuration Keys for Workflow Control
- Tier Composition Patterns
- Diagnostic & Observability

If required context is missing, stop and tell the user to run `/vibe-workflow-init`.

## Design Loop

Start with:

```md
Based on what you told me, this is what I recommend.
```

Then show:

- each required component in plain English
- the runtime surface it maps to
- why that surface is appropriate
- the feasibility tier
- constraints and tradeoffs
- what can be done with config/skills/tools/middleware/source changes
- what cannot be done as stated

Reference citations are optional. Include them only when a claim is risky, surprising, disputed, or needed to explain a feasibility boundary.

Use simple text diagrams when useful. Keep diagrams explanatory, not decorative.

## Architecture Sanity Check

Before asking for user approval or generating `DESIGN.md` / `ARCHITECTURE.md`, perform a blocking architecture sanity check. VibeFlow should optimize for workflows with the highest likelihood of success, which means checking the whole runtime composition and not only the obvious component.

Use `references/feasibility/runtime-pattern-catalog.md` to select valid runtime patterns. Do not present the catalog as a list of things to include; use it to choose and justify the smallest correct surface composition.

Evaluate every applicable runtime surface:

- skills/prompts for guidance, sequencing, and workflow instructions
- config for enabling, disabling, routing, permissions, model/tool settings, and existing runtime controls
- tools/MCP for executable actions, structured capabilities, and external systems
- built-in workflow tools for structured user questions, plan-mode exit, todo tracking, subagent tasks, webfetch, and websearch
- middleware for pre-turn inspection, halt/continue actions, context injection, compaction, and guardrails
- agents/profiles where the runtime has a concrete agent/profile/tool mechanism; do not invent persona orchestration
- scratchpad for temporary artifacts
- AGENTS.md for persistent context injection
- programmatic mode for CI/CD and machine-readable validation output
- events/session/state for durable lifecycle state, audit trails, replay, diagnostics, and evidence
- hooks at verified lifecycle boundaries only
- source changes for AgentLoop, middleware timing, tool selection, permission semantics, event schema, persistence, or other runtime behavior changes

For each surface, classify it as `selected`, `rejected`, or `not_applicable`, and record:

- why it fits or does not fit
- what contract it must obey
- what failure mode it introduces
- what simpler alternative exists
- what evidence/source/docs ground the claim

Write this as a design decision contract in `WORKFLOW_CONTRACT.json`. The contract should preserve freedom of design while preventing oversight: selected surfaces require capability, rationale, runtime contract, implementation evidence target, and validation proof; rejected and not-applicable surfaces require rationale but no implementation.

Run these specific checks:

- Middleware placement: verify the behavior belongs before LLM turns; do not claim middleware can intercept during tool execution or after tool results unless source proves it.
- Middleware semantics: `before_turn(context)` fires before each LLM call; `INJECT_MESSAGE` composes; `STOP` and `COMPACT` short-circuit later middleware.
- Tool placement: use tools for executable capabilities, stateful session-local capability, `get_result_extra()` post-tool context, tool prompts, permission overrides, and tool-triggered profile switching; do not use tools for changing AgentLoop control policy.
- Built-in workflow tools: use `ask_user_question` for structured approval/intake/clarification, `exit_plan_mode` for plan-to-implementation, `todo` for session progress, `task` for read-only subagents, and `webfetch`/`websearch` for external research.
- Skill placement: skill `allowed_tools` is a real tool availability boundary; check it against required tools.
- Remote tool placement: distinguish MCP from Mistral Connectors.
- MCP placement: use `prompt` for usage hints and justify `sampling_enabled`.
- Agent placement: use agents/profiles only through supported runtime mechanisms, including tool-triggered profile switching via `switch_agent_callback` if applicable.
- Subagent placement: subagents return text; parent writes project files.
- Hook placement: `POST_AGENT_TURN` only, with exit code 2 for retry and `transcript_path` available for full-session review.
- Persistence placement: use AGENTS.md for stable injected context, todo for session state, scratchpad for temp artifacts, and files for durable audit/evidence.
- Programmatic placement: use `--output streaming` or `--output json` for CI/CD evidence.
- Reasoning visibility: do not depend on visible reasoning unless backend/model support for `ReasoningEvent` is verified.
- Composition: include every required surface for a cohesive workflow, but reject redundant surfaces when a smaller design satisfies the success criteria.
- Alternatives: if multiple surfaces could solve a requirement, compare them explicitly and pick one.

Include a short `Architecture Sanity Check` section in the recommendation before the approval question. If a required surface is unverified, classify the design as assumption-based and list verification tasks. Do not write design artifacts until the sanity check has no blocking gaps or the user explicitly approves the known assumptions.

## Blunt Feasibility Review

Give grounded opinions. Do not flatter bad architecture.

Call out:

- over-engineering
- underspecified behavior
- impossible runtime assumptions
- places where the user's idea is feasible only if implemented differently
- cheaper/smaller designs that satisfy the same goal
- cases where source modification is the honest answer

If the user proposes an alternative, reflect it honestly:

1. Is it feasible?
2. What tier does it require?
3. What would have to change?
4. Is there a simpler equivalent implementation?
5. Should the design be amended?

## Approval Gate

Do not advance until the user approves a design.

If approved, write:

- `DESIGN.md` - human-readable runtime topology, component explanation, architecture sanity check decisions, and selected/rejected surfaces
- `ARCHITECTURE.md` - diagrams, file/component map, middleware/hook/tool/agent boundaries, and data/control flow
- update `WORKFLOW_CONTRACT.json` with design status, selected feasibility tier, selected runtime surfaces, rejected alternatives, `design.requirements`, `design.surfaceDecisions`, and unresolved assumption-based checks

Then tell the user the next step is `/vibe-workflow-plan`.
