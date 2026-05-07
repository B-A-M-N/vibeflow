# Tier Composition Patterns

Many real workflows combine tiers. Classify the whole design by the highest required tier, but explain each component separately.

## A + B: Skill Uses Custom Tool

- Skill describes when/how to use a custom tool.
- Tool implements the external action.
- Overall tier: B.
- Common mistake: pretending tool behavior can control the agent loop.

## A + C: Skill With Middleware Guard

- Skill provides workflow instructions.
- Middleware injects context or blocks unsafe continuation before LLM turns (turn limits, budget guards, read-only reminders).
- Overall tier: C (middleware logic) + D (registration in `_setup_middleware()`).
- **Critical mistake: using middleware as a phase state machine.** Middleware cannot observe what the LLM just produced. It runs before the next LLM call. A middleware that advances workflow phases based on LLM output has a structural one-turn delay on every transition and is fragile to any variation in LLM text. The correct surface for phase sequencing is the `task` tool — each phase is a separate `task()` call from the parent agent.
- Common mistake: expecting middleware to run after tool execution.
- Common mistake: assuming `before_turn()` fires once per user message. It fires before **every LLM call** in the tool loop. On a turn with 5 tool calls, middleware fires 6 times. Middleware that counts "turns" or accumulates per-turn state will miscount. Execution order: reset hook retries → loop: `before_turn()` → LLM call + tools → (if hook retries: inject message, loop again with another `before_turn()`).
- Common mistake: `reset()` not checking `ResetReason`. A middleware that clears all state on any `reset()` call will silently restart when context compaction fires (`ResetReason.COMPACT`). Guard: `if reset_reason == ResetReason.STOP: clear_state()`.

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

## A: Multi-Phase Workflow via Task Tool (NOT Middleware)

The correct pattern for multi-phase workflow orchestration. The parent agent sequences phases by issuing `task()` calls and checking `TaskResult.completed` between them.

- Overall tier: A (built-in profiles) or B (custom subagent profiles + custom tools).
- Phase signal: the parent agent issues the next `task()` call when the previous one completes — no middleware, no text parsing, no state machine.
- State across phases: write state to the scratchpad or a workflow YAML file; pass the path in each task prompt.
- **Why not middleware**: middleware fires before LLM calls, cannot observe LLM output, and has no after_turn(). A middleware-based phase machine has a structural one-turn delay on every transition and silently misbehaves if compaction fires mid-phase.
- **Why not text signals**: `PHASE_COMPLETE: X` in LLM output requires regex parsing that breaks on any wording variation. Use a custom `complete_phase` tool returning a `BaseModel` instead.
- Common mistake: designing the phase state machine in middleware and the task dispatch in skills — these two surfaces see different execution points and will diverge.
- Common mistake: not handling `TaskResult.completed = False` — both middleware stops and unhandled exceptions produce `completed=False`; the parent prompt must check it.

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

## B: Scope Enforcement via Tool (NOT Middleware)

- Custom `BaseTool` subclass wraps write/edit operations with `resolve_permission()` that checks target paths against an allowlist.
- Or: `approval_callback` on `AgentLoop` inspects tool call arguments and denies out-of-scope operations.
- Overall tier: B.
- **Critical mistake: implementing scope enforcement as middleware.** Middleware only runs `before_turn()` — it cannot see which tools the LLM will call or what file paths they'll target. A middleware that "blocks each file edit as it happens" is architecturally impossible.
- Common mistake: using skill `allowed_tools` as a scope boundary (advisory only; the model sees all tools regardless).

## B: Phase-Gate Enforcement via Tool + Profile Switch

- Workflow starts in a read-only profile (e.g., `plan`).
- LLM finishes the phase, calls a custom tool: `advance_phase(from="PLAN", to="IMPLEMENT")`.
- The tool validates the transition, writes state to disk, calls `ctx.switch_agent_callback("implement-profile")`.
- `reload_with_initial_messages()` rebuilds backend, ToolManager, SkillManager, and system prompt.
- The new profile's `enabled_tools`/`disabled_tools` physically prevents the LLM from calling tools not in that set.
- Overall tier: B.
- **The trigger is the critical piece**: without a custom tool calling `switch_agent_callback`, there is no enforcement — just text saying "don't use that tool yet." The tool is the only reliable trigger because the LLM must call it to advance, and the tool performs the switch as a side effect.
- **Compaction survival**: after `compact()`, the system prompt (already rebuilt for the current phase) is preserved. The LLM continues working. It does NOT call `advance_phase` to restore state — that tool is for advancing phases, not restoring them.
- **Backend rebuild**: `reload_with_initial_messages()` calls `self.backend_factory()` before rebuilding ToolManager. This is how the new profile's `active_model` takes effect. Designs that show the model change coming from rebuilding the system prompt alone are incorrect.
- Common mistake: expecting `switch_agent` to reset message history — it preserves the full conversation.
- Common mistake: expecting `switch_agent` to clear middleware — the middleware pipeline survives the switch.
- Common mistake: expecting `todo` state to survive a profile switch — `switch_agent` creates a new `ToolManager` and the todo list is lost.

## B: Skill Naming Convention

- Skill directory name must match the `name` field in SKILL.md frontmatter.
- Name must match pattern `^[a-z0-9]+(-[a-z0-9]+)*$` — lowercase letters, numbers, and hyphens only.
- Overall tier: B (skill) + A (config).
- Common mistake: naming a skill "PRForge" — the directory must be `pr` and the name field must be `pr`.

## Tier E Escape Hatch

If a user idea is impossible as stated but feasible with a different implementation, do not label the entire goal impossible. Label the stated mechanism Tier E and propose the feasible replacement mechanism with its tier.

| Stated mechanism (Tier E) | Feasible replacement |
|---|---|
| Middleware that runs after each tool call | `get_result_extra()` on the tool (Tier B) — injects context after the tool result; middleware cannot intercept post-tool |
| Hook that fires before the agent turn | No pre-turn hook exists; use middleware `INJECT_MESSAGE` (Tier C) to inject context before the LLM call |
| Middleware-based phase state machine | `task` tool for each phase (Tier A/B) — parent agent dispatches phases as sequential task calls and checks `TaskResult.completed`; no middleware needed |
| Text signal control flow (`PHASE_COMPLETE: X`) | Custom tool call returning `BaseModel` (Tier B) — structured, machine-readable, and not dependent on exact LLM wording |
| Skill `allowed_tools` as a hard tool-access boundary | Agent profile flat-TOML `enabled_tools` override (Tier A) for actual restriction |
| Subagent that writes project files autonomously | Custom subagent profile with write tools permitted (Tier A/B) — "subagents can't write" is prompt guidance on `explore`, not a runtime block |
| Middleware that blocks individual tool calls mid-turn | Custom `BaseTool` with `resolve_permission()` (Tier B) — middleware only runs `before_turn()` and cannot see or block individual tool calls |
| Phase-gate enforcement without a tool trigger | Custom tool calling `ctx.switch_agent_callback()` (Tier B) — without the tool, there is no enforcement, just guidance text the LLM can ignore |
| `after_turn()` in middleware | Does not exist — the `ConversationMiddleware` Protocol only defines `before_turn()` and `reset()`. Use `get_result_extra()` on a tool (Tier B) for post-tool context injection |
| AgentLoop that writes workflow state files | LLM writes state via tool calls (Tier A/B) — `AgentLoop` has no API for arbitrary state writes; only `SessionLogger` persists conversation history |
| Skill named "PRForge" or similar invalid name | Rename to match `^[a-z0-9]+(-[a-z0-9]+)*$` and directory name (Tier A) — e.g., directory `pr`, name `pr` |
| Compaction survival via `advance_phase` tool | System prompt preservation (built-in) — after `compact()`, the LLM continues working. If detailed state is needed, read a state file via `read_file`. The advance tool is for phase transitions, not state restoration |
| Profile switch that changes model without backend rebuild | `self.backend_factory()` in `reload_with_initial_messages()` (built-in) — the backend must be rebuilt for the new profile's `active_model` to take effect |
| Middleware that calls `switch_agent_callback` | Custom tool calling `ctx.switch_agent_callback()` (Tier B) — `ConversationContext` has no `switch_agent_callback`; it lives exclusively in `InvokeContext` which is only passed to tools |
| Custom middleware returning COMPACT without metadata | Populate `metadata={'old_tokens': ..., 'threshold': ...}` in `MiddlewareResult` (Tier D) — without these keys, `_handle_middleware_result` falls back to misleading defaults |
| Hook type other than `post_agent_turn` | Only `POST_AGENT_TURN` exists — `HookType` is a `StrEnum` with one member. Design must use `before_turn()` middleware (Tier C) for pre-turn behavior |
| Agent profile in `.yaml`/`.json`/`.md` format | Rename to `.toml` (Tier A) — `AgentManager._discover_agents()` only globs `*.toml`; other extensions are silently ignored |
| Tool permission value like `conditional`, `once`, `prompt` | Use only `always`, `never`, or `ask` (Tier A) — `ToolPermission` has 3 values only; anything else raises `ToolPermissionError` |
| Subagent profile used as `--agent` flag | Use an `agent_type=AGENT` profile (Tier A) — `AgentManager.__init__` raises `ValueError` for non-agent profiles as initial agent |
| Subagent tool accessing `ctx.scratchpad_dir` | Pass scratchpad path in task prompt text (Tier A) — `scratchpad_dir=None` when `is_subagent=True`; it's never injected via `InvokeContext` |
| Hook command as Python import path | Use shell command or script path (Tier A) — `HookConfig.command` is a subprocess string; dotted Python paths pass validation but fail at execution |
| `BaseTool` subclass named `PRForgeTool` or `WriteFileTool` | Rename to `PRForge`/`WriteFile` or set `name` explicitly via `ClassVar` (Tier B) — `get_name()` regex produces `p_r_forge_tool`/`write_file_tool` |
| Skill `allowed-tools: "bash, grep"` (comma-separated) | Use space-separated: `allowed-tools: bash grep` (Tier A) — `parse_allowed_tools` uses `.split()`, not `.split(",")` |
| Tool file `_helpers.py` or `_my_tool.py` | Rename to not start with `_` (Tier A) — `_load_tools_from_file()` returns `None` for `_*.py`, silently ignored |
| Tool with syntax/import error | Fix the Python file (Tier A) — bare `except Exception: return` on module load silently drops broken tools |
| Tool mutating `self.state` without lock | Add `asyncio.Lock` (Tier B) — singleton instances + `asyncio.gather` parallel execution = data race |
| Agent TOML with `name = "my-agent"` expecting it to set identity | Rename the file (Tier A) — `name=path.stem` in `from_toml()`; TOML `name` key goes to overrides |
| Agent TOML with `safety: permissive` | Use `safe`, `neutral`, `destructive`, or `yolo` (Tier A) — other values raise `ValueError`, agent silently skipped |
| Same agent stem in multiple search paths | Deduplicate (Tier A) — second copy silently dropped with only `logger.debug()` |
| SKILL.md at search path root (not in subdirectory) | Move to `skills/my-skill/SKILL.md` (Tier A) — `iterdir()` + `is_dir()` guard skips root-level files |
| Custom skill named `vibe-workflow-init` (or any builtin) | Choose a different name (Tier A) — silently skipped when name matches builtin |
| Middleware INJECT before STOP in pipeline | Reorder: STOP first, then INJECT (Tier D) — STOP short-circuits and discards accumulated injects |
| Hook exiting 2 with message on stderr | Write retry message to stdout (Tier A) — stderr-only exit 2 falls through to warning handler |
| Hook assuming unlimited retries | Cap at 3 per user turn (built-in) — `_MAX_RETRIES = 3` hardcoded, resets per user message |
| Tool accessing `ctx.scratchpad_dir` without null guard | Add null check (Tier A) — `init_scratchpad()` can return `None` even for primary agents |
| Tool `run()` using `return result` | Use `yield result` (Tier B) — `run()` must be an AsyncGenerator; `return` produces a coroutine, `async for` raises TypeError |
| Agent TOML in subdirectory of agent_paths | Move to search path root (Tier A) — `glob("*.toml")` not `rglob`; subdir files silently ignored |
| Tool accessing `ctx.plan_file_path` without null guard | Add null check (Tier A) — `plan_file_path: Path | None = None`, only populated for plan agent |
| Tool calling `ctx.approval_callback(...)` without null guard | Add null check (Tier A) — `approval_callback` is None in programmatic/subagent contexts |
| Agent TOML `disabled_tools = [...]` expecting additive | Use `base_disabled` (Tier A) — `disabled_tools` replaces the list via deep merge; `base_disabled` unions |
| Custom tool without `description` ClassVar | Override `description: ClassVar[str]` (Tier B) — default is a placeholder string visible to LLM |
| Hook doing network/compile/test at default 30s timeout | Set explicit timeout (Tier A) — default 30.0s, exceeded hooks killed with WARNING, no retry |
| Config with both `enabled_tools` and `disabled_tools` | Use only one (Tier A) — `enabled_tools` non-empty means `disabled_tools` is ignored; same for skills |
| MCP tool referenced as `server.tool` | Use `server_tool` (Tier A) — MCP tools registered with underscore separator |
| Tool path with helpers/ subdirs containing BaseTool subclasses | Flatten or use `_` prefix (Tier A) — `rglob("*.py")` picks up all subdirectories |
| Custom `plan.toml` overriding builtin plan | Rename file (Tier A) — custom TOML silently replaces builtin (unlike skills); avoid builtin stem names |