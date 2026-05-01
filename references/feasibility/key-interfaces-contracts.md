# Key Interfaces & Contracts

This document defines the contracts that any workflow implementation must obey when touching Mistral Vibe internals.

## BaseTool Contract (vibe/core/tools/base.py)

Every tool must implement this contract:

```python
class BaseTool(Generic[TAgs, TRes, TConfig, TState]):
    # Identity — name is a ClassVar[str] or via get_name() classmethod, NOT a @property
    # description is a ClassVar[str], NOT a @property
    name: ClassVar[str]
    description: ClassVar[str]

    # Configuration
    @classmethod
    def _get_tool_config_class(cls) -> type[TConfig]: ...
    @classmethod
    def from_config(cls, config_getter: Callable[[], TConfig]) -> Self: ...
    # from_config receives a GETTER FUNCTION, not the config object directly

    # Execution — actual call chain: AgentLoop._execute_tool_call → invoke(ctx, **raw) → run(args, ctx)
    # There is no __call__ on BaseTool. invoke() validates args via Pydantic before calling run().
    def invoke(self, ctx: InvokeContext, **raw_kwargs) -> TRes: ...  # Entry point (validates args)
    def run(self, args: TAgs, ctx: InvokeContext) -> TRes: ...       # Implementation target

    # Rewind / availability — no get_permission() classmethod; permission via BaseToolConfig.permission
    def get_file_snapshot(self, args: TAgs) -> ...: ...  # Called before run() for session rewind. Override in tools that modify files.
    @classmethod
    def is_available(cls) -> bool: ...  # Controls whether tool appears in available_tools. Default True.
```

**Generic parameters:**
- `TArgs`: Pydantic model for input validation (must inherit `ToolArgs`)
- `TRes`: Pydantic model for output (must inherit `ToolResult`)
- `TConfig`: Pydantic model for config (must inherit `BaseToolConfig`)
- `TState`: must inherit `BaseToolState` (Pydantic model with `extra="forbid"`) — not an arbitrary dict

**Permission** — there is no `get_permission()` classmethod on `BaseTool`. Permission is controlled by:
- `BaseToolConfig.permission: ToolPermission` — default is `ToolPermission.ASK`
- `resolve_permission(args, ctx)` — per-invocation override called before config-level permission

**`ToolPermission` values are lowercase StrEnum**: `"always"`, `"ask"`, `"never"`. Config files must use lowercase. `permission = "always"` not `"ALWAYS"`.

**Capability flags** (in `BaseToolConfig`, vibe/core/tools/base.py:99-115):
- `permission: ToolPermission` — `"always"`, `"ask"`, `"never"`
- `allowlist: list[str]` — patterns that auto-allow
- `denylist: list[str]` — patterns that auto-deny
- `sensitive_patterns: list[str]` — force ASK even if `"always"`

**Additional tool extension points:**
- `resolve_permission(args, ctx)` — per-invocation permission override before config-level permission.
- `get_result_extra()` — post-tool context injection to the LLM alongside the tool result.
- `BaseToolState` — session-local persistent state (Pydantic model, `extra="forbid"`).
- `get_tool_prompt()` / `prompt_path` — tool-specific prompt content injected into the system prompt.
- `get_file_snapshot()` — capture file state before `run()` for the rewind system; override in tools that modify files.
- `is_available()` — platform/dependency gate; tool is hidden from `available_tools` when `False`.

## InvokeContext (vibe/core/tools/base.py:42-57)

Passed to every tool execution. All fields are optional with `None` defaults:

```python
class InvokeContext:
    tool_call_id: str                              # Links to ToolCallEvent
    session_dir: Path | None                       # Current session directory (None in some subagent contexts)
    agent_manager: AgentManager | None             # Access to agent switching
    skill_manager: SkillManager | None             # Access to skill discovery/execution
    approval_callback: Callable | None             # For ASK permission flow
    user_input_callback: Callable | None           # For requesting user input
    switch_agent_callback: Callable | None         # For agent profile switching
    sampling_callback: MCPSamplingHandler | None   # For MCP sampling flows
    entrypoint_metadata: EntrypointMetadata | None # Telemetry/call-site metadata
    plan_file_path: Path | None                    # Path to active plan file (plan mode)
    scratchpad_dir: Path | None                    # Path to session scratchpad directory
```

**What this means for tool implementors:** Tools can access agent/skill managers, request approval, ask user, switch agent profiles, and access scratchpad/plan paths through this context. All fields may be `None` — guard before use.

`switch_agent_callback` is the supported tool-orchestration path for profile switching. Do not model profiles as general autonomous coworkers unless the runtime exposes that mechanism.

## ConversationMiddleware Protocol (vibe/core/middleware.py)

There is **no `Middleware` ABC to subclass**. The interface is a Protocol (`ConversationMiddleware`). Duck typing works — any object implementing the two methods below is valid middleware:

```python
# ConversationMiddleware Protocol — duck-typed, not an ABC
async def before_turn(self, context: ConversationContext) -> MiddlewareResult:
    # Inspect conversation context
    # Return MiddlewareResult with a MiddlewareAction
    ...

def reset(self, reset_reason: ResetReason = ResetReason.STOP) -> None:
    # Called by the pipeline on STOP or COMPACT actions.
    # Stateless middleware may use pass — this is the norm for built-ins like TurnLimitMiddleware.
    # Stateful middleware must handle both ResetReason.STOP and ResetReason.COMPACT correctly.
    ...
```

`ResetReason` has two values: `ResetReason.STOP` (session or middleware halt) and `ResetReason.COMPACT` (context compaction). Custom middleware must handle both paths. The pipeline calls `reset()` with the appropriate reason on every STOP or COMPACT event.

**MiddlewareAction** (vibe/core/middleware.py):
```python
class MiddlewareAction(Enum):
    CONTINUE = "continue"          # Proceed to LLM call
    STOP = "stop"                  # Halt the AgentLoop entirely — no compaction
    INJECT_MESSAGE = "inject_message"  # Collect message; joined with \n\n; continue after all middleware
    COMPACT = "compact"            # Trigger compaction (summarize, reset session ID, recalculate context_tokens), then CONTINUE — NOT the same as STOP
```

**`COMPACT` vs `STOP`**: `COMPACT` summarizes history, resets session ID, recalculates `context_tokens`, then continues the loop. `STOP` halts the loop entirely with no compaction. These have completely different effects.

**`INJECT_MESSAGE` composition**: all `INJECT_MESSAGE` results from all middleware in a `run_before_turn()` call are collected and joined with `\n\n` into a single injected message. If any middleware returns `STOP` or `COMPACT`, all previously accumulated injections are discarded.

**MiddlewarePipeline** (vibe/core/middleware.py:33-48):
- `add(middleware)` — add middleware to pipeline (source code only — no config-based registration)
- `async before_turn()` — runs all middleware in order, returns first non-CONTINUE action
- Pipeline is called once per LLM turn in the multi-step loop (not per user message, not per tool execution, not per streaming chunk)
- `STOP` and `COMPACT` return immediately and short-circuit later middleware.

**Registration**: there is no config-based middleware registration. The only path is modifying `_setup_middleware()` in `vibe/core/agent_loop.py` or calling `add()` after construction. Both are Tier D source changes. `ReadOnlyAgentMiddleware` is registered twice — once for the `plan` profile and once for the `chat` profile, each with different reminder text.

**What this means for middleware implementors:** Custom middleware is valid, and multiple middleware can be composed. It must be implemented as runtime/source code and registered with the pipeline. You can inspect conversation context, halt the loop, request compaction, or inject messages, but only before LLM turns.

## ConversationContext (vibe/core/types.py)

The message/event types that flow through the system:

**LLMMessage** (vibe/core/types.py:213-285):
```python
class LLMMessage(BaseModel):
    role: Role                    # system, user, assistant, tool
    content: Content | None        # Main message content
    reasoning_content: Content | None  # Model's internal reasoning
    tool_calls: list[ToolCall] | None # Tool invocations
    tool_call_id: str | None      # Links tool result to call
    message_id: str | None        # Unique identifier
```

**BaseEvent hierarchy** (vibe/core/types.py:345-423):
```python
class BaseEvent(BaseModel, ABC):
    # No event_type or timestamp fields — BaseEvent has only model_config = ConfigDict(arbitrary_types_allowed=True)
    pass

class UserMessageEvent(BaseEvent):
    content: str                      # User input being processed
    message_id: str                   # Unique identifier for this user message

class AssistantEvent(BaseEvent):
    content: str
    stopped_by_middleware: bool = False   # True when middleware halted the response

class ReasoningEvent(BaseEvent):
    content: str                      # Backend-specific: see note below

class ToolCallEvent(BaseEvent):
    tool_name: str
    tool_class: type[BaseTool]
    args: BaseModel
    tool_call_id: str
    tool_call_index: int | None       # Parallel call index — use to correlate parallel calls to results

class ToolResultEvent(BaseEvent):
    tool_name: str
    tool_class: type[BaseTool] | None
    result: BaseModel | None
    error: str | None
    skipped: bool = False
    skip_reason: str | None           # Populated when skipped=True
    cancelled: bool = False           # True when user cancelled mid-execution
    duration: float | None
    tool_call_id: str

class ToolStreamEvent(BaseEvent):
    tool_name: str                    # Name of the tool streaming output
    message: str                      # Real-time output fragment
    tool_call_id: str                 # Links to originating ToolCallEvent

class CompactStartEvent(BaseEvent):
    current_context_tokens: int       # Token count BEFORE compaction (NOT old_context_tokens)
    threshold: int                    # The auto_compact_threshold that triggered this
    tool_call_id: str                 # ACP protocol workaround — compact events tunneled as tool calls

class CompactEndEvent(BaseEvent):
    old_context_tokens: int           # Token count before compaction
    new_context_tokens: int           # Token count after compaction
    summary_length: int               # Char count of compaction summary — proof point for non-empty summary
    threshold: int
    tool_call_id: str

class WaitingForInputEvent(BaseEvent):
    task_id: str                      # Identifies the pending input request
    label: str | None                 # Display label for the input prompt
    predefined_answers: list[str] | None  # Structured answers for ask_user_question UI
```

**ReasoningEvent availability is backend-specific**: Mistral backend extracts `ReasoningEvent` content from native `ThinkChunk` elements. Generic backend requires `reasoning_field_name` to be configured in `ProviderConfig` — if not configured, `ReasoningEvent` is not emitted. Do not design control flow that depends on `ReasoningEvent` without confirming the active backend and its config.

**`AssistantEvent.stopped_by_middleware`**: when `True`, the response was halted by middleware, not by natural completion. Programmatic consumers can distinguish middleware-forced stops from normal ends by checking this field on the final `AssistantEvent`.

**`message_observer` callback**: `AgentLoop` supports a `message_observer` callback that captures full conversation state via the `MessageList` and fires when messages are added or modified. This is separate from the event stream and persists state even if the UI disconnects. It is the correct surface for programmatic consumers that need full conversation capture, not event-by-event streaming.

**AgentStats** (vibe/core/types.py:34-103) — full field inventory:

| Field | Type | Notes |
|---|---|---|
| `steps` | `int` | LLM call count, not user turn count |
| `session_prompt_tokens` | `int` | Cumulative input tokens |
| `session_completion_tokens` | `int` | Cumulative output tokens |
| `session_total_llm_tokens` | computed | Sum of prompt + completion tokens |
| `context_tokens` | `int` | Current context window size; updated after each LLM call and after compaction. This is what `AutoCompactMiddleware` compares against `auto_compact_threshold`. Use it to prove compaction fired or that context stayed within bounds. |
| `tool_calls_agreed` | `int` | Approved (not the same as succeeded) |
| `tool_calls_rejected` | `int` | User-rejected or permission-denied |
| `tool_calls_failed` | `int` | Threw an exception |
| `tool_calls_succeeded` | `int` | Completed without error |
| `last_turn_duration` | `float` | Seconds for last LLM call |
| `tokens_per_second` | `float` | Output throughput for last LLM call |
| `session_cost` | computed | **Rough worst-case estimate only.** Prompt caching not reflected. If model changes mid-session, uses current pricing for all accumulated tokens. Do not use as a hard gate. |

**Reset semantics:**
- `AgentStats` is **NOT reset** on `compact()` — cumulative session totals survive compaction.
- `AgentStats` **IS reset** on `clear_history()` via `AgentStats.create_fresh()`. Validation evidence spanning a `clear_history()` call will see zeroed stats. Listeners are copied to the fresh instance; accumulated counts are not.

**`ToolResultEvent.duration`**: tool execution latency in seconds (float). Available in the event stream. Use this as the proof point for tool latency bounds, not log parsing.

**What this means for workflow designers:** If you need new event types (Tier D), you must also update TUI handlers (vibe/cli/textual_ui/handlers/event_handler.py) and ACP server to handle them.

## OpenTelemetry Observability (vibe/core/tracing.py)

OTEL is **opt-in** (`enable_otel = false` by default, `exclude=True` so it won't appear in generated config) and **best-effort** — tracing failures are caught and logged as warnings, never raised to the caller.

**Prerequisites:**
- `enable_otel = true` in config
- Either `otel_endpoint` set explicitly, or `MISTRAL_API_KEY` (or the configured `api_key_env_var`) available in environment. If neither is set, `otel_span_exporter_config` returns `None` and tracing is silently disabled.

**Span inventory:**

`invoke_agent mistral-vibe` (one per `act()` call):
- `gen_ai.operation.name = "invoke_agent"`
- `gen_ai.provider.name = "mistral_ai"`
- `gen_ai.agent.name = "mistral-vibe"`
- `gen_ai.request.model` (model alias)
- `gen_ai.conversation.id` (session ID, also propagated as OTEL baggage to child spans)

`execute_tool {name}` (one per tool call, child of agent span):
- `gen_ai.tool.name`, `gen_ai.tool.call.id`, `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result`, `gen_ai.tool.type = "function"`
- `gen_ai.conversation.id` (inherited via baggage)

The Mistral SDK also creates `chat {model}` spans as siblings under the agent span.

**`TelemetryClient` is not OTEL.** These are separate surfaces:
- `TelemetryClient` sends events to Mistral's internal telemetry servers (`enable_telemetry`, default enabled). Events: `vibe.request_sent` (before each LLM call), `tool_call_finished` (after each tool). Not accessible to external workflow validation.
- OTEL is opt-in, exports to a configurable OTLP endpoint, and is the correct surface for external observability proof and per-tool validation.

**Design implication:** Prefer OTEL `execute_tool` spans for per-tool proof (arguments and result are span attributes). Prefer session logs for conversation-level audit (full message sequence). Do not rely on session log JSONL parsing for per-tool verification — it requires manual correlation of tool calls to results.

## Session File Format (vibe/core/session/session_loader.py)

Session data is stored per-session in a directory with two files:

- `messages.jsonl` — one JSON object per line, each with `role` and `content`. System messages are excluded when loaded via `SessionLoader.load_session()`.
- `meta.json` — fields: `session_id`, `parent_session_id`, `cwd`, `title`, `end_time`, `environment.working_directory`

**Session ID drift after compaction:** `_reset_session()` generates a new session ID (same suffix, new timestamp prefix) and sets `parent_session_id` to the old ID. Validation evidence that uses session IDs to locate log files must follow the `parent_session_id` chain — a single session ID is not stable across the full workflow run if compaction fires.

## Hook Invocation Contract (vibe/core/hooks/models.py)

Hook scripts receive this JSON payload on stdin at invocation:

```python
class HookInvocation(BaseModel):
    session_id: str          # Current session ID
    transcript_path: str     # Path to the session transcript file
    cwd: str                 # Working directory for the session
    hook_event_name: str     # Name of the hook event that fired
```

Hook scripts must read and parse stdin to get session context. Without this, the script has no access to the transcript or session identity.

**Exit code contract:**
- `0` → success, no agent effect
- `2` + non-empty stdout → retry: stdout is injected as a user-role message, hook chain breaks
- `2` + empty stdout → warning only, no retry (common bug: using `exit 2` as generic failure without printing feedback)
- any other non-zero → warning only, no retry

**3-retry ceiling:** the runtime tracks retries per hook name per user turn (`_MAX_RETRIES = 3`). After 3 retries, the hook logs an error and stops retrying for that turn. Retry count resets on every new user message. Workflows using hooks as quality gates must account for this ceiling.

## Key Source File Map

| Contract | Source File | Key Classes/Functions |
|---|---|---|
| BaseTool | vibe/core/tools/base.py | BaseTool, BaseToolConfig, ToolPermission, InvokeContext |
| ToolManager | vibe/core/tools/manager.py | ToolManager, _available, _instances |
| Middleware | vibe/core/middleware.py | ConversationMiddleware (Protocol), MiddlewarePipeline, MiddlewareAction, ResetReason |
| AgentLoop | vibe/core/agent_loop.py | AgentLoop, MessageList, act() |
| Events | vibe/core/types.py | BaseEvent hierarchy, LLMMessage, AgentStats |
| Skills | vibe/core/skills/manager.py | SkillManager, SkillInfo, parse_skill_command |
| Hooks | vibe/core/hooks/manager.py | HooksManager, HookRetryState, HookExitCode |
| Hook Config | vibe/core/hooks/config.py | load_hooks_from_fs, HookConfigResult |
| Hook Models | vibe/core/hooks/models.py | HookInvocation, HookConfig |
| Session | vibe/core/session/ | SessionLogger, SessionLoader, SessionMetadata |
| Config | vibe/core/config/_settings.py | VibeConfig, ModelConfig, SessionLoggingConfig, ConnectorConfig |
| System Prompt | vibe/core/system_prompt.py | get_universal_system_prompt(), ProjectContextProvider |
| LLM Backend | vibe/core/llm/backend/ | BackendLike, MistralBackend, GenericBackend |
| Tracing | vibe/core/tracing.py | agent_span, tool_span, set_tool_result, _safe_span |
| Session Loader | vibe/core/session/session_loader.py | SessionLoader, load_session, MESSAGES_FILENAME, METADATA_FILENAME |
| Agent Profiles | vibe/core/agents/models.py | AgentProfile, AgentType, BuiltinAgentName |
| Agent Manager | vibe/core/agents/manager.py | AgentManager, switch_profile() |
| Rewind | vibe/core/rewind/manager.py | RewindManager, FileSnapshot |
| Scratchpad | vibe/core/scratchpad.py | init_scratchpad() |
