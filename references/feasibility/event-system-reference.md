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

The entire UI is a Textual app (`vibe/cli/textual_ui/`). Two layers to modify: Python widget files (structure/behavior) and `app.tcss` (styling).

### Layout Map

Top-level layout from `VibeApp.compose()`:

```
#chat (ChatScroll)
  └── Banner                          ← banner.py (cat + info line)
  └── #messages (VerticalGroup)       ← all chat messages mount here

#loading-area (Horizontal)
  ├── NarratorStatus                  ← narrator_status.py
  ├── #loading-area-content (Static)  ← LoadingWidget mounts here dynamically
  └── FeedbackBar                     ← feedback_bar.py

#bottom-app-container
  └── ChatInputContainer              ← chat_input/ directory

#bottom-bar (Horizontal)
  ├── PathDisplay                     ← path_display.py
  ├── #spacer
  └── ContextProgress                 ← context_progress.py
```

### Component Reference

| What you see | File | What to change |
|---|---|---|
| Banner (cat + model info) | `widgets/banner/banner.py` | `Banner.compose()` — add/remove/reorder widgets |
| Cat animation | `widgets/banner/petit_chat.py` | `STARTING_DOTS` (shape), `TRANSITIONS` (animation frames) |
| User messages | `widgets/messages.py` → `UserMessage` | `compose()` — layout, prefix chars |
| Assistant messages | `widgets/messages.py` → `AssistantMessage` | wraps a `Markdown` widget |
| Thinking/reasoning block | `widgets/messages.py` → `ReasoningMessage` | `SPINNING_TEXT`, `COMPLETED_TEXT`, triangle chars ▶▼ |
| Tool call display | `widgets/tools.py` | tool name/args rendering |
| Tool result display | `widgets/tool_widgets.py` | result formatting |
| Bash output block | `widgets/messages.py` → `BashOutputMessage` | prompt char `$`, border style |
| Error/warning blocks | `widgets/messages.py` → `ErrorMessage`, `WarningMessage` | prefix text, border |
| Interrupt message | `widgets/messages.py` → `InterruptMessage` | "Interrupted · What should Vibe do instead?" text |
| Spinner/status indicator | `widgets/status_message.py` | ✓/✕ chars, `SpinnerType` |
| Feedback bar | `widgets/feedback_bar.py` | `_prompt_text()` — "How is Vibe doing?" text |
| Bottom path display | `widgets/path_display.py` | path formatting |
| Context progress bar | `widgets/context_progress.py` | token usage display |
| "Load more" button | `widgets/load_more.py` | `_label_text()` |

### Styling

All CSS lives in `vibe/cli/textual_ui/app.tcss` — Textual's CSS dialect with `ansi_*` color tokens (respects terminal color scheme).

Key selectors:

| Selector | What it styles |
|---|---|
| `.reasoning-message-content` | thinking block text color/style |
| `.bash-prompt`, `.bash-command`, `.bash-output` | bash block |
| `.diff-added`, `.diff-removed`, `.diff-header` | diff colors |
| `.todo-pending`, `.todo-in_progress`, `.todo-completed` | todo item colors |
| `#bottom-bar`, `#loading-area` | bottom chrome layout |
| `.warning-content` | yellow warning text |
| `$mistral_orange: #FF8205` | the one named color variable |

### Four Core Widget Patterns

Understanding which pattern fits which display need is the key to working with the TUI.

**Pattern 1: `reactive` + `watch_*` — Live Status Displays**

Use when: a value changes over time and needs to auto-update without manual refresh calls.

How it works: Textual watches the reactive field. When you assign a new value, `watch_<field>()` fires automatically — update child widgets inside it.

`ContextProgress` — one reactive field, one watcher, one `update()` call:

```python
class ContextProgress(NoMarkupStatic):
    tokens = reactive(TokenState())

    def watch_tokens(self, new_state: TokenState) -> None:
        ratio = min(1, new_state.current_tokens / new_state.max_tokens)
        self.update(f"{ratio:.0%} of {new_state.max_tokens // 1000}k tokens")
```

`Banner` uses the same pattern with a dataclass as the reactive value and multiple child widgets updated in the watcher.

Use for: phase indicator, current agent name, token spend counter, hook status — any value pushed from outside.

**Pattern 2: `SpinnerMixin` — Working → Done Lifecycle**

Use when: anything with an "in progress" state that resolves to success or failure.

How it works: Mix `SpinnerMixin` into your `Static` subclass. Call `start_spinner_timer()` on mount. Call `stop_spinning(success=True/False)` when done. The mixin handles the frame loop, the ✓/✕ swap, and cleanup.

Three spinner types: `BRAILLE` (⠋⠙⠹...), `PULSE` (■■□□...), `SNAKE` (braille snake animation).

`StatusMessage` — ready-made widget composing a spinner icon + text label side by side.

`LoadingWidget` — extends further with color-cycling text animation and an elapsed timer.

Use for: hook execution status, phase transition indicator, any async operation with a clear end state.

**Pattern 3: `set_interval` Timer — Polling / Animated Displays**

Use when: anything that needs to animate or poll on a fixed cadence, independent of external events.

How it works: Call `self.set_interval(seconds, callback)` in `on_mount()`. The callback fires on the Textual event loop — safe to call `self.update()` from it. Store the returned `Timer` and call `.stop()` in `on_unmount()`.

`NarratorStatus` — animates bar characters at 150ms intervals while a state is active, stops the timer when idle:

```python
SHRINK_FRAMES = "█▇▆▅▄▃▂▁"
BAR_FRAMES = ["▂▅▇", "▃▆▅", "▅▃▇", "▇▂▅", "▅▇▃", "▃▅▆"]

def watch_state(self, new_state: NarratorState) -> None:
    self._stop_timer()
    match new_state:
        case NarratorState.IDLE:
            self.update("")
        case NarratorState.SUMMARIZING | NarratorState.SPEAKING:
            self._timer = self.set_interval(ANIMATION_INTERVAL, self._tick)
```

Use for: elapsed time counters, animated status bars, any display that ticks independently of LLM events.

**Pattern 4: Inline Chat Messages — Mounting into `#messages`**

Use when: information belongs in the conversation flow (tool results, phase transitions, validation output, warnings).

How it works: all chat content mounts into the `#messages` `VerticalGroup`. Existing message classes show the structural options:

| Class | Structure | Use for |
|---|---|---|
| `AssistantMessage` | Markdown renderer, streaming | Rich formatted output |
| `BashOutputMessage` | `$ cmd` header + output block | Command results |
| `InterruptMessage` | Border + plain text | Phase boundary markers |
| `WarningMessage` / `ErrorMessage` | Colored border + text | Hook failures, scope violations |
| `ReasoningMessage` | Collapsible header + Markdown | Long output collapsed by default |

`ReasoningMessage` is a useful template for collapsible sections — the ▶/▼ toggle, spinner-while-streaming header, and hidden-until-expanded content body are all reusable patterns (e.g., "Investigation Summary", "Validation Ledger").

### Where Each Display Type Belongs

| Location | What goes there | How |
|---|---|---|
| **Banner** (top, persistent) | Phase name, active model, run ID | Add fields to `BannerState` dataclass, update in `watch_state()` |
| **#loading-area** (below chat, transient) | Hook running, agent switching, git operations | Mount `LoadingWidget` or `StatusMessage`, remove when done |
| **#bottom-bar** (always visible) | Token spend, current branch, scope file count | Add a new reactive `Static` next to `ContextProgress` |
| **#messages** (inline, scrollable) | Validation results, review checklist, approval doc | Mount a `ReasoningMessage` or custom `Static` subclass |

### Adding a New Widget

1. Create a new file in `vibe/cli/textual_ui/widgets/`
2. Subclass `Static` or `Widget` from Textual
3. Import it in `app.py` and `yield` it inside `VibeApp.compose()` at the desired position
4. Add CSS rules to `app.tcss` targeting its ID or class

To mount dynamically inline with chat (e.g., a phase status widget), call `await self._mount_and_scroll(YourWidget())` from the event handler.

### Event-to-Widget Flow

```
AgentLoop emits event → VibeApp._handle_agent_loop_events
  → some events handled directly (HookStartEvent → loading widget)
  → all events passed to EventHandler.handle_event
    → maps to widget mutations in #messages container
```

**Double-dispatch:** Some events (notably `HookStartEvent`) are consumed by both `VibeApp` (for loading widget) and `EventHandler` (for display). Custom consumers must account for this or loading widget behavior is lost.

### Banner Modification

- **Change shape:** modify `STARTING_DOTS` in `petit_chat.py`. Each entry is a set of x-coordinates for that y-row. Complex numbers like `1j + 6` mean `y=1, x=6`.
- **Change/remove animation:** update or clear `TRANSITIONS`.
- **Replace entirely:** swap `yield PetitChat(animate=self._animated)` in `banner.py:57` for any other Textual widget.
- **Disable animation via config:** `disable_welcome_banner_animation: true` → `animate=False`, frozen on first frame.

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
