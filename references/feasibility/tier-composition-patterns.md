# Tier Composition Patterns

Many real workflows combine tiers. Classify the whole design by the highest required tier, but explain each component separately.

## A + B: Skill Uses Custom Tool

- Skill describes when/how to use a custom tool.
- Tool implements the external action.
- Overall tier: B.
- Common mistake: pretending tool behavior can control the agent loop.

## A + C: Skill With Middleware Guard

- Skill provides workflow instructions.
- Middleware injects phase state or blocks unsafe continuation before LLM turns.
- Overall tier: C.
- Common mistake: expecting middleware to run after tool execution.
- Common mistake: assuming `before_turn()` fires once per user message. It fires before **every LLM call** in the tool loop — including after tool results when the loop continues. On a multi-tool turn, a skill + middleware design will see `before_turn()` called once per tool batch plus once for the final response. Execution order per user message: reset hook retries → loop: `before_turn()` → LLM call + tools → (if hook retries: inject message, loop again with another `before_turn()`).

## B + C: Tool With Turn-Level Policy

- Tool performs custom action.
- Middleware controls whether the next LLM turn should continue, stop, compact, or receive injected context.
- Overall tier: C.
- Common mistake: splitting one simple tool into unnecessary runtime machinery.

## C + D: Middleware Needs New Runtime Hook

- Middleware is not enough because the required interception point does not exist.
- Source patch adds or moves the hook.
- Overall tier: D.
- Common mistake: claiming normal middleware can intercept places it cannot.

## D + Event Consumer Changes

- Source emits new event or changes existing event shape.
- TUI/ACP/event handlers must be updated.
- Overall tier: D.
- Common mistake: updating producer only.

## A + A: Multiple Tier A Surfaces

- Config enables MCP server. Skill describes when/how to use it. AGENTS.md provides persistent project context. Agent profile restricts tool availability via flat TOML overrides.
- Overall tier: A.
- Common mistake: duplicating guidance across AGENTS.md and skill body, creating conflicting instructions.
- Common mistake: using `allowed_tools` in the skill to restrict tools — it is advisory only. Use agent profile flat-TOML `enabled_tools` override instead.

## A + Hook: Skill With Post-Turn Validation

- Skill provides workflow instructions.
- Hook validates the agent's output after each turn and optionally injects a retry message.
- Overall tier: A.
- Common mistake: treating the hook as a pre-turn or tool-level interceptor. Hooks fire only after the last LLM turn of a user message — never before or during tool execution.
- Common mistake: `exit 2` without stdout — empty stdout on exit code 2 emits a warning only; it does NOT trigger a retry.
- Common mistake: assuming hooks run in subagents. Subagent `AgentLoop` is constructed without `hook_config_result` — subagents never run hooks.

## Hook → Middleware Re-entry

When a hook requests a retry, the loop continues and middleware fires again before the next LLM call. This is not a separate tier but a critical execution-order fact for any composition using both hooks and middleware:

- `TurnLimitMiddleware` counts the hook-triggered LLM call against the turn limit.
- `ContextWarningMiddleware` may fire on the hook-triggered turn if context grew.
- Any stateful middleware tracking "first turn" will see the hook-triggered call as a subsequent turn.

## A + A/B: Subagent Delegation

- Parent uses the built-in `task` tool to delegate to a subagent profile.
- A + A: `task` + built-in `explore` profile. No custom code.
- A + B: `task` + custom subagent profile + custom tools.
- Overall tier: A or B respectively.
- Common mistake: passing a non-subagent profile name to `task` — raises `ToolError` if `agent_type != SUBAGENT`.
- Common mistake: assuming subagents run hooks — subagents never run hooks.
- Common mistake: assuming subagents have their own scratchpad — `is_subagent=True` sets `scratchpad_dir=None`; parent scratchpad path is injected as text in the task prompt.
- Common mistake: assuming `explore` auto-approve applies to custom profiles — only `explore` is in `TaskToolConfig.allowlist`; custom subagents need explicit allowlist or permission config.

## B: Profile Switch via Tool

- Tool performs an action, then calls `ctx.switch_agent_callback` to change the active agent profile.
- The change takes effect on the next LLM turn.
- Overall tier: B.
- Common mistake: expecting the switch to be visible to ACP clients — `AgentProfileChangedEvent` is silently dropped by the ACP layer.
- Common mistake: treating profile switch as a temporary mode change — the switch persists for the remainder of the session unless switched back.

## Tier E Escape Hatch

If a user idea is impossible as stated but feasible with a different implementation, do not label the entire goal impossible. Label the stated mechanism Tier E and propose the feasible replacement mechanism with its tier.

| Stated mechanism (Tier E) | Feasible replacement |
|---|---|
| Middleware that runs after each tool call | `get_result_extra()` on the tool (Tier B) — injects context after the tool result; middleware cannot intercept post-tool |
| Hook that fires before the agent turn | No pre-turn hook exists; use middleware `INJECT_MESSAGE` (Tier C) to inject context before the LLM call |
| Skill `allowed_tools` as a hard tool-access boundary | Agent profile flat-TOML `enabled_tools` override (Tier A) for actual restriction |
| Subagent that writes project files autonomously | Custom subagent profile with write tools permitted (Tier A/B) — "subagents can't write" is prompt guidance on `explore`, not a runtime block |
