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

Skill metadata includes `allowed_tools`. This is a real constraint on which tools are available while the skill is active. It is not just prose guidance.

**Not valid for**

- enforcing arbitrary runtime behavior beyond supported skill metadata
- changing AgentLoop policy
- post-tool interception

**Fit checks**

- If a skill requires tools, `allowed_tools` must include those tools.
- If a skill is expected to prevent tool use, verify `allowed_tools` expresses that boundary.
- If a requirement needs deterministic execution, pair the skill with a tool/MCP/connector instead of relying on prompt text.

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

### Scratchpad

Use the session scratchpad for intermediate artifacts, draft manifests, temporary evidence, and validation outputs that should not clutter the project tree. Scratchpad files are auto-allowed and shared with subagents.

Do not use scratchpad for canonical lifecycle records that need to persist in the project.

### `task` Subagents

Use `task` for parallel or specialized read/analysis work. Custom subagents are possible when configured with `agent_type = "subagent"`.

**Hard constraint:** subagents return text to the parent. They must not be responsible for writing project files. If delegated work produces artifact content, the parent agent writes it.

Custom subagents are config-level agent profiles with `agent_type = "subagent"`, a system prompt, model, and tool set. This is more specific than a generic "agent role."

Good uses:

- read-only research
- validator returning findings
- planner/reviewer returning a proposal
- parallel source exploration

Bad uses:

- subagent directly generating files
- subagent owning persistent workflow state
- subagent used where a profile switch or tool permission scope is enough

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

**Not valid for**

- post-tool interception
- during-tool execution
- arbitrary event handling
- changing tool execution logic without source changes

## Agent Profiles

**Valid roles**

- supported profile switching among real profiles such as default, plan, accept-edits, and auto-approve
- read-only reminder behavior through middleware tied to a profile name
- tool-triggered profile switch via `InvokeContext.switch_agent_callback`

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

## Configuration Layer

**Valid roles**

- active model selection
- auto-approve and permission defaults
- enabled/disabled tool sets
- custom tool paths
- MCP server configuration
- tool-specific config override, including permission, allowlist, denylist, and sensitive patterns
- model `thinking` level where supported: `off`, `low`, `medium`, `high`, `max`
- `compaction_model` for cheaper long-session compaction

**Fit checks**

- If a need is "allow this command but ask for that command," prefer `BaseToolConfig` permission patterns before source changes.
- If a need is "make this tool available/unavailable," prefer `enabled_tools`, `disabled_tools`, `tool_paths`, skill `allowed_tools`, or tool config before source changes.
- Recommend higher thinking levels for complex design/feasibility work and lower/off thinking for mechanical patching where quality risk is low.
- Recommend `compaction_model` for workflows expected to run long enough to hit auto-compaction.

## Planning And Approval Mode

`exit_plan_mode` is the canonical approval gate between planning and implementation. It reads the plan, shows it in a preview, and gives the user a runtime-supported choice of next mode.

Use it instead of inventing an approval prompt when the workflow is already in plan mode.

## Persistent Context

Use project `AGENTS.md` or `.vibe/AGENTS.md` for persistent context injected into every session. This is lighter than a skill when the requirement is stable project convention or workflow context rather than a user-invocable procedure.

Do not use AGENTS.md for dynamic workflow state or approval records.

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

**Exit code semantics**

- `0`: done, no agent effect
- `2`: re-inject stdout as a user message and retry
- anything else: warning/no behavioral retry

**Not valid for**

- pre-turn interception
- tool-level interception
- per-file interception
- middleware replacement
- mid-turn control flow

Use hooks for post-turn validation/retry, not for core logic that must run before a turn or during tool execution.

## Programmatic Mode

Use CLI programmatic mode for CI/CD and external validation harnesses.

**Valid roles**

- `--output streaming` newline-delimited JSON evidence
- `--output json` final JSON transcript
- `--max-turns`, `--max-price`, and `--enabled-tools` boundaries
- machine-parseable validation runs

Prefer programmatic output parsing over asking the agent to manually write evidence when building CI-integrated workflows.

Programmatic mode combines naturally with `--max-turns`, `--max-price`, and `--enabled-tools` for bounded automation.

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
- Skill prompt text used as hard enforcement when `allowed_tools` or runtime controls are needed.
- Agent profile described as a general autonomous role.
- Subagent assigned to write project files.
- Source patch for simple permission or tool-availability configuration.
- Tool used to change AgentLoop control policy.
- MCP or connector used as hidden workflow state.
- Workflow branching based on reasoning traces without model/backend support.
- Multiple context injection paths selected without a conflict/ordering rationale.
- Generic "ask user" step when `ask_user_question` structured choices are needed.
- Invented plan approval gate when `exit_plan_mode` fits.
- Todo used as durable cross-session audit state.
- Scratchpad used for canonical workflow records.
- MCP server `sampling_enabled` enabled without justification.
- Programmatic CI workflow that ignores `--output streaming` / `--output json`.
