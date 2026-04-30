# Extension Point Taxonomy (Tiers A-E)

Every workflow design must be classified by exactly one feasibility tier before implementation. These tiers map to specific Mistral Vibe runtime surfaces.

## Tier A: Native Config / Skill-Only

**Runtime surfaces used:** `config.toml`, SKILL.md files, built-in tools, MCP server config

**Whats available:**
- `config.toml` keys: `api_key`, `active_model`, `auto_approve`, `permission`, `enabled_tools`, `disabled_tools`, `tool_paths`, `[[mcp_servers]]`, and tool-specific config overrides
- Skills: Create `SKILL.md` files in `.vibe/skills/`, `~/.config/vibe/skills/`, or project `skills/` dirs
- Skill format: YAML frontmatter (`name`, `description`, `allowed-tools`, `user-invocable`) + markdown body. `allowed-tools` / `allowed_tools` is a real tool availability constraint while the skill is active.
- Built-in tools: ReadFile, WriteFile, EditFile, Bash, Grep, SearchReplace, Glob, LSP, WebFetch, WebSearch
- MCP servers: Add to `[[mcp_servers]]` in config.toml (stdio, http, streamable-http transports)
- Mistral Connectors: Remote tool surface integrated by ToolManager through ConnectorRegistry, distinct from MCP server config
- `VibeConfig` (vibe/core/config.py): All runtime configuration

**Constraints:**
- Cannot modify AgentLoop behavior (vibe/core/agent_loop.py)
- Cannot add new middleware (vibe/core/middleware.py)
- Cannot change tool permission logic (vibe/core/tools/base.py)
- Cannot add new built-in tool types without MCP

**Feasibility check:** Can the workflow be described entirely in config.toml + SKILL.md files?

**Example:** A skill that runs `git log` and summarizes commits using the Bash tool.

## Tier B: Tool-Level Extension

**Runtime surfaces used:** `vibe/core/tools/builtins/`, `vibe/core/tools/mcp/`, Mistral Connectors, `ToolManager` search paths, `BaseTool` contract

**Whats available:**
- Create Python class inheriting from `BaseTool` in `vibe/core/tools/builtins/` or custom search path
- Tool components (vibe/core/tools/base.py):
  - `ToolArgs` (Pydantic): Input validation
  - `ToolResult` (Pydantic): Execution output
  - `ToolConfig` (Pydantic, inherits `BaseToolConfig`): Configuration
  - `ToolState`: Persistent state for tool instance
- Register in tool search path: `config.tool_paths` or default tool dir
- Tool permission system: `ALWAYS`, `ASK`, `NEVER` + `allowlist`/`denylist`/`sensitive_patterns`
- `resolve_permission()` for per-invocation permission override before config-level permission
- `get_result_extra()` for post-tool context injection to the LLM
- `BaseToolState` for session-local persistent tool state
- `get_tool_prompt()` / `prompt_path` for tool-specific system prompt guidance
- MCP tools: Use `MCPRegistry` (vibe/core/tools/mcp/registry.py) + `create_mcp_http_proxy_tool_class` / `create_mcp_stdio_proxy_tool_class`
- Mistral Connectors: Use ConnectorRegistry-backed remote tools through ToolManager
- `ToolManager` (vibe/core/tools/manager.py): Discovery, configuration merge, instantiation, permission filtering

**Constraints:**
- Tool executes when AgentLoop calls it — cannot change when/why it's called
- Cannot intercept the message flow (that's middleware)
- Cannot add pre-tool middleware
- `BaseTool.__call__(args, ctx)` → `run(args, ctx)` is the only entry point

**Feasibility check:** Does the workflow need a new tool class, but no changes to how/when tools are called?

**Example:** A custom `JiraTicket` tool that calls Jira API, added as a new Python tool class.

## Tier C: Middleware-Level Extension

**Runtime surfaces used:** `vibe/core/middleware.py`, `MiddlewarePipeline`, `Middleware` base class, `MiddlewareAction`, registration code in the runtime/AgentLoop setup

**Whats available:**
- Middleware base: `vibe/core/middleware.py` — subclass `Middleware`
- Pipeline: `MiddlewarePipeline.before_turn()` runs all registered middleware before each LLM call in a multi-step tool loop, not merely once per user message
- `MiddlewareAction` enum: `CONTINUE` (proceed), `STOP` (halt loop), `INJECT_MESSAGE` (add to message history), `COMPACT` (halt loop, same as STOP)
- Built-in middleware: TurnLimitMiddleware, PriceLimitMiddleware, AutoCompactMiddleware, ReadOnlyAgentMiddleware, ContextWarningMiddleware
- Middleware can: modify messages, inject system prompts, halt execution, or trigger compaction through distinct `MiddlewareAction` values
- Pipeline composition: multiple `INJECT_MESSAGE` results compose; `STOP` and `COMPACT` short-circuit later middleware
- Custom middleware is valid when implemented as Python source/runtime-code and registered into the pipeline. Multiple custom middleware are valid if ordering and short-circuit behavior are designed explicitly.
- Registration: Add to pipeline via `AgentLoop.__init__()` or config

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

[ ] Tier A: Native config/skill-only?
    - Only uses: config.toml, SKILL.md, built-in tools, MCP servers
    - No Python code changes needed
    - Source: vibe/core/config.py, SKILL.md format

[ ] Tier B: Tool-level extension?
    - New Python tool class(es) needed
    - No AgentLoop/middleware changes
    - Source: vibe/core/tools/base.py, vibe/core/tools/manager.py

[ ] Tier C: Middleware-level extension?
    - New middleware class(es) needed
    - AgentLoop modifications NOT needed
    - Source: vibe/core/middleware.py, vibe/core/agent_loop.py (pipeline init)

[ ] Tier D: Source modification required?
    - Changes to vibe/core/*.py files
    - Must maintain fork or patches
    - Source: vibe/core/agent_loop.py, vibe/core/tools/, vibe/core/types.py

[ ] Tier E: Not feasible?
    - Explain why
    - Suggest alternative approach

Selected tier: [A/B/C/D/E]
Rationale: [why this tier]
Source files affected: [list Python files, or "none" for A/B]
```
