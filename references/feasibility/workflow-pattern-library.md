# Workflow Pattern Library

Common workflow patterns mapped to Mistral Vibe runtime surfaces, feasibility tiers, and constraints.

## Pattern: Skill-Guided Workflow

**Use when:** The desired behavior can be achieved by better instructions, command modes, or reusable knowledge.

- Runtime surface: skills + config
- Tier: A
- Constraints: cannot change AgentLoop, middleware timing, tool permissions, event schema, or persistence model; the scratchpad system prompt section is only injected for the parent agent (`scratchpad_dir` is non-None) — skills that reference scratchpad paths are invisible to subagents
- Proof: skill loads correctly, instructions are followed, no source changes needed

## Pattern: External Service Tool

**Use when:** The workflow needs a new action such as Jira, GitHub, database, or internal API access.

- Runtime surface: tool or MCP server
- Tier: B
- Constraints: tool runs only when selected by the model/tool system; it does not intercept message flow; if the tool is used as a custom subagent via `task`, `TaskToolConfig.allowlist` only contains `["explore"]` by default — custom subagent profiles require explicit allowlist or permission config under `[tools.task]`
- Proof: tool contract validates args/results, permissions are correct, failure modes are reported

## Pattern: Post-Turn Validation/Retry

**Use when:** The workflow needs to inspect the agent's output after each turn, inject corrective feedback, or enforce quality gates without modifying source.

- Runtime surface: hooks (`hooks.toml`, `enable_experimental_hooks = true`)
- Tier: A
- Constraints:
  - `POST_AGENT_TURN` only — no pre-turn, no tool-level interception
  - 3-retry ceiling per hook name per user turn; retry count resets on new user message
  - `exit 2` + non-empty stdout = retry; `exit 2` + empty stdout = warning only (silent failure)
  - 30s default timeout; chain breaks on first retrying hook
  - Subagents never run hooks — `hook_config_result` is not passed to subagent `AgentLoop`
  - Requires `enable_experimental_hooks = true`; field has `exclude=True` and will not appear in auto-generated config
- Proof: `HookEndEvent.status` is `OK`, retry message injected when expected, `HookRunEndEvent` fires

## Pattern: Subagent Delegation

**Use when:** The workflow needs to delegate a bounded, autonomous subtask to a specialized agent without consuming parent context.

- Runtime surface: `task` tool (built-in), agent profiles (`agent_type = subagent`)
- Tier: A (built-in `explore`) or B (custom subagent profile + custom tools)
- Constraints:
  - `task` only accepts `agent_type = SUBAGENT` profiles; passing a primary agent profile raises `ToolError`
  - `explore` is auto-approved; custom subagents require explicit `allowlist` or permission config under `[tools.task]`
  - `TaskResult.completed = False` when middleware stops the subagent OR when a tool call is skipped
  - Subagents have no scratchpad (`is_subagent=True` → `scratchpad_dir=None`); parent scratchpad path is injected into the task text string
  - Subagents do not run hooks
  - Parallel subagents require multiple `task` tool calls in one LLM turn, not a single call
  - "Subagents cannot write files" is prompt guidance on `explore`, not a runtime block; custom subagent profiles with write tools can write
- Proof: `TaskResult.completed` is `True`, response is non-empty

## Pattern: Phase/Policy Guard

**Use when:** The workflow needs to inject phase context, stop unsafe continuation, or enforce turn-level policy before LLM calls.

- Runtime surface: middleware + source registration in `_setup_middleware()`
- Tier: D (registration requires modifying `AgentLoop._setup_middleware()` — a source change; the middleware logic itself is Tier C)
- Constraints: middleware runs before LLM turns, not during tool execution or after tool results; runs before every LLM call in the tool loop, not once per user message
- Proof: middleware returns correct `MiddlewareAction`, including `COMPACT` handling

## Pattern: Event-Aware UX or Telemetry

**Use when:** The workflow needs custom visibility, streaming display, or observability.

- Runtime surface: event system + handlers + diagnostics
- Tier: C (consuming existing events) or D (new event types or changed event shapes)
  - Tier C: consuming existing events (`CompactStartEvent`, `ToolResultEvent`, etc.) in a custom consumer — no new event types needed
  - Tier D: adding new event types, changing existing event field shapes, or adding new consumers to TUI/ACP handlers
- Constraints: new event types require updates to consumers such as TUI/ACP handlers; hook events are not surfaced to ACP clients at all
- Note: OTEL (`vibe/core/tracing.py`, opt-in via `enable_otel = true`) and `TelemetryClient` are distinct surfaces. OTEL exports to an external OTLP endpoint and is the correct surface for external proof. `TelemetryClient` sends to Mistral's internal servers and is not accessible to workflow validation scripts.
- Proof: emitted events are consumed without breaking existing UI/server paths

## Pattern: Session-Backed Continuity

**Use when:** The workflow needs persistence across turns or sessions.

- Runtime surface: SessionLogger / SessionLoader / session metadata
- Tier:
  - A: reading/writing files in the session directory, using `SessionLoader.load_session()` to replay prior context — no source changes
  - C: middleware that reads `ConversationContext` to inject session-derived state before each turn
  - D: changing `SessionLogger` storage format, adding new metadata fields, or modifying `_reset_session()` behavior
- Constraints: do not claim memory across sessions unless it is stored and loaded through real persistence; session ID changes after compaction — validation evidence must follow the `parent_session_id` chain
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
- Is the workflow interactive or headless? `ask_user_question` is unavailable in three distinct ways: (1) CLI `-p` / `--prompt` mode adds it to `disabled_tools` — the tool is hidden from the model; (2) ACP contexts load config with `disabled_tools=["ask_user_question"]` — same effect; (3) `run_programmatic()` called directly does NOT add it to `disabled_tools`, but passes no `user_input_callback` — the tool appears in the model's list but **fails at runtime with no callback** when invoked. All three must be accounted for separately.
- Does the workflow use hooks? Is `enable_experimental_hooks = true` confirmed in config? Without it, hooks are silently disabled. The field has `exclude=True` and will not appear in auto-generated config.
- Does the workflow spawn subagents via `task`? Does it handle `TaskResult.completed = False`? This fires on middleware stop AND on skipped tool calls.
- Does the workflow depend on a stable session ID? Session ID changes after compaction — validation evidence must follow the `parent_session_id` chain.
