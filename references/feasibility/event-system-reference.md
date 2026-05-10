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

**Mitigation for profile switches without ACP source changes:** Tools that trigger a profile switch via `ctx.switch_agent_callback` should yield a human-readable confirmation string as their result (e.g., `"Profile changed: plan → implement (model: mistral-large)"`). Since the tool result is displayed in the chat as a `ToolResultEvent`, this provides visible confirmation to the user without requiring ACP layer changes. This is a Tier B workaround for a Tier D gap.

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
- **`RateLimitError` kills the turn — no turn-level retry**: the backend has `@async_retry(tries=3)` at the HTTP request level, but `_chat()` and `_chat_streaming()` catch exceptions and immediately raise `RateLimitError`. There is no turn-level retry loop. The error propagates to the UI and the turn ends. Free-tier models with tight rate limits will kill mid-phase. This is not a recoverable error within the session.
- **`MissingPromptFileError` is a hard crash**: if `system_prompt_id` in any agent profile TOML points to a non-existent file in `~/.vibe/prompts/`, the runtime raises `MissingPromptFileError` at config load. The agent cannot start. This is not a warning or a fallback — it is a hard blocker. Every custom prompt file must be deployed before the profile that references it is used.
- **Compaction triggers an extra `count_tokens` LLM call**: after `compact()` summarizes history, it calls `backend.count_tokens()`. For `GenericBackend` (OpenRouter), this is a second full LLM call with `max_tokens=16`. Every compaction costs 2 API calls, not 1. This matters for free-tier budgets and rate limit headroom.

## TUI Surface Reference

The Textual UI (`vibe/cli/textual_ui/`) is a consumer of the event stream. When modifying events or adding new ones, the TUI must be updated alongside ACP.

**Key files:**

| File | Role |
|---|---|
| `vibe/cli/textual_ui/app.py` | `VibeApp` — main Textual app, receives events from `AgentLoop` via `_handle_agent_loop_events` |
| `vibe/cli/textual_ui/handlers/event_handler.py` | `EventHandler` — maps events to widget mutations (tool call/result widgets, assistant messages, compact indicators) |
| `vibe/cli/textual_ui/widgets/banner/banner.py` | `Banner` — top-of-screen composable: info text + `PetitChat` widget inside a `Horizontal` container (`id=banner-container`) |
| `vibe/cli/textual_ui/widgets/banner/petit_chat.py` | `PetitChat` — animated braille-art widget. Shape defined by `STARTING_DOTS` (list of sets of x-coords per row). Animation via `TRANSITIONS` (add/remove dot ops every 160ms). Rendered via `render_braille()` from `braille_renderer.py`. Controlled by `disable_welcome_banner_animation` config — when `True`, `animate=False` and the widget stays frozen on the first frame. |

**Modifying the banner:**

- To change the shape: modify `STARTING_DOTS` in `petit_chat.py`. Each entry is a set of x-coordinates for that y-row. Complex numbers like `1j + 6` mean `y=1, x=6`.
- To change or remove animation: update/clear `TRANSITIONS`.
- To replace the banner entirely: swap `yield PetitChat(animate=self._animated)` in `banner.py:57` for any other Textual widget (e.g., a `Static` with plain text or ASCII art).

**Event-to-widget flow:**

```
AgentLoop emits event → VibeApp._handle_agent_loop_events
  → some events handled directly (HookStartEvent → loading widget)
  → all events passed to EventHandler.handle_event
    → maps to widget mutations in the chat container
```

**Double-dispatch:** Some events (notably `HookStartEvent`) are consumed by both `VibeApp` (for loading widget) and `EventHandler` (for display). Custom consumers must account for this or loading widget behavior is lost.

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
