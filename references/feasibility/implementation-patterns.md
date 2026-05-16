# Verified Implementation Patterns

Source-confirmed recipes for the most common Mistral Vibe extension tasks. Every pattern here has been verified against the source code. Use these as starting points — do not invent variations without re-checking the source.

---

## Middleware Patterns

### Pattern 1: Stats-based STOP Guard

Check `context.stats` in `before_turn()`, return `STOP` with a reason string. `stats` exposes exactly three branchable values without source modification: `steps`, `session_cost`, `context_tokens`.

```python
async def before_turn(self, context: ConversationContext) -> MiddlewareResult:
    if context.stats.steps >= self.max_turns:
        return MiddlewareResult(
            action=MiddlewareAction.STOP,
            message=f"Turn limit reached ({self.max_turns})",
        )
    return MiddlewareResult(action=MiddlewareAction.CONTINUE)
```

Source: `middleware.py:49-62` (TurnLimitMiddleware), `middleware.py:65-78` (PriceLimitMiddleware)

---

### Pattern 2: Threshold-based COMPACT with Metadata

Return `COMPACT` with `metadata={"old_tokens": ..., "threshold": ...}`. The agent loop reads these keys to populate `CompactStartEvent`. If omitted, it falls back to current stats.

```python
async def before_turn(self, context: ConversationContext) -> MiddlewareResult:
    if context.stats.context_tokens >= self.threshold:
        return MiddlewareResult(
            action=MiddlewareAction.COMPACT,
            metadata={
                "old_tokens": context.stats.context_tokens,
                "threshold": self.threshold,
            },
        )
    return MiddlewareResult(action=MiddlewareAction.CONTINUE)
```

Source: `middleware.py:81-96` (AutoCompactMiddleware)

---

### Pattern 3: One-shot INJECT_MESSAGE with Boolean Flag

Inject exactly once per session using a `has_warned` boolean. Reset in `reset()` on **both** `STOP` and `COMPACT` — this is the production pattern for "warn once then stay silent."

```python
def __init__(self, threshold_fraction: float = 0.5):
    self.threshold_fraction = threshold_fraction
    self.has_warned = False

async def before_turn(self, context: ConversationContext) -> MiddlewareResult:
    if not self.has_warned and context.stats.context_tokens >= threshold:
        self.has_warned = True
        return MiddlewareResult(
            action=MiddlewareAction.INJECT_MESSAGE,
            message="Context is filling up — consider compacting.",
        )
    return MiddlewareResult(action=MiddlewareAction.CONTINUE)

def reset(self, reset_reason: ResetReason = ResetReason.STOP) -> None:
    self.has_warned = False  # reset on both STOP and COMPACT
```

Source: `middleware.py:99-125` (ContextWarningMiddleware)

---

### Pattern 4: Profile-aware Enter/Exit Injection

Track `_was_active` state. Inject on profile entry; inject an exit message on profile exit. The reminder can be a callable (evaluated lazily) or a plain string. After `reset()`, the next `before_turn()` re-injects if the profile is still active.

```python
def __init__(self, get_profile, target_profile, reminder, exit_message):
    self._get_profile = get_profile          # callable returning current profile name
    self._target_profile = target_profile    # profile name to watch
    self._reminder = reminder                # str or callable → str
    self._exit_message = exit_message        # str
    self._was_active = False

async def before_turn(self, context: ConversationContext) -> MiddlewareResult:
    is_active = self._get_profile() == self._target_profile
    if is_active and not self._was_active:
        self._was_active = True
        msg = self._reminder() if callable(self._reminder) else self._reminder
        return MiddlewareResult(action=MiddlewareAction.INJECT_MESSAGE, message=msg)
    if not is_active and self._was_active:
        self._was_active = False
        return MiddlewareResult(action=MiddlewareAction.INJECT_MESSAGE, message=self._exit_message)
    return MiddlewareResult(action=MiddlewareAction.CONTINUE)

def reset(self, reset_reason: ResetReason = ResetReason.STOP) -> None:
    self._was_active = False  # re-inject reminder on next before_turn after any reset
```

Source: `middleware.py:154-195` (ReadOnlyAgentMiddleware — used for both `plan` and `chat` profiles)

---

## Tool Patterns

### Pattern 5: Tool-triggered Profile Switch with Fallback

Prefer `ctx.switch_agent_callback` (triggers full `reload_with_initial_messages()` — rebuilds tools, skills, system prompt). Fall back to `ctx.agent_manager.switch_profile()` (does not rebuild). `switch_agent()` is idempotent: returns early if already on the target profile. Does **not** reset the middleware pipeline.

```python
async def run(self, args: MyArgs, ctx: InvokeContext) -> AsyncIterator:
    if ctx.switch_agent_callback:
        await ctx.switch_agent_callback("accept-edits")
    elif ctx.agent_manager:
        await ctx.agent_manager.switch_profile("accept-edits")
    yield MyResult(message="Switched to accept-edits mode")
```

Source: `exit_plan_mode.py:119-133`, `agent_loop.py:1576-1581`

---

### Pattern 6: Interactive Confirmation Before Profile Switch

Use `ctx.user_input_callback(AskUserQuestionArgs(...))` to get user confirmation before switching. Guard with `if ctx.user_input_callback is None: raise ToolError(...)` — this is how `exit_plan_mode` fails cleanly in headless contexts.

```python
async def run(self, args: MyArgs, ctx: InvokeContext) -> AsyncIterator:
    if ctx.user_input_callback is None:
        raise ToolError("This tool requires interactive confirmation and cannot run headless.")
    response = await ctx.user_input_callback(AskUserQuestionArgs(
        questions=[Question(text="Proceed?", choices=[Choice(label="Yes"), Choice(label="No")])],
        content_preview=args.plan_text,
    ))
    if response.answers[0] == "Yes":
        await ctx.switch_agent_callback("accept-edits")
    yield MyResult(message="User chose: " + response.answers[0])
```

Source: `exit_plan_mode.py:63-115`

---

### Pattern 7: Subagent Delegation with Scratchpad Forwarding

Create a fresh `AgentLoop` with `is_subagent=True` and `defer_heavy_init=True`. Pass the scratchpad path explicitly in the task text — it is **not** inherited automatically. Accumulate `AssistantEvent.content` into a list, join at the end.

```python
# The task tool does this internally. Key details for custom implementations:
# 1. is_subagent=True → scratchpad_dir=None, no hook pipeline
# 2. defer_heavy_init=True → skips expensive setup until act() is called
# 3. Scratchpad forwarding: prepend ctx.scratchpad_dir to the task text
task_text = f"Scratchpad dir: {ctx.scratchpad_dir}\n\n{args.task}" if ctx.scratchpad_dir else args.task
# 4. Accumulate result
result_parts = []
async for event in subagent_loop.act(task_text):
    if isinstance(event, AssistantEvent):
        result_parts.append(event.content)
result = "\n".join(result_parts)
```

Source: `task.py:127-185`

---

### Pattern 8: Allowlist/Denylist Permission Resolution in Tools

Override `resolve_permission()` to check `fnmatch` patterns against args. Return `PermissionContext(permission=ToolPermission.ALWAYS)` for allowlist matches, `NEVER` for denylist. Return `None` to fall through to config permission.

```python
def resolve_permission(self, args: MyArgs, ctx: InvokeContext) -> PermissionContext | None:
    path = args.path
    for pattern in self._config.denylist:
        if fnmatch.fnmatch(path, pattern):
            return PermissionContext(permission=ToolPermission.NEVER)
    for pattern in self._config.allowlist:
        if fnmatch.fnmatch(path, pattern):
            return PermissionContext(permission=ToolPermission.ALWAYS)
    return None  # fall through to BaseToolConfig.permission
```

Source: `task.py:94-105`

---

### Pattern 9: get_file_snapshot() for Rewind Support

Call `self.get_file_snapshot_for_path(args.path)` to capture file state before modification. The agent loop calls `get_file_snapshot()` before `invoke()` and registers the snapshot with `RewindManager`. Return `None` to opt out.

```python
def get_file_snapshot(self, args: MyArgs) -> FileSnapshot | None:
    return self.get_file_snapshot_for_path(args.path)
```

Source: `write_file.py:82-83`, `agent_loop.py:954-956`

---

### Pattern 10: sensitive_patterns for Always-Ask Overrides

Set `sensitive_patterns` in your tool config to patterns that trigger `ASK` even when `permission = "always"`. Production default for file-writing tools: `["**/.env", "**/.env.*"]`. This protects specific file patterns without disabling auto-approve globally.

```python
class MyToolConfig(BaseToolConfig):
    sensitive_patterns: list[str] = ["**/.env", "**/.env.*", "**/secrets/**"]
```

Source: `write_file.py:41-47`

---

### Pattern 13: Tool Config Merging from TOML

`ToolManager.get_tool_config()` merges the tool's default config with user overrides from `config.tools[tool_name]`. The merge is `{**default.model_dump(), **user_overrides}`. Any field in a `BaseToolConfig` subclass can be overridden from `config.toml` under `[tools.<tool_name>]`.

```toml
[tools.my_custom_tool]
permission = "always"
allowlist = ["/safe/path/**"]
my_custom_field = "overridden_value"
```

Source: `manager.py:395-411`

---

### Pattern 14: Tool Instance Lifecycle

`ToolManager.get()` creates instances on first call and caches them in `_instances`. The same instance is reused for all calls within a session. Instance-level state persists across tool calls within the same session. **State is lost on `reload_with_initial_messages()`** — which creates a new `ToolManager`. Design tools to not depend on state surviving a profile switch or compaction.

Source: `manager.py:413-431`

---

### Pattern 15: is_available() Filters Before enabled_tools/disabled_tools

`available_tools` calls `cls.is_available()` first, then applies per-source filtering, then `enabled_tools`/`disabled_tools`. A tool returning `False` from `is_available()` is never in the model's tool list regardless of config. Use for binary-dependency checks.

```python
@classmethod
def is_available(cls) -> bool:
    return shutil.which("ripgrep") is not None  # only available when rg is installed
```

Source: `manager.py:194-216`

---

## Hook Patterns

### Pattern 11: Hook Retry with exit 2 + stdout

Full retry chain:
- `exit 2` + non-empty stdout → inject stdout as `role: user` message, break hook chain for this turn, loop again (middleware fires on re-entry)
- `exit 2` + empty stdout → warning only, no retry
- Any other non-zero → warning with stdout/stderr, no retry
- Timeout (default 30s) → warning, no retry regardless of exit code

Retries are tracked per hook name, reset per user turn. `_MAX_RETRIES = 3`.

```bash
#!/bin/bash
# Hook script — read session context from stdin
payload=$(cat)
transcript=$(echo "$payload" | python3 -c "import sys,json; print(json.load(sys.stdin)['transcript_path'])")

# Check output, inject feedback if needed
if ! check_output "$transcript"; then
    echo "Output failed quality check: missing required section X"  # stdout → injected as user message
    exit 2
fi
exit 0
```

Source: `manager.py:79-125`

---

### Pattern 12: Hooks in Programmatic Mode

`run_programmatic()` accepts `hook_config_result: HookConfigResult | None` — hooks can run in programmatic mode if passed explicitly. Default is `None` (no hooks). When `stopped_by_middleware=True`, `run_programmatic()` raises `ConversationLimitException`.

```python
from vibe.core.hooks.config import load_hooks_from_fs

hook_config = load_hooks_from_fs()  # loads from ~/.vibe/hooks.toml + .vibe/hooks.toml
result = run_programmatic(
    prompt="...",
    hook_config_result=hook_config,   # hooks active in programmatic mode
)
# ConversationLimitException raised if middleware stops the loop
```

Source: `programmatic.py:27-57`, `programmatic.py:86-91`

---

### Pattern 16: Forced Tool Choice Override

`get_tool_choice()` is hardcoded to `"auto"` — the model decides each turn whether to call a tool or emit text. There is no config-level or tool-level mechanism to force a tool call. When a workflow reaches a point where a specific tool *must* be called (a phase-advance tool, a gate-check tool, a checkpoint tool), the model can silently emit text instead and the workflow stalls with no error.

**General mechanism:**

1. Add a `_forced_tool_choice` instance variable to `AgentLoop`, typed as `StrToolChoice | AvailableTool | None`, default `None`.
2. In `_chat()` and `_chat_streaming()`, consume it before falling through:
   ```python
   tool_choice = self._forced_tool_choice if self._forced_tool_choice is not None \
                 else self.format_handler.get_tool_choice()
   self._forced_tool_choice = None  # consume after one use
   ```
3. At the enforcement point, resolve the target tool class from `ToolManager.available_tools` and construct an `AvailableTool` with the specific function name. Fall back to `"required"` if the tool isn't in the schema.
4. Inject a user-role reminder message alongside setting the forced choice.

**Why consumption-on-read is safe:** The forced choice applies to exactly one LLM turn. If the tool call fails (returns a `ToolResult` with an error), the loop continues normally — the model gets a free, unforced turn to fix blocking conditions. This prevents the "trapped" failure mode where a forced tool fails and the model has no escape path.

**When to use:** Any workflow with a mandatory transition point where a specific tool must be called and text output would stall the workflow.

**When not to use:** For general "the model should probably call a tool" guidance. That belongs in the system prompt or skill text. Forced choice is for mechanically enforced transitions.

**Tier:** D (source changes to `agent_loop.py`).

Source: `agent_loop.py:1139-1147`, `agent_loop.py:1207-1215`, `format.py:63-73`

---

### Pattern 17: Phase Advance Enforcement with Retry Cap

When a workflow phase completes, the model must call a specific transition tool to advance. Without enforcement, the model may emit text and stall. This pattern combines middleware STOP detection, message injection, forced tool choice, and profile-change verification.

**Mechanism:**

```python
_MAX_ADVANCE_REMINDERS = 3
_advance_reminder_count = 0
_profile_before = self.agent_profile.name

# In _conversation_loop, when middleware signals STOP:
if (
    should_break_loop
    and _advance_reminder_count < _MAX_ADVANCE_REMINDERS
):
    _advance_reminder_count += 1
    # Force the transition tool on the next turn
    target_cls = self.tool_manager.available_tools.get("<transition_tool_name>")
    if target_cls:
        self._forced_tool_choice = AvailableTool(
            function=AvailableFunction(
                name=target_cls.get_name(),
                description=target_cls.description,
                parameters=target_cls.get_parameters(),
            )
        )
    else:
        self._forced_tool_choice = "required"
    self.messages.append(LLMMessage(
        role=Role.user,
        content="[SYSTEM] Call <transition_tool_name> now to advance.",
        injected=True,
    ))
    should_break_loop = False

# After the turn, verify the profile actually changed
if self.agent_profile.name != _profile_before:
    _advance_reminder_count = 0  # reset for next phase
```

**Why this works:** The forced choice is consumed after one use. If the transition tool fails, the model gets a free turn to fix blocking conditions. The retry cap prevents infinite reminder loops. Profile-change verification ensures the enforcement stops once the transition succeeds.

**Tier:** D (source changes to `agent_loop.py`; depends on Pattern 16).

Source: `agent_loop.py:807-828`, `agent_loop.py:1139-1147`

---

### Pattern 18: Subagent Delegation with Result Validation and Fallback

The parent agent issues `task()` calls and must handle incomplete results. `TaskResult.completed = False` fires on middleware stops, skipped tool calls, and unhandled exceptions — the parent will not act on it unless the prompt explicitly checks.

**Mechanism:**

```python
# Parent issues subagent task
result = task(task="Analyze the codebase for X", agent="explore")

# Check completion — do not assume success
if not result.completed:
    # Read response for error detail (don't just check completed)
    if "rate limit" in result.response.lower():
        # Retry with backoff
        result = task(task="Analyze the codebase for X", agent="explore")
    elif "turn limit" in result.response.lower():
        # Split the task into smaller chunks
        ...
    else:
        # Fail with evidence
        raise WorkflowError(f"Subagent failed: {result.response}")

# Only proceed with valid results
process(result.response)
```

**Key detail:** Always read `result.response` when `completed = False`. The response contains the error detail — whether it was a middleware stop, a skipped tool, or an unhandled exception. Callers that only check `completed` without reading `response` will miss the error cause.

**Tier:** A (built-in `explore`) or B (custom subagent profiles).

Source: `task.py:127-185`

---

### Pattern 19: Compaction-Safe and Switch-Safe State Persistence

Both context compaction and agent profile switches can destroy in-memory state. Compaction resets the session ID and rebuilds the message list. Profile switches create a new `ToolManager` (wiping `todo` state) and rebuild the backend. State held only in memory is lost in both cases.

**General pattern:**

```python
# Before any operation that might trigger compaction or profile switch:
state = {
    "phase": current_phase,
    "completed_steps": steps_done,
    "evidence": evidence_files,
    "pending_actions": remaining,
}
write_state_file(state, ".workflow-state.json")

# After the operation (compaction or switch), read it back:
state = read_state_file(".workflow-state.json")
if state is None:
    # State lost — fail with evidence, do not silently restart
    raise WorkflowError("State file missing after context operation")
validate_state_integrity(state)  # check required fields exist
```

**Where to write:** Use a deterministic path in the project directory (`.workflow-state.json`) or the scratchpad. Never rely on `todo` state surviving a profile switch. Never rely on in-memory variables surviving compaction.

**What this means for workflow designers:** Any workflow that spans multiple phases with profile switches must persist state to disk at each phase boundary. The state file is the only cross-switch, cross-compaction continuity mechanism available to the LLM.

**Tier:** A (file I/O via built-in tools).

Source: `agent_loop.py` (reload_with_initial_messages), `middleware.py` (AutoCompactMiddleware)

---

### Pattern 20: Profile Switch with Visible Confirmation

`AgentProfileChangedEvent` is silently dropped by the ACP layer. The TUI only calls `on_profile_changed`, which typically updates the status bar — no in-chat indication. If the user isn't watching the status bar, they never know the profile (and therefore the active model, tool set, and system prompt) changed.

**Pattern:** Tools that trigger a profile switch via `ctx.switch_agent_callback` should yield a human-readable confirmation string as their result. Since the tool result is shown in the chat as a `ToolResultEvent`, this is free — no event system changes needed.

```python
async def run(self, args: MyArgs, ctx: InvokeContext) -> AsyncIterator:
    old_profile = ctx.agent_manager.active_profile.name if ctx.agent_manager else "unknown"
    if ctx.switch_agent_callback:
        await ctx.switch_agent_callback(args.target_profile)
    yield MyResult(
        message=f"Profile changed: {old_profile} → {args.target_profile} "
                f"(model: {ctx.agent_manager.active_profile.active_model})"
    )
```

**Why this matters:** Profile changes affect the model, tool availability, system prompt, and permission boundaries. An invisible change means the user doesn't know why the agent suddenly can't call certain tools, or why response quality changed.

**Tier:** B (tool-level; no source changes needed if the tool already exists).

Source: `event_handler.py:111-113`, `agent_loop.py:1576-1581`

---

### Pattern 21: Source Modification Verification (Hard Invariant)

This is not a pattern for a specific extension — it is a **meta-pattern that governs ALL Tier D changes**. Any modification to `vibe/core/` source files (AgentLoop, middleware, tools, events, session, hooks, format, etc.) is incomplete until tests have been constructed and run that verify the modification works as intended.

**The invariant:**

> Any custom modification to source that deviates from upstream MUST be verified as working. You MUST construct and run actual tests against the source changes to verify that the unique changes added work as intended.

**Why this is non-negotiable:**
- Source patches to `vibe/core/` are not covered by upstream tests — upstream tests verify upstream behavior, not your custom behavior.
- A modification that "looks correct" can silently break under concurrency, after compaction, on profile switch, or when an edge case the author did not consider is hit.
- Without a test, the only way to verify the change is to run the full workflow and observe — which is manual, slow, and unreliable.
- On the next Vibe update, your patch may be silently overwritten or conflict with new behavior. A test detects this immediately.

**Minimum test requirements:**

Every source modification MUST include tests that satisfy ALL of the following:

1. **Exercise the modified code path.** The test must call the specific function/method/behavior that was changed, not just import the module.
2. **Assert expected behavior.** The test must have explicit assertions about what the modification does — not just "it doesn't crash."
3. **Fail on regression.** If the modification is reverted, broken, or overwritten, the test MUST fail. A test that always passes is not a test.
4. **Be independently runnable.** The test must be runnable without the full Vibe runtime — unit tests with mocks, targeted script-level verification, or integration tests with a test harness. "Run the full agent and watch the output" is not a test.

**Test construction process:**

```python
# Step 1: Identify what you changed and what it should do.
# Example: "Added _forced_tool_choice to AgentLoop. When set, _chat() should
#          pass it to the LLM backend instead of 'auto', then clear it."

# Step 2: Write a test that exercises exactly that behavior.
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from vibe.core.agent_loop import AgentLoop

class TestForcedToolChoice(unittest.TestCase):
    def test_forced_choice_overrides_auto(self):
        """_chat() must use _forced_tool_choice when set, then clear it."""
        loop = AgentLoop.__new__(AgentLoop)
        loop._forced_tool_choice = AvailableTool(
            function=AvailableFunction(name="my_tool", description="...", parameters={})
        )
        loop.format_handler = MagicMock()
        loop.format_handler.get_tool_choice.return_value = "auto"

        mock_backend = AsyncMock()
        mock_backend.chat.return_value = iter([])

        with patch.object(loop, '_make_request', new=mock_backend.chat):
            # ... drive _chat() and assert the forced choice was passed
            pass

        # Assert: _forced_tool_choice was consumed (set to None after use)
        self.assertIsNone(loop._forced_tool_choice)

    def test_forced_choice_cleared_on_failure(self):
        """_forced_tool_choice must be consumed even if the LLM call fails."""
        # ... test that the choice is cleared even on exception
        pass

# Step 3: Run the test. It MUST pass. If it fails, fix the source, not the test.
# Step 4: Include the test file in the deliverable alongside the source change.
```

**What counts as a valid test:**

| Test type | Valid? | Notes |
|---|---|---|
| `unittest.TestCase` with mocks | Yes | Preferred for unit-level changes |
| `pytest` function with fixtures | Yes | Equivalent to unittest |
| Standalone script that exercises the change and exits 0/1 | Yes | Minimum acceptable — must have assertions |
| Script that prints output for manual inspection | No | Not automated, not assertable |
| "Run the full workflow and observe" | No | Too slow, too broad, not repeatable |
| Upstream test that happens to import the module | No | Upstream tests verify upstream behavior, not your change |

**Where to place tests:**

- `vibe/core/tests/` — for unit tests of specific modules
- `vibe/tests/integration/` — for integration tests that exercise multiple components
- A standalone `test_<feature>.py` in the project root — acceptable for workflow-specific verification scripts

**Tier:** D+ (applies to all Tier D changes; without tests, the change is incomplete and must not be marked DONE).

**This pattern references:** `runtime-pattern-catalog.md` anti-pattern "Source modification without constructed tests", `extension-point-taxonomy.md` Tier D constraints.
