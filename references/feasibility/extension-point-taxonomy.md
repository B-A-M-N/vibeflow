# Extension Point Taxonomy (Tiers A-E)

Every workflow design must be classified by exactly one feasibility tier before implementation. These tiers map to specific Mistral Vibe runtime surfaces.

## Tier A: Native Config / Skill-Only

**Runtime surfaces used:** `config.toml`, SKILL.md files, built-in tools, MCP server config

**Whats available:**
- `config.toml` keys: `bypass_tool_permissions` (NOT `auto_approve` — silently ignored), `active_model`, `permission`, `enabled_tools`, `disabled_tools`, `tool_paths`, `[[mcp_servers]]`, `[[connectors]]`, `enable_experimental_hooks`, `system_prompt_id`, `auto_compact_threshold`, `api_timeout`, and tool-specific config overrides. Full key reference: `vibe/core/config/_settings.py`.
- Skills: Create `SKILL.md` files in `skill_paths` (config), `.agents/skills/` (project root, trusted folders only), `.vibe/skills/` (project root, trusted folders only), or `~/.vibe/skills/` (global). `~/.config/vibe/skills/` does **not** exist. Trusted-folder requirement applies to all project-level paths.
- Skill format: YAML frontmatter (`name`, `description`, `allowed-tools`, `user-invocable`) + markdown body. `allowed-tools` / `allowed_tools` is **advisory only** — it is never used to filter `ToolManager.available_tools`. The model sees all available tools regardless. Use agent profile `overrides.enabled_tools` for actual restriction.
- Custom agent profiles: Define a YAML/TOML agent profile with `agent_type = "subagent"` — no Python code needed. The `task` tool can then invoke it by name. This is a valid Tier A surface for subagent delegation.
- Built-in tools: ReadFile, WriteFile, EditFile, Bash, Grep, SearchReplace, Glob, LSP, WebFetch, WebSearch
- MCP servers: Add to `[[mcp_servers]]` in config.toml (stdio, http, streamable-http transports)
- Mistral Connectors: Remote tool surface integrated by ToolManager through ConnectorRegistry, distinct from MCP server config
- Hooks: Create `hooks.toml` (project `.vibe/hooks.toml` or global `~/.vibe/hooks.toml`) + set `enable_experimental_hooks = true`. Hooks are shell scripts — no Python code needed. They fire after agent turns (`POST_AGENT_TURN`), support exit-code retry semantics, have a 30s default timeout, and a 3-retry limit per hook per user turn.
- Tool discovery paths: `DEFAULT_TOOL_DIR` (builtins), `config.tool_paths`, `.vibe/tools/` (project, trusted folders only), `~/.vibe/tools/` (global). Builtins always win on name conflicts.
- `VibeConfig` (vibe/core/config/_settings.py): All runtime configuration

**Constraints:**
- Cannot modify AgentLoop behavior (vibe/core/agent_loop.py)
- Cannot add new middleware (vibe/core/middleware.py)
- Cannot change tool permission logic (vibe/core/tools/base.py)
- Cannot add new built-in tool types without MCP
- `task` tool only accepts profiles with `agent_type = "subagent"` — custom subagent profiles must set this field

**Feasibility check:** Can the workflow be described entirely in config.toml + SKILL.md files + optional hooks.toml + optional agent profile TOML?

**Example:** A skill that runs `git log` and summarizes commits using the Bash tool.

## Tier B: Tool-Level Extension

**Runtime surfaces used:** `vibe/core/tools/builtins/`, `vibe/core/tools/mcp/`, Mistral Connectors, `ToolManager` search paths, `BaseTool` contract

**Whats available:**
- Create Python class inheriting from `BaseTool` in a custom search path (`config.tool_paths`, `.vibe/tools/`, or `~/.vibe/tools/`). **Do NOT place custom tools in `vibe/core/tools/builtins/` — that is a Tier D source modification.**
- Tool components (vibe/core/tools/base.py):
  - `ToolArgs` (Pydantic): Input validation
  - `ToolResult` (Pydantic): Execution output
  - `ToolConfig` (Pydantic, inherits `BaseToolConfig`): Configuration
  - `ToolState`: Persistent state for tool instance
- Tool permission system: `ALWAYS`, `ASK`, `NEVER` + `allowlist`/`denylist`/`sensitive_patterns`
- `resolve_permission()` for per-invocation permission override before config-level permission
- `get_result_extra()` for post-tool context injection to the LLM
- `BaseToolState` for session-local persistent tool state
- `get_tool_prompt()` / `prompt_path` for tool-specific system prompt guidance
- `get_file_snapshot(args)` — called before `run()` to capture file state for the rewind system. Override in tools that modify files.
- `is_available()` classmethod — controls whether the tool appears in `available_tools`. Default returns `True`. Override for platform or dependency checks.
- `InvokeContext.switch_agent_callback` — tools can trigger agent profile switches during execution. This is the supported surface for tool-driven profile transitions.
- MCP tools: Use `MCPRegistry` (vibe/core/tools/mcp/registry.py) + `create_mcp_http_proxy_tool_class` / `create_mcp_stdio_proxy_tool_class`
- Mistral Connectors: Use ConnectorRegistry-backed remote tools through ToolManager
- `ToolManager` (vibe/core/tools/manager.py): Discovery, configuration merge, instantiation, permission filtering

**Actual tool call chain**: `AgentLoop._execute_tool_call` → `tool_instance.invoke(ctx=..., **args_dict)` → `run(args, ctx)`. `invoke()` validates args via Pydantic before calling `run()`. There is no `__call__` on `BaseTool`. The entry point is `invoke()`, not `__call__`.

**Constraints:**
- Tool executes when AgentLoop calls it — cannot change when/why it's called
- Cannot intercept the message flow (that's middleware)
- Cannot add pre-tool middleware

**Feasibility check:** Does the workflow need a new tool class, but no changes to how/when tools are called?

**Example:** A custom `JiraTicket` tool that calls Jira API, placed in `.vibe/tools/`.

## Tier C: Middleware-Level Extension

**Runtime surfaces used:** `vibe/core/middleware.py`, `MiddlewarePipeline`, `Middleware` base class, `MiddlewareAction`, registration code in the runtime/AgentLoop setup

**Whats available:**
- Middleware interface: `vibe/core/middleware.py` — there is **no `Middleware` base class to subclass**. The interface is the `ConversationMiddleware` Protocol. Duck typing works: any object with `async def before_turn(self, context: ConversationContext) -> MiddlewareResult` and `def reset(self, reset_reason: ResetReason = ResetReason.STOP) -> None` is valid middleware.
- Pipeline: `MiddlewarePipeline.before_turn()` runs all registered middleware before each LLM call in a multi-step tool loop, not merely once per user message
- `MiddlewareAction` enum: `CONTINUE` (proceed), `STOP` (halt loop entirely — no compaction), `INJECT_MESSAGE` (add to message history, then continue), `COMPACT` (trigger context compaction, then continue — **NOT the same as STOP**)
- `COMPACT` vs `STOP`: `COMPACT` summarizes history, resets session ID, recalculates `context_tokens`, then continues the loop. `STOP` halts the loop without any of this. They have completely different effects.
- `INJECT_MESSAGE` composition: all `INJECT_MESSAGE` results from all middleware in a single `run_before_turn()` call are collected and joined with `\n\n` into a single injected message. `STOP` and `COMPACT` short-circuit immediately and discard any previously accumulated inject messages.
- Built-in middleware: TurnLimitMiddleware, PriceLimitMiddleware, AutoCompactMiddleware, ReadOnlyAgentMiddleware (registered **twice** — once for `plan` profile, once for `chat` profile, each with different reminder strings), ContextWarningMiddleware
- Custom middleware is valid when implemented as Python source/runtime-code and registered into the pipeline. Multiple custom middleware are valid if ordering and short-circuit behavior are designed explicitly.
- Registration: **there is no config-based middleware registration**. The only path is `middleware_pipeline.add(mw)` in source code. The pipeline is initialized in `_setup_middleware()`, called from `__init__` and `reload_with_initial_messages`. Adding custom middleware requires modifying `_setup_middleware()` or calling `add()` after construction — both are Tier D source changes.

**Constraints:**
- Runs ONLY before LLM turns (not after tool execution, not during tool execution, not on arbitrary events)
- Cannot change the tool execution logic itself
- Cannot add new event types (`BaseEvent` hierarchy in vibe/core/types.py)
- `MiddlewarePipeline` is initialized in `vibe/core/agent_loop.py` AgentLoop

**Feasibility check:** Does the workflow need code to run before LLM turns, but not modify AgentLoop itself?

**Example:** A `WorkflowPhaseGuard` middleware that injects current phase context into system prompt before each turn.

## Tier D: Source Modification Required

**Runtime surfaces used:** All Python source files in `vibe/core/`

**Whats available:**

| Source File | What You Can Modify |
|---|---|
| `vibe/core/agent_loop.py` | AgentLoop: message management (MessageList), LLM backend interaction (BackendLike), tool execution flow, event emission (BaseEvent types), session logging (SessionLogger), stats tracking (AgentStats) |
| `vibe/core/middleware.py` | MiddlewarePipeline + built-in middleware: add new middleware types, change pipeline ordering, modify injection logic |
| `vibe/core/tools/manager.py` | ToolManager: discovery, configuration merge, instantiation, permission filtering; add new discovery sources, change permission logic, add new tool types |
| `vibe/core/tools/base.py` | BaseTool, BaseToolConfig, ToolPermission: add new permission levels, change tool execution lifecycle |
| `vibe/core/types.py` | BaseEvent hierarchy, LLMMessage types, AgentStats: add new event types, change message format |
| `vibe/core/skills/manager.py` | SkillManager: discovery, parsing, command handling; change skill discovery paths, parsing logic, injection method |
| `vibe/core/session/` | SessionLogger, SessionLoader: change storage format, add new metadata fields |
| `vibe/core/system_prompt.py` | Universal system prompt generation, project context, platform rules |
| `vibe/core/agents/models.py` | AgentProfile, AgentType, builtin agent definitions — add new builtin agent types here |
| `vibe/core/agents/manager.py` | AgentManager: agent switching, profile resolution |
| `vibe/core/rewind/` | RewindManager: session fork/rewind, file snapshots (used by `get_file_snapshot()` in tools) |
| `vibe/core/hooks/` | Hooks system: add new hook types beyond `POST_AGENT_TURN`, change hook execution semantics |

**Constraints:**
- Changes are to the installed package — will be overwritten by updates unless maintained as a fork
- Must understand the full event-driven streaming architecture
- Must maintain compatibility with TUI (textual UI) and ACP server interfaces
- `BackendLike` (vibe/core/llm/backend/) is a black box — cannot modify LLM provider behavior

**Feasibility check:** Does the workflow require changing how AgentLoop, tools, middleware, or events work at the source level?

**Example:** Modifying AgentLoop to support a new "plan mode" that automatically enters a planning phase before any tool execution.

## Tier E: Not Feasible / Contradicts Runtime

**What it means:** The workflow demands behavior that contradicts Mistral Vibe's fundamental architecture or cannot be implemented even with source changes.

**Common reasons:**
- Requires the agent to "read the user's mind" (no mechanism for telepathy)
- Requires real-time user interaction during autonomous loops (AgentLoop only checks for user input at specific points; middleware runs before turns, not during)
- Requires new event types that the TUI/ACP cannot handle (without modifying those too)
- Requires tools to execute in parallel without using the supported async/threading model (AgentLoop supports parallel tool calls via asyncio + threading, see agent_loop.py:1-12 and test_ui_snapshot_parallel_tool_calls.py)
- Requires the agent to "remember" across sessions without using SessionLogger (sessions are the only persistence)
- Requires changing how LLM backends work (backend is a black box from Vibe's perspective)
- Requires workflow topology that creates infinite loops with no convergence (AgentLoop has turn limits and middleware guards)

**What to do:** Explicitly label as Tier E, explain why it's not feasible, and suggest alternatives (e.g., "use a human-in-the-loop approval instead of autonomous decision").

## Classification Checklist

For every workflow design, run this checklist:

```
Feasibility Classification:

[ ] Tier A (config/skill): Native config/skill-only?
    - Only uses: config.toml, SKILL.md, built-in tools, MCP servers
    - No Python code changes needed
    - Source: vibe/core/config/_settings.py, SKILL.md format

[ ] Tier A (hooks): Post-turn shell script behavior?
    - Only uses: hooks.toml, enable_experimental_hooks = true
    - No Python code changes needed
    - Constraint: POST_AGENT_TURN only, 3-retry limit, 30s default timeout
    - Source: vibe/core/hooks/

[ ] Tier A (agent profiles): Custom subagent profile?
    - Only uses: YAML/TOML agent definition with agent_type = "subagent"
    - No Python code changes needed
    - Constraint: task tool only accepts AgentType.SUBAGENT profiles
    - Source: vibe/core/agents/models.py

[ ] Tier B: Tool-level extension?
    - New Python tool class(es) needed, placed in tool_paths / .vibe/tools/ / ~/.vibe/tools/
    - No AgentLoop/middleware changes
    - Entry point: invoke() → run(), NOT __call__
    - Source: vibe/core/tools/base.py, vibe/core/tools/manager.py

[ ] Tier C: Middleware-level extension?
    - New middleware class(es) needed (duck-typed Protocol, not ABC subclass)
    - AgentLoop modifications NOT needed (except _setup_middleware() registration)
    - COMPACT ≠ STOP: COMPACT continues after compaction; STOP halts entirely
    - Source: vibe/core/middleware.py, vibe/core/agent_loop.py (_setup_middleware)

[ ] Tier D: Source modification required?
    - Changes to vibe/core/*.py files
    - Must maintain fork or patches
    - Source: vibe/core/agent_loop.py, vibe/core/tools/, vibe/core/types.py, vibe/core/agents/, vibe/core/rewind/, vibe/core/hooks/

[ ] Tier E: Not feasible?
    - Explain why
    - Suggest alternative approach

Selected tier: [A/B/C/D/E]
Rationale: [why this tier]
Source files affected: [list Python files, or "none" for Tier A]
```
