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
