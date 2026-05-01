# Runtime Pattern Catalog

This catalog describes valid Mistral Vibe workflow extension patterns. Use it to select the smallest correct runtime surface for a requirement. Do not treat this as a menu of everything to include.

## Selection Principle

For each requirement:

1. Identify what must happen.
2. Pick the smallest runtime surface that can reliably provide that capability.
3. Record why stronger surfaces were rejected.
4. Validate selected surfaces with implementation and proof.

Prefer native runtime primitives before custom surfaces. In particular, structured user decisions should use `ask_user_question`, plan-to-apply gates should use `exit_plan_mode`, session progress should use `todo`, intermediate files should use scratchpad, and CI evidence should use programmatic JSON output when applicable.

## Skills

**Valid roles**

- guided workflow procedure
- user-invocable behavior
- domain/process instruction
- prompt scaffold
- tool availability boundary through `allowed_tools`

**Important capability**

Skill metadata includes `allowed_tools`, but this field is **advisory only and not enforced at the tool-availability level**. The model sees all available tools regardless of what `allowed_tools` declares. The field is parsed into `SkillMetadata` but is never used to filter `ToolManager.available_tools`. Treating `allowed_tools` as a hard access boundary will silently fail. Use agent profile `overrides.enabled_tools` when actual tool restriction is needed.

**Not valid for**

- enforcing arbitrary runtime behavior beyond supported skill metadata
- changing AgentLoop policy
- post-tool interception
- restricting tool access (use agent profile `overrides` instead)

**Fit checks**

- If a requirement needs deterministic execution, pair the skill with a tool/MCP/connector instead of relying on prompt text.
- If a requirement needs actual tool restriction, use agent profile TOML `overrides` dict with `enabled_tools`, not `allowed_tools`.

## Tools

**Valid roles**

- structured user clarification and approval through `ask_user_question`
- canonical plan-to-implementation gate through `exit_plan_mode`
- session-scoped phase tracking through `todo`
- agent-as-tool delegation through `task`
- deterministic action
- structured repo/file operation
- external API call
- web/documentation research through `webfetch` and `websearch`
- validation/test runner
- controlled permission boundary
- post-execution context injection through `get_result_extra()`
- stateful capability through `BaseToolState`
- profile orchestration through `InvokeContext.switch_agent_callback`
- tool-specific system prompt guidance through `get_tool_prompt()` / `prompt_path`

**Important capabilities**

- `resolve_permission()` can provide per-invocation permission overrides before config-level permission.
- `BaseToolConfig` supports `permission`, `allowlist`, `denylist`, and `sensitive_patterns`.
- `get_result_extra()` injects extra LLM context after a tool result; this is not middleware.
- `BaseToolState` supports stateful tool instances within a session.
- `get_tool_prompt()` / `prompt_path` can inject tool-specific prompt text into the system prompt.
- `InvokeContext.switch_agent_callback` lets a tool trigger a supported profile switch.

**Tool discovery order**: `ToolManager` builds the search path as `[DEFAULT_TOOL_DIR, *config.tool_paths, *project_tools_dirs, *user_tools_dirs]` and iterates in order — later entries overwrite earlier ones in the `_available` dict. Custom tools in `config.tool_paths` **override built-ins**, not the other way around. Tool discovery is recursive (`rglob("*.py")`) — all subdirectories of each path are searched.

**Non-obvious behaviors**

- **Parallel tool execution within a turn**: tools emitted in the same LLM response are executed concurrently. Data-dependent tool calls (read file A, then use its content to decide what to write to file B) must be split across separate LLM turns, not parallel calls in one response. Workflow designs that assume sequential in-turn execution will silently run concurrently.

**Not valid for**

- changing when AgentLoop asks for tools
- acting before every LLM turn
- replacing middleware or source changes for runtime policy changes

**Fit checks**

- Use tool config overrides before source changes when the need is permission, allowlist, denylist, or sensitive-pattern control.
- Use `get_result_extra()` for post-tool context injection instead of inventing post-tool middleware.
- Use tool state only for session-local state, not cross-session persistence.
- Use profile switching only through supported callback/profile behavior, not invented autonomous roles.

## Built-In Workflow Tools

### `ask_user_question`

Use this for approval gates, intake forms, and ambiguity clarification.

**Supported shape**

- 1-4 questions shown as tabs
- 2-4 choices per question
- each choice has label and description
- `multi_select: true` for multi-choice answers
- `hide_other: false` automatically adds a free-text "Other" option
- `content_preview` shows scrollable context above the questions

Prefer this over generic prose like "ask the user" when the workflow needs a structured decision.

**`ask_user_question` is disabled in programmatic and ACP modes**: the CLI adds it to `disabled_tools` when running with `--prompt`, and the ACP layer also loads config with `disabled_tools=["ask_user_question"]`. Any workflow using `ask_user_question` must document that it is unavailable in both headless CLI and ACP contexts.

Good uses:

- approval gate with the proposed plan in `content_preview`
- ambiguity clarification with 2-4 contextual options
- intake form where the user may select multiple constraints
- "Other" escape hatch when the design space is not closed

### `exit_plan_mode`

Use this as the canonical plan-to-implementation gate. It shows the plan as a `content_preview` and lets the user choose implementation mode, default mode, or staying in plan mode.

This is usually better than inventing a custom approval step between planning and applying edits.

Use this for workflows that follow the plan-then-implement pattern: write the plan, show it with `content_preview`, then let the user choose `accept-edits`, `default`, or stay in plan mode.

### `todo`

Use this for session-scoped workflow state: phase status, blockers, and priorities. It is in-memory and persists across turns within a session.

Use files only when the state must survive across sessions, become audit evidence, or be consumed by external tooling.

Each item has status such as `pending`, `in_progress`, `completed`, or `cancelled`, and priority such as `low`, `medium`, or `high`.

**Non-obvious behaviors**

- **Write replaces the entire list**: `todo(action="write", todos=[...])` replaces the full list, not appends to it. If the list is `[A, B]` and you write `[A]`, `B` is silently gone. The model must always pass the complete desired list.
- **Wiped on agent profile switch**: todo state lives on the tool instance. `switch_agent` creates a new `ToolManager`, which creates a new `Todo` with an empty list. Todo state does not survive profile switches.

### Scratchpad

Use the session scratchpad for intermediate artifacts, draft manifests, temporary evidence, and validation outputs that should not clutter the project tree. Scratchpad files are auto-allowed and the parent's `scratchpad_dir` path is passed to subagents via `InvokeContext`.

Do not use scratchpad for canonical lifecycle records that need to persist in the project.

**Non-obvious behaviors**

- **Temp directory, not project-relative**: the scratchpad is created with `tempfile.mkdtemp()` — it lives in the OS temp directory. Its path is non-deterministic across sessions. Do not treat it as a stable or project-relative path.
- **Subagents have no independent scratchpad**: `scratchpad_dir = None` when `is_subagent=True`. The parent's scratchpad path is passed via `InvokeContext.scratchpad_dir` to the task tool context, but the subagent's `AgentLoop` itself has no scratchpad. Workflows assuming subagents get their own isolated scratchpad will break.

### `task` Subagents

Use `task` for parallel or specialized read/analysis work. Custom subagents are possible when configured with `agent_type = "subagent"`.

**Design constraint:** subagents return text to the parent. The built-in `explore` subagent is read-only by profile — it cannot write files. This is a profile-level restriction, not a hard runtime constraint on all subagents. A custom subagent with `agent_type = "subagent"` and a permissive profile could write files. The correct pattern is still: subagent returns analysis, parent writes files — but the rationale is sound workflow design, not an enforced runtime block.

Custom subagents are config-level agent profiles with `agent_type = "subagent"`, a system prompt, model, and tool set. This is more specific than a generic "agent role."

Good uses:

- read-only research
- validator returning findings
- planner/reviewer returning a proposal
- parallel source exploration

Bad uses:

- subagent directly generating project files (write responsibility belongs to parent)
- subagent owning persistent workflow state
- subagent used where a profile switch or tool permission scope is enough

**Non-obvious behaviors**

- **Scratchpad path is passed as text, not as an auto-allow**: the parent's scratchpad path is prepended to the task prompt as a plain string. The subagent's `AgentLoop` has `scratchpad_dir = None` — it has no scratchpad of its own and the system prompt does not include the scratchpad section. Whether writes to that path are permitted depends on the parent's approval callback, not an inherent auto-allow mechanism. Treat scratchpad access in subagents as prompt-guided, not permission-guaranteed.
- **Config isolation**: subagents get a fresh `VibeConfig.load()` — they do not inherit the parent's runtime config overrides. Permission mutations the parent made at runtime are invisible to the subagent.
- **Custom subagents default to `ASK` permission**: only `explore` is in the default `TaskToolConfig.allowlist`. Any custom subagent falls through to config-level `ASK` permission and will prompt on every `task` call in auto-approve contexts unless explicitly added to the allowlist.
- **`completed: False` is silent to the LLM**: when a subagent is stopped by middleware (turn limit, price limit), `TaskResult.completed = False` is just text in the tool result. The parent agent will not act on it unless the workflow prompt explicitly checks for it. Subagent workflows using turn or price limits must include a prompt instruction to handle incomplete results.
- **Parallel subagents require multiple tool calls in one turn**: the `task` tool runs one subagent per call. Parallelism requires the LLM to emit multiple `task` tool calls in the same response turn (which the runtime supports via parallel tool execution). A single `task` call does not spawn parallel work; the design must prompt the model to issue concurrent calls.

### `webfetch` / `websearch`

Use `webfetch` to fetch a known URL and convert HTML to markdown. Use `websearch` for external web search through Mistral's search integration.

Good uses:

- current external API docs
- PR/release notes or issue pages
- third-party service behavior
- research phases when source captures are missing or stale

Do not rely on implicit model knowledge when the workflow needs current external facts.

## Remote Tools: MCP And Mistral Connectors

**Valid roles**

- external capability bridge
- multi-tool service integration
- service boundary for HTTP/stdio/streamable HTTP capabilities
- Mistral Connector API-backed remote tools through `ConnectorRegistry`

**Important distinction**

MCP and Mistral Connectors are both remote tool surfaces, but they are not the same mechanism. MCP uses configured MCP servers. Connectors use Mistral connector integration through the tool manager.

MCP server config can include:

- `prompt`: usage hint appended to tool descriptions
- `sampling_enabled`: permits the MCP server to request LLM completions

Use `prompt` when the agent needs guidance on when a remote tool is appropriate. Treat `sampling_enabled` as a meaningful escalation: the server can request model completions, so the design must justify that capability.

**Non-obvious behaviors**

- **`sampling_enabled` defaults to `True`**: every configured MCP server can request LLM completions by default. This is not opt-in. Workflows that do not need MCP-initiated model completions should explicitly set `sampling_enabled = false`. The design should account for any MCP server where `sampling_enabled` is left at the default.

**Not valid for**

- hidden control flow
- replacing workflow state
- bypassing permission/safety modeling

## Middleware

**Valid roles**

- pre-LLM-turn gate
- context injector through `MiddlewareAction.INJECT_MESSAGE`
- stop condition through `MiddlewareAction.STOP`
- compaction trigger through `MiddlewareAction.COMPACT`
- budget/turn/context guard
- read-only reminder or safety reminder
- per-LLM-call orchestration hint before the model acts

**Extension boundary**

Custom middleware is valid. A workflow may define multiple middleware classes that each do different pre-turn work: gating, context injection, compaction decisions, read-only reminders, turn/budget limits, or workflow phase reminders.

The constraint is where custom middleware lives and how it is registered. Middleware is internal Python. Normal skills, config, hooks, and workflow manifests do not register arbitrary custom middleware by themselves. A design that creates new middleware is a source-level/runtime-code extension unless it is only configuring/using built-in middleware already exposed by the runtime.

**Protocol**

Middleware has one runtime hook for active behavior:

```python
async def before_turn(context: ConversationContext) -> MiddlewareResult: ...
```

It also has `reset(reset_reason)` for lifecycle reset. There is no `after_turn`, `after_tool`, `on_event`, `pre_tool`, or `post_tool`.

`before_turn()` fires before every LLM call in a multi-step tool loop, not just once per user message.

**Pipeline semantics**

- `INJECT_MESSAGE` results compose additively.
- `STOP` returns immediately and short-circuits later middleware.
- `COMPACT` returns immediately and short-circuits later middleware.
- Middleware ordering matters when STOP/COMPACT-capable middleware is mixed with injectors.
- Multiple middleware are valid when each has a clear pre-turn responsibility and ordering rationale.

**Non-obvious behaviors**

- **Accumulated injections are dropped on STOP/COMPACT**: `INJECT_MESSAGE` results from earlier middlewares accumulate, but if any later middleware returns `STOP` or `COMPACT`, all previously accumulated injections are silently discarded. If middleware A injects and middleware B stops, A's message is dropped entirely.
- **`ConversationContext` field inventory**: the context object has exactly three fields: `messages` (full message list), `stats` (`AgentStats`), and `config` (`VibeConfig`). There is no `tool_results`, `last_tool_name`, or `turn_number` field. `AgentStats` exposes `steps`, `session_cost`, `context_tokens`, `tool_calls_agreed`, `tool_calls_rejected`, `tool_calls_failed`, `tool_calls_succeeded`. Use `stats.steps` as a turn-count proxy.
- **`TurnLimitMiddleware` step semantics**: the check is `stats.steps - 1 >= max_turns`. `stats.steps` is incremented twice per user message (once on append, once at each LLM turn start). `max_turns=1` means one LLM call. Setting `max_turns` based on "number of tool calls" or "number of user messages" will produce the wrong count.
- **Built-in pipeline order**: `TurnLimitMiddleware` (only if `max_turns` set) → `PriceLimitMiddleware` (only if `max_price` set) → `AutoCompactMiddleware` → `ContextWarningMiddleware` (only if `context_warnings = true`) → `ReadOnlyAgentMiddleware` (plan) → `ReadOnlyAgentMiddleware` (chat). The default pipeline is just `AutoCompactMiddleware` + two `ReadOnlyAgentMiddleware` instances. Custom middleware added at runtime appends after these. Since `STOP`/`COMPACT` short-circuit, placement before `AutoCompactMiddleware` means the custom middleware can prevent compaction from firing.
- **Compaction re-injects plan reminder**: after compaction, `ReadOnlyAgentMiddleware` resets `_was_active = False`. On the next turn in plan mode the full plan reminder is re-injected. Workflows that compact frequently in plan mode will see the reminder re-injected after each compaction.
- **Transition-only injection**: `ReadOnlyAgentMiddleware` injects only on profile entry and exit, not on every turn. There is no per-turn reminder after the initial injection. Mid-session drift from plan-mode constraints is not automatically corrected.
- **`ContextWarningMiddleware` fires once**: the warning fires when `context_tokens >= auto_compact_threshold * 0.5`, then `has_warned = True` until compaction or session reset. Only active when `context_warnings = true` (default `false`). If `auto_compact_threshold` is 0, the warning never fires. Workflows using the warning as a signal will receive it exactly once per session.

**Not valid for**

- post-tool interception
- during-tool execution
- arbitrary event handling
- changing tool execution logic without source changes

## Agent Profiles

**Valid roles**

- supported profile switching among real profiles: `default`, `plan`, `accept-edits`, `auto-approve`, `chat`
- read-only reminder behavior through middleware tied to a profile name
- tool-triggered profile switch via `InvokeContext.switch_agent_callback`

**`chat` profile**

The `chat` profile is a built-in read-only conversational mode. Its overrides set `bypass_tool_permissions = true` and `enabled_tools = ["grep", "read_file", "ask_user_question", "task"]` — a specific fixed list, not all read-only tools. `bash`, `write_file`, `search_replace`, and all MCP tools are excluded. A middleware reminder is injected on profile entry that file edits and non-listed tools are blocked; a matching exit reminder fires when leaving chat mode.

**`lean` builtin agent**: a built-in agent with `install_required = True` — not available by default, must be explicitly installed. Uses a specialized system prompt, a different model (`leanstral`), a compaction model, and custom tool config. Not relevant for general workflows; document it when it appears in `installed_agents`.

**Not valid for**

- general autonomous role-specialization unless the runtime exposes that behavior
- imaginary multi-agent coworkers
- profile behavior without a real Vibe profile or callback path

Agent profiles are not a general-purpose role-specialization framework. Use profile switching for permission/mode scoping. Use `task` subagents for read-only delegated analysis. Use tools for deterministic actions.

Correct pattern:

- start in `plan` mode for read-only exploration and planning
- use `exit_plan_mode` for user approval
- switch to `accept-edits` or `default` for implementation

This is often the smallest correct alternative to custom middleware or subagent orchestration.

**Non-obvious behaviors**

- **Profile switch preserves middleware**: `switch_agent` calls `reload_with_initial_messages(reset_middleware=False)`. The full middleware pipeline survives the switch. Custom middleware from the previous profile remains active in the new profile.
- **Profile switch preserves full message history**: the new profile sees the complete conversation history from the previous profile. There is no context reset. This is useful for continuity but can be context pollution in multi-phase designs that expect a clean slate.
- **`todo` state is wiped on switch**: `switch_agent` creates a new `ToolManager`, which creates a new `Todo` instance with an empty list. Any todo state from before the switch is lost.
- **Agent profile config overrides for per-phase tool restriction**: agent profile TOML files support config overrides via **flat top-level keys** — there is no `[overrides]` section. Keys not consumed as profile metadata (`display_name`, `description`, `safety`, `agent_type`) are collected as config overrides, including `enabled_tools`, `disabled_tools`, `active_model`, and `[tools.bash]` sub-tables. This is the correct surface for per-phase tool restriction. A special `base_disabled` key merges with the existing `disabled_tools` list rather than replacing it — use it to disable specific tools without clobbering user config.

## Configuration Layer

**Valid roles**

- active model selection
- `bypass_tool_permissions` (permission bypass flag — renamed from `auto_approve` in v2.9.0; using `auto_approve` is silently ignored)
- enabled/disabled tool sets (`enabled_tools`, `disabled_tools`)
- enabled/disabled skill sets (`enabled_skills`, `disabled_skills`, `skill_paths`)
- enabled/disabled agent profiles (`enabled_agents`, `disabled_agents`, `agent_paths`, `installed_agents`)
- custom tool paths (`tool_paths`)
- MCP server configuration including per-server `disabled` and `disabled_tools`
- connector configuration including per-connector `disabled` and `disabled_tools`
- tool-specific config override, including permission, allowlist, denylist, and sensitive patterns
- `compaction_model` for cheaper long-session compaction
- `auto_compact_threshold` (global default: 200,000 tokens; overridable per-model)
- `api_timeout` (float, default 720s)
- `system_prompt_id` (selects active system prompt; points to builtin name or custom file in `~/.vibe/prompts/`)
- `enable_experimental_hooks` (prerequisite for hooks to load — see below)
- `context_warnings: bool` (default `false`) — gate for `ContextWarningMiddleware`; without it, the 50% context warning is never injected
- `VIBE_*` environment variable overrides for every `VibeConfig` field

**Key config structure**

`thinking` is **per-model**, set inside `[[models]]`, not a top-level key:

```toml
[[models]]
name = "mistral-vibe-cli-latest"
provider = "mistral"
thinking = "high"
auto_compact_threshold = 150_000
```

`session_prefix` is **not top-level** — it lives under `[session_logging]`:

```toml
[session_logging]
session_prefix = "my-workflow"
enabled = true
save_dir = "/path/to/logs"
```

**Fit checks**

- If a need is "allow this command but ask for that command," prefer `BaseToolConfig` permission patterns before source changes.
- If a need is "make this tool available/unavailable," prefer `enabled_tools`, `disabled_tools`, `tool_paths`, or tool config before source changes. Same glob/`re:` pattern support applies to `enabled_skills`, `disabled_skills`, `enabled_agents`, `disabled_agents`.
- Use `system_prompt_id` to point at a custom prompt file in `~/.vibe/prompts/` before patching source. This is a config-only alternative to source changes for prompt customization.
- Recommend higher thinking levels (per-model) for complex design/feasibility work and lower/off for mechanical patching where quality risk is low.
- For long workflows, set both `compaction_model` and `auto_compact_threshold` together — threshold determines when, compaction model determines what runs.
- Any workflow that declares hooks must assert `enable_experimental_hooks = true` in its validation evidence. It is a workflow-critical prerequisite, not an optional flag.

**Pattern syntax**: `enabled_tools`, `disabled_tools`, `enabled_skills`, `disabled_skills`, `enabled_agents`, `disabled_agents` all support glob patterns (e.g., `bash*`) and full regex via a `re:` prefix (e.g., `re:^bash.*$`). This also applies to tool config `allowlist` and `denylist`.

**MCP and connector per-entry controls**

MCP servers (`[[mcp_servers]]`) support:
- `disabled = true` — hides all tools from the server (tools still discovered but not exposed)
- `disabled_tools = ["search", "read"]` — hides specific tools by name without the server prefix

Connectors (`[[connectors]]`) support the same shape. These are distinct from the global `disabled_tools` list.

**`VIBE_*` environment overrides**

Every `VibeConfig` field can be overridden via a `VIBE_`-prefixed env var (case-insensitive). This is the correct surface for CI/headless workflows that cannot write `config.toml`. Example: `VIBE_BYPASS_TOOL_PERMISSIONS=true`.

**Non-obvious behaviors**

- **`enabled_tools` silently ignores `disabled_tools`**: when `enabled_tools` is non-empty, `disabled_tools` is completely ignored. Same rule applies to `enabled_skills`/`disabled_skills` and `enabled_agents`/`disabled_agents`. Setting both is a silent bug.
- **Compaction model must share provider**: `compaction_model` must use the same provider as the active model. A mismatch raises `ValueError` at config load time, not at compaction time.
- **`enable_experimental_hooks` is excluded from generated config**: this field has `exclude=True`, so it does not appear in auto-generated `config.toml`. It must be added manually. Hooks silently do nothing without it.
- **`auto_compact_threshold` interaction**: if you set a global `auto_compact_threshold` without a `compaction_model`, compaction uses the active model at full cost. For long workflows, set both.
- **`system_prompt_id` default is `"cli"`**: overriding it changes the entire base system prompt, including headless-mode behavior. Test thoroughly in the target execution context.

## Planning And Approval Mode

`exit_plan_mode` is the canonical approval gate between planning and implementation. It reads the plan, shows it in a preview, and gives the user a runtime-supported choice of next mode.

Use it instead of inventing an approval prompt when the workflow is already in plan mode.

## Persistent Context

Use project `AGENTS.md` or `.vibe/AGENTS.md` for persistent context injected into every session. This is lighter than a skill when the requirement is stable project convention or workflow context rather than a user-invocable procedure.

Do not use AGENTS.md for dynamic workflow state or approval records.

**`~/.vibe/prompts` override risk** (added v2.9.0): users can silently override built-in prompts by placing files in `~/.vibe/prompts/`. Workflows that depend on specific system prompt content may behave differently in environments where these overrides exist. Workflows should document this risk when relying on system prompt wording for correctness.

Good uses:

- stable project conventions
- workflow-wide operating rules
- repository-specific constraints that should apply to every phase

Bad uses:

- phase status
- validation evidence
- user approvals
- transient ambiguity notes

## Hooks

The runtime hook surface is constrained.

**Valid role**

- `POST_AGENT_TURN` validation/observer hook. This is the only hook type.
- output validation that can ask the agent to retry by exiting with code `2`
- warning-only observer by exiting with non-zero other than `2`
- full-session analysis by reading `transcript_path` from the hook payload

**Hook invocation interface**

Hooks receive a JSON payload on stdin with these fields:

```json
{
  "session_id": "<session id>",
  "transcript_path": "<path to session transcript>",
  "cwd": "<working directory>",
  "hook_event_name": "<hook event name>"
}
```

This is the only way a hook script knows its session and transcript path. Hook scripts that do not read stdin will have no session context.

**Hook load locations**

Hooks are loaded from two locations:
1. `~/.vibe/hooks.toml` (global user hooks)
2. `.vibe/hooks.toml` (project-level, trusted folders only)

Both files are merged at load time. Duplicate hook names across files are deduplicated — the first occurrence wins and an issue is logged. When generating `hooks.toml`, place it in the correct location for the target scope (global vs. project).

**Exit code semantics**

- `0`: done, no agent effect
- `2`: re-inject stdout as a user message and retry
- anything else: warning/no behavioral retry

**Non-obvious behaviors**

- **Chain break**: when any hook exits with code `2`, the runtime breaks out of the hook list immediately. Subsequent hooks in the same `POST_AGENT_TURN` list do not run that turn. In a list `[lint, typecheck, test]`, if `lint` retries, `typecheck` and `test` are skipped until the next turn. Order hooks by priority; do not assume all run every turn.
- **Feature flag required**: hooks are gated behind `enable_experimental_hooks = true` in config. This field is marked `exclude=True` so it does not appear in generated `config.toml`. Hooks silently do nothing without it. Any workflow using hooks is assumption-based until this flag is confirmed in the target environment.
- **Retry stdout is a user-role message**: the re-injected stdout lands as `role: user`, not a system message or tool result. The model treats it as a user turn. Write hook output as explicit instructions, not raw tool output or command stderr.
- **Retry count resets per user message**: the 3-retry cap is per hook per user message, not per session. A consistently-failing hook retries 3 times on every new user message indefinitely.
- **Exit code `2` with empty stdout does not retry**: empty stdout on exit code `2` emits a warning only. Retry fires only when exit code is `2` AND stdout is non-empty.

**Not valid for**

- pre-turn interception
- tool-level interception
- per-file interception
- middleware replacement
- mid-turn control flow

Use hooks for post-turn validation/retry, not for core logic that must run before a turn or during tool execution.

## Programmatic Mode

Use CLI programmatic mode (`-p` / `--headless`) for CI/CD and external validation harnesses.

**Valid roles**

- `--output streaming` newline-delimited JSON evidence
- `--output json` final JSON transcript
- `--max-turns`, `--max-price`, and `--enabled-tools` boundaries
- machine-parseable validation runs

Prefer programmatic output parsing over asking the agent to manually write evidence when building CI-integrated workflows.

Programmatic mode combines naturally with `--max-turns`, `--max-price`, and `--enabled-tools` for bounded automation.

**Non-obvious behavior**

- **Headless mode changes agent behavior**: when running with `-p`, the system prompt gains a headless section that instructs the model to never ask questions, never wait for confirmation, and complete the task in a single pass. Workflows designed for interactive use (e.g., those that call `ask_user_question`) will behave differently in headless mode. The design and plan phases should explicitly ask whether the workflow is interactive or headless — this affects whether structured user decisions are valid in the workflow.

## Events, Reasoning, And Observability

**Valid roles**

- evidence stream
- UI/ACP observability
- tool call/result trace
- assistant output trace
- reasoning trace when the active backend/model emits `ReasoningEvent`

**Fit checks**

- Do not design control flow that depends on visible reasoning unless the selected model/backend supports reasoning events.
- New event types require source changes and consumer updates.

## Source Changes

**Valid roles**

- AgentLoop behavior changes
- middleware timing changes
- tool selection policy changes
- event schema changes
- ToolManager discovery/instantiation changes
- session persistence semantics

**Not valid for**

- simple workflow guidance
- basic tool availability or permission configuration
- behavior satisfied by skill metadata, tool config, MCP/connectors, or a normal tool wrapper

## Surface Interaction Map

| Combination | Valid Pattern | Risk |
|---|---|---|
| skill `allowed_tools` + tool | Skill constrains available tools while tool provides deterministic action | Required tool omitted from `allowed_tools` |
| tool + agent profile | Tool triggers profile switch via `switch_agent_callback` | Treating profiles as autonomous roles |
| `task` subagent + parent agent | Subagent returns analysis, parent writes files | Subagent assigned file-writing responsibility |
| tool `get_result_extra()` + middleware `INJECT_MESSAGE` | Separate post-tool and pre-turn context injection paths | Duplicate or conflicting context |
| tool prompt file + skill | Both add system-prompt guidance | Ordering or conflicting instructions |
| config tool overrides + tool | Config shapes permission and allow/deny behavior | Source patch overbuilt for permission policy |
| middleware injector + STOP/COMPACT middleware | Pre-turn injection plus halt/compact gate | STOP/COMPACT short-circuits later middleware |
| MCP/connectors + tools | Remote tools surfaced through ToolManager | Confusing connector semantics with MCP config |
| `exit_plan_mode` + agent profile | Built-in plan-to-implementation mode transition | Invented approval gate duplicates runtime support |
| hook `POST_AGENT_TURN` + transcript path | Full-conversation validation/retry after a turn | Assuming pre-turn or tool interception |
| `ask_user_question` + `content_preview` | Structured approval/intake/clarification | Generic prose prompt loses decision structure |
| `todo` + lifecycle artifacts | Session progress in todo, durable proof in files | Todo treated as cross-session record |
| scratchpad + validation | Temporary evidence/drafts outside project tree | Canonical records hidden in temp space |
| `webfetch`/`websearch` + plan | Current external research | Stale model knowledge |
| AGENTS.md + skill | Persistent project context plus invocable procedure | Duplicated or conflicting system prompt guidance |
| programmatic output + CI | Machine-readable validation evidence | Manual evidence writing |

## Anti-Patterns

- Middleware as `after_tool` / `post_tool` hook.
- Custom middleware presented as a config/skill-only extension, rather than source/runtime-code extension.
- Hook used as pre-turn, tool-level, or mid-turn interceptor.
- Skill `allowed_tools` used as a hard tool-access boundary. It is advisory only; the model sees all tools regardless. Use agent profile `overrides.enabled_tools` for actual restriction.
- Skill prompt text used as hard enforcement when runtime controls are needed.
- Agent profile described as a general autonomous role.
- Subagent assigned to write project files (the explore subagent is read-only by profile; custom subagents can write if the profile permits — the design constraint is a sound convention, not an enforced runtime block).
- Source patch for simple permission or tool-availability configuration.
- Tool used to change AgentLoop control policy.
- MCP or connector used as hidden workflow state.
- Workflow branching based on reasoning traces without model/backend support.
- Multiple context injection paths selected without a conflict/ordering rationale.
- Generic "ask user" step when `ask_user_question` structured choices are needed.
- Invented plan approval gate when `exit_plan_mode` fits.
- Todo used as durable cross-session audit state.
- Scratchpad used for canonical workflow records.
- Scratchpad treated as a project-relative or stable path — it is a temp directory with a non-deterministic path.
- MCP server `sampling_enabled` left at default (`true`) without explicit justification. The default is on, not off — any configured MCP server can request LLM completions unless `sampling_enabled = false` is set.
- Programmatic CI workflow that ignores `--output streaming` / `--output json`.
- Hook script that uses `exit 2` without printing stdout — empty stdout on exit code 2 silently emits a warning and does NOT trigger a retry.
- Config that references `auto_approve` — it was renamed to `bypass_tool_permissions` in v2.9.0 and is silently ignored under the old name.
- Interactive workflow (`ask_user_question`, user approval gates) designed without accounting for headless/programmatic mode, where the model is instructed to never wait for input.
- Workflow that spawns subagents and assumes they always complete — `TaskResult.completed = False` when middleware stops a subagent, and the parent will not handle it unless the workflow prompt explicitly checks for it.
