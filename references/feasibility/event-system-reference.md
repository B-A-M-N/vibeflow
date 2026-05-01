# Event System Reference

Use this when a design depends on streaming, observability, UI behavior, or validation proof.

## Core Rule

Events are runtime outputs that consumers must understand. Adding new event types is not just a producer change; every relevant consumer must be updated.

## Full Event Inventory

| Event | Key Fields | When It Fires |
|---|---|---|
| `UserMessageEvent` | `content` | User input received |
| `AssistantEvent` | `content`, `stopped_by_middleware` | Each LLM text chunk; final event has `stopped_by_middleware=True` if middleware halted |
| `ReasoningEvent` | `content` | Model reasoning/thinking blocks (backend-specific — see below) |
| `ToolCallEvent` | `tool_name`, `args`, `tool_call_id`, `tool_call_index` | Tool invocation requested; `tool_call_index` is the parallel call index — use it to correlate parallel tool calls to results in correct order |
| `ToolResultEvent` | `result`, `error`, `skipped`, `skip_reason`, `duration`, `cancelled`, `tool_call_id` | Tool execution completed |
| `ToolStreamEvent` | `message`, `tool_call_id` | Real-time output fragment from a running tool |
| `CompactStartEvent` | `current_context_tokens`, `tool_call_id` | Context compaction begins; `current_context_tokens` = tokens before compaction; `tool_call_id` is an ACP protocol workaround (compact events are tunneled as tool calls in the ACP spec) |
| `CompactEndEvent` | `old_context_tokens`, `new_context_tokens`, `summary_length`, `tool_call_id` | Context compaction complete; `summary_length` (int, char count) is a proof point that compaction produced a non-empty summary |
| `WaitingForInputEvent` | `task_id`, `label`, `predefined_answers` | Agent paused awaiting user response; `label` and `predefined_answers` carry structured prompt data for consumers rendering `ask_user_question` UI |
| `AgentProfileChangedEvent` | (profile fields) | Active agent profile changed mid-turn via `switch_agent`; **silently dropped by ACP layer** — ACP clients do not see profile changes without source changes |
| `HookRunStartEvent` | — | Hook chain begins for the turn |
| `HookStartEvent` | `hook_name` | Individual hook begins executing |
| `HookEndEvent` | `hook_name`, `status` (`OK`/`WARNING`/`ERROR`), `content` | Individual hook finished; `content` has detail on failure/timeout |
| `HookRunEndEvent` | — | Entire hook chain for the turn completed; TUI uses this to clean up the `HookRunContainer` widget (removes it if no hook messages were shown, leaves it if any were). Any consumer that opens a hook UI container on `HookRunStartEvent` must close or finalize it on `HookRunEndEvent`. |

**`HookUserMessage` is not a `BaseEvent`**: it is a `BaseModel` yielded by `HooksManager.run()` alongside events as a distinct signal type. The agent loop handles it by injecting the content as a user-role message and triggering a retry. It is never passed to the TUI `EventHandler` or the ACP layer. Do not model it as an event; it is a hook retry signal internal to the agent loop.

## Known Event Surfaces

- `vibe/core/types.py`: `BaseEvent` hierarchy, `LLMMessage`, `AgentStats`
- `vibe/core/agent_loop.py`: emits all events above
- `vibe/cli/textual_ui/handlers/event_handler.py`: TUI event consumption
- ACP/server paths: must understand any event surfaced to external clients
- `message_observer` callback: separate from the event stream; fires on `MessageList` mutations (with gaps — see below)

## ACP Consumer Coverage

Not all events are surfaced to ACP clients. Workflows that depend on ACP-visible events must verify coverage here:

| Event | TUI handling | ACP handling |
|---|---|---|
| `AssistantEvent` | Rendered as assistant message | → `AgentMessageChunk` |
| `ReasoningEvent` | Rendered as thought | → `AgentThoughtChunk` |
| `ToolCallEvent` | Tool call widget | → tool call session update (conditional) |
| `ToolResultEvent` | Tool result widget | → tool result session update (conditional) |
| `ToolStreamEvent` | Streaming tool output | → `ToolCallProgress` |
| `CompactStartEvent` | Internal state transition | → compact start session update |
| `CompactEndEvent` | Internal state transition | → compact end session update |
| `AgentProfileChangedEvent` | `on_profile_changed` callback | **silently dropped (`pass`)** |
| `HookRunStartEvent` | Loading widget shown | **not handled — not in ACP event loop** |
| `HookStartEvent` | Loading widget (double-dispatch — see below) | **not handled** |
| `HookEndEvent` | Loading widget update | **not handled** |
| `HookRunEndEvent` | `HookRunContainer` cleanup | **not handled** |
| `WaitingForInputEvent` | Input prompt rendered | not enumerated above |

**Implication:** Any workflow that switches agent profiles and expects ACP clients to reflect the change requires source changes to the ACP layer. Hook events are entirely invisible to ACP clients without source changes.

## `message_observer` — Programmatic Observation Surface

`AgentLoop` supports a `message_observer` callback that fires on `MessageList` mutations. This is distinct from the event stream:

- Events are ephemeral streaming signals consumed by the UI and ACP layer.
- `message_observer` captures durable conversation state and persists even if the UI disconnects.

**Critical observer gaps** — the observer does NOT fire on all mutations:
- `append()` and `extend()` → **notify observer** ✓
- `insert()` → **does not notify** — messages inserted mid-list are invisible to the observer
- `reset()` → **does not notify** — calls `on_reset` hooks instead (separate registration path via `MessageList.on_reset(hook)`)
- `silent()` context manager → **suppresses all notifications** while active

Programmatic consumers using `message_observer` for full conversation capture will miss messages inserted via `insert()` and will not see the list replacement that occurs during compaction (which uses `reset()`). Consumers that need compaction-safe capture must also register an `on_reset` hook.

## `ReasoningEvent` Is Backend-Specific

`ReasoningEvent` is only emitted when the active backend supports it:

- **Mistral backend**: extracts from native `ThinkChunk` elements — always available when the model emits thinking.
- **Generic backend**: requires `reasoning_field_name` configured in `ProviderConfig`. If not configured, `ReasoningEvent` is never emitted.

Do not design control flow that depends on `ReasoningEvent` without confirming the active backend and its config.

## `CompactStartEvent` / `CompactEndEvent` for Programmatic Monitoring

These events carry token counts before and after compaction. Programmatic workflows that need to monitor context usage or log compaction events should consume these events from the stream. They are not surfaced to the TUI as visible messages — only as internal state transitions.

The `context_tokens` field on `AgentStats` is recalculated via a real token count call after compaction completes. This is the authoritative proof point that compaction fired and context is within bounds — not the event alone.

## `ToolResultEvent.duration` — Tool Latency Proof

`ToolResultEvent.duration` (float, seconds) is the correct proof point for tool execution latency. It is available directly in the event stream without log parsing or OTEL. Use it for latency bounds validation in programmatic workflows.

## Observability Proof Surface Selection

| Proof need | Correct surface |
|---|---|
| Per-tool arguments and result | OTEL `execute_tool` span attributes |
| Tool latency | `ToolResultEvent.duration` |
| Conversation-level audit | Session log `messages.jsonl` |
| Session identity / lineage | Session log `meta.json` (`session_id`, `parent_session_id`) |
| Compaction fired | `CompactStartEvent` / `CompactEndEvent` + `AgentStats.context_tokens` |
| Middleware halt | `AssistantEvent.stopped_by_middleware = True` |
| Cumulative cost estimate | `AgentStats.session_cost` (worst-case estimate, not exact) |

OTEL is opt-in (`enable_otel = false` default). Any design that claims OTEL as a proof surface must assert `enable_otel = true` in validation evidence. OTEL errors are swallowed — tracing failures are logged as warnings and never raised.

## Failure Modes

- **OTEL enabled but API key not set**: `otel_span_exporter_config` returns `None` and tracing is silently disabled. No error is raised.
- **Stats zeroed by `clear_history()`**: `AgentStats` is reset on `clear_history()` via `AgentStats.create_fresh()`. Evidence collected after a history clear does not represent the full session. Stats survive `compact()` — only `clear_history()` resets them.
- **Session ID drift after compaction**: `_reset_session()` generates a new session ID (same suffix, new timestamp prefix) and sets `parent_session_id` to the old ID. Evidence that records a session ID at workflow start may not match the session ID at validation time if compaction fired. Follow the `parent_session_id` chain.
- **`session_cost` as hard gate**: it is a worst-case estimate. Prompt caching can make actual cost lower. Do not use it as a hard pass/fail gate.
- **`enable_experimental_hooks` missing**: without `enable_experimental_hooks = true`, all hooks are silently disabled. This field has `exclude=True` so it will not appear in auto-generated config. Workflows using hooks must assert this key is present.

## Design Implications

- Existing event usage is usually Tier A-C depending on whether code changes are needed.
- New event classes are Tier D unless the extension surface is already exposed.
- Any design requiring custom UI/ACP behavior must name both producer and consumer changes.
- Prefer OTEL `execute_tool` spans for per-tool proof (arguments and result are span attributes, correlation is automatic via baggage). Prefer session log JSONL for conversation-level audit. Do not use session log parsing for per-tool verification — it requires manual correlation of tool calls to results across messages.
- **`HookStartEvent` double-dispatch**: `HookStartEvent` has two consumers in the TUI path — the `VibeApp._handle_agent_loop_events` loop handles it directly to show a loading widget, and then passes it to `EventHandler.handle_event`. Any custom consumer wrapping the event stream must account for this double-dispatch pattern or the loading widget behavior will be lost.

## Proof Points

- Event emitted with expected fields.
- Event consumer handles it without crashing or ignoring critical state.
- Validation report includes trace/log evidence.
- Existing event paths still work.
