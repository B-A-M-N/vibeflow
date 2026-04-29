# Workflow Pattern Library

Common workflow patterns mapped to Mistral Vibe runtime surfaces, feasibility tiers, and constraints.

## Pattern: Skill-Guided Workflow

**Use when:** The desired behavior can be achieved by better instructions, command modes, or reusable knowledge.

- Runtime surface: skills + config
- Tier: A
- Constraints: cannot change AgentLoop, middleware timing, tool permissions, event schema, or persistence model
- Proof: skill loads correctly, instructions are followed, no source changes needed

## Pattern: External Service Tool

**Use when:** The workflow needs a new action such as Jira, GitHub, database, or internal API access.

- Runtime surface: tool or MCP server
- Tier: B
- Constraints: tool runs only when selected by the model/tool system; it does not intercept message flow
- Proof: tool contract validates args/results, permissions are correct, failure modes are reported

## Pattern: Phase/Policy Guard

**Use when:** The workflow needs to inject phase context, stop unsafe continuation, or enforce turn-level policy before LLM calls.

- Runtime surface: middleware
- Tier: C
- Constraints: middleware runs before LLM turns, not during tool execution or after tool results
- Proof: middleware returns correct `MiddlewareAction`, including `COMPACT` handling

## Pattern: Event-Aware UX or Telemetry

**Use when:** The workflow needs custom visibility, streaming display, or observability.

- Runtime surface: event system + handlers + diagnostics
- Tier: C or D
- Constraints: new event types require updates to consumers such as TUI/ACP handlers
- Proof: emitted events are consumed without breaking existing UI/server paths

## Pattern: Session-Backed Continuity

**Use when:** The workflow needs persistence across turns or sessions.

- Runtime surface: SessionLogger / SessionLoader / session metadata
- Tier: A, C, or D depending on whether existing session behavior is enough
- Constraints: do not claim memory across sessions unless it is stored and loaded through real persistence
- Proof: session data is written, loaded, and used in a later run

## Pattern: Source-Level Runtime Change

**Use when:** The desired workflow changes how AgentLoop, tools, middleware, events, config, or sessions fundamentally behave.

- Runtime surface: `vibe/core/*`
- Tier: D
- Constraints: source patches must be maintained across Mistral Vibe updates and compatible with TUI/ACP
- Proof: source-level tests or targeted runtime checks cover the changed behavior

## Pattern: Impossible Assumption

**Use when:** The request contradicts runtime mechanics or lacks any implementable signal.

- Runtime surface: none
- Tier: E
- Constraints: do not fake feasibility
- Proof: cite the specific missing runtime mechanism and offer the nearest workable alternative

## Design Review Questions

- Is this really a source change, or can a skill/tool/middleware satisfy it?
- Is middleware being used for something that actually happens during tool execution?
- Is a new tool enough, or is the user asking to change when tools are selected?
- Does the workflow need new events, and if so, who consumes them?
- Does persistence use real session/config/state surfaces?
- Is the proposed component count proportionate to the problem?
