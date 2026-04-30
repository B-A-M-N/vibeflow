# Key Interfaces & Contracts

This document defines the contracts that any workflow implementation must obey when touching Mistral Vibe internals.

## BaseTool Contract (vibe/core/tools/base.py)

Every tool must implement this contract:

```python
class BaseTool(Generic[TAgs, TRes, TConfig, TState]):
    # Identity
    @property
    def name(self) -> str: ...           # Unique tool identifier
    @property
    def description(self) -> str: ...    # What the tool does

    # Configuration
    @classmethod
    def _get_tool_config_class(cls) -> type[TConfig]: ...
    def from_config(cls, config: TConfig) -> Self: ...

    # Execution
    def __call__(self, args: TAgs, ctx: InvokeContext) -> TRes: ...
    def run(self, args: TAgs, ctx) -> TRes: ...  # Actual implementation

    # Permission
    @classmethod
    def get_permission(cls, args: TAgs) -> ToolPermission: ...
```

**Generic parameters:**
- `TArgs`: Pydantic model for input validation (must inherit `ToolArgs`)
- `TRes`: Pydantic model for output (must inherit `ToolResult`)
- `TConfig`: Pydantic model for config (must inherit `BaseToolConfig`)
- `TState`: Persistent state dict (arbitrary, stored per instance)

**Capability flags** (in `BaseToolConfig`, vibe/core/tools/base.py:99-115):
- `permission: ToolPermission` — ALWAYS, ASK, NEVER
- `allowlist: list[str]` — patterns that auto-allow
- `denylist: list[str]` — patterns that auto-deny
- `sensitive_patterns: list[str]` — force ASK even if ALWAYS

**Additional tool extension points:**
- `resolve_permission()` — per-invocation permission override before config-level permission.
- `get_result_extra()` — post-tool context injection to the LLM alongside the tool result.
- `BaseToolState` — session-local persistent state cached by the tool manager.
- `get_tool_prompt()` / `prompt_path` — tool-specific prompt content injected into the system prompt.

## InvokeContext (vibe/core/tools/base.py:45-57)

Passed to every tool execution:

```python
class InvokeContext:
    tool_call_id: str              # Links to ToolCallEvent
    session_dir: Path              # Current session directory
    agent_manager: AgentManager     # Access to agent switching
    skill_manager: SkillManager       # Access to skill discovery/execution
    approval_callback: Callable    # For ASK permission flow
    user_input_callback: Callable  # For requesting user input
    switch_agent_callback: Callable # For agent profile switching
```

**What this means for tool implementors:** Tools can access agent/skill managers, request approval, ask user, and switch agent profiles through this context.

`switch_agent_callback` is the supported tool-orchestration path for profile switching. Do not model profiles as general autonomous coworkers unless the runtime exposes that mechanism.

## ConversationMiddleware Protocol (vibe/core/middleware.py)

All middleware must implement:

```python
class Middleware(ABC):
    async def before_turn(self, messages: MessageList) -> MiddlewareAction:
        # Inspect/modify messages
        # Return MiddlewareAction
        ...
```

**MiddlewareAction** (vibe/core/middleware.py):
```python
class MiddlewareAction(Enum):
    CONTINUE = "continue"          # Proceed to LLM call
    STOP = "stop"                  # Halt the AgentLoop entirely
    INJECT_MESSAGE = "inject_message"  # Add content to message history, then proceed
    COMPACT = "compact"            # Trigger compaction / early return path
```

**MiddlewarePipeline** (vibe/core/middleware.py:33-48):
- `register(middleware: Middleware)` — add middleware to pipeline
- `async before_turn()` — runs all middleware in order, returns first non-CONTINUE action
- Pipeline is called once per LLM turn in the multi-step loop (not per user message, not per tool execution, not per streaming chunk)
- `INJECT_MESSAGE` results compose additively.
- `STOP` and `COMPACT` return immediately and short-circuit later middleware.
- `COMPACT` must be treated as a distinct halting/early-return action, not as normal continuation or generic injection.

**What this means for middleware implementors:** You can inspect/modify message history, halt the loop, or inject messages — but ONLY before LLM turns.

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

**BaseEvent hierarchy** (vibe/core/types.py:332-387):
```python
class BaseEvent(BaseModel):
    event_type: str
    timestamp: datetime

class AssistantEvent(BaseEvent):
    content: str
    stopped_by_middleware: bool = False

class ReasoningEvent(BaseEvent):
    content: str

class ToolCallEvent(BaseEvent):
    tool_name: str
    tool_class: type[BaseTool]
    args: BaseModel
    tool_call_id: str

class ToolResultEvent(BaseEvent):
    tool_name: str
    tool_class: type[BaseTool] | None
    result: BaseModel | None
    error: str | None
    skipped: bool = False
    duration: float | None
```

**AgentStats** (vibe/core/types.py:34-126):
- Token metrics: `session_prompt_tokens`, `session_completion_tokens`, `context_tokens`
- Tool metrics: `tool_calls_agreed`, `tool_calls_rejected`, `tool_calls_failed`, `tool_calls_succeeded`
- Performance: `last_turn_duration`, `tokens_per_second`, `steps`
- Cost: `input_price_per_million`, `output_price_per_million`, `session_cost`

**What this means for workflow designers:** If you need new event types (Tier D), you must also update TUI handlers (vibe/cli/textual_ui/handlers/event_handler.py) and ACP server to handle them.

## Key Source File Map

| Contract | Source File | Key Classes/Functions |
|---|---|---|
| BaseTool | vibe/core/tools/base.py | BaseTool, BaseToolConfig, ToolPermission, InvokeContext |
| ToolManager | vibe/core/tools/manager.py | ToolManager, _available, _instances |
| Middleware | vibe/core/middleware.py | Middleware, MiddlewarePipeline, MiddlewareAction |
| AgentLoop | vibe/core/agent_loop.py | AgentLoop, MessageList, act() |
| Events | vibe/core/types.py | BaseEvent hierarchy, LLMMessage, AgentStats |
| Skills | vibe/core/skills/manager.py | SkillManager, SkillInfo, parse_skill_command |
| Session | vibe/core/session/ | SessionLogger, SessionLoader, SessionMetadata |
| Config | vibe/core/config.py | VibeConfig, MCPServer configs |
| System Prompt | vibe/core/system_prompt.py | get_universal_system_prompt(), ProjectContextProvider |
| LLM Backend | vibe/core/llm/backend/ | BackendLike, MistralBackend, GenericBackend |
