# Runtime Pattern Catalog

This catalog describes valid Mistral Vibe workflow extension patterns. Use it to select the smallest correct runtime surface for a requirement. Do not treat this as a menu of everything to include.

## Selection Principle

For each requirement:

1. Identify what must happen.
2. Pick the smallest runtime surface that can reliably provide that capability.
3. Record why stronger surfaces were rejected.
4. Validate selected surfaces with implementation and proof.

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

- deterministic action
- structured repo/file operation
- external API call
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

## Remote Tools: MCP And Mistral Connectors

**Valid roles**

- external capability bridge
- multi-tool service integration
- service boundary for HTTP/stdio/streamable HTTP capabilities
- Mistral Connector API-backed remote tools through `ConnectorRegistry`

**Important distinction**

MCP and Mistral Connectors are both remote tool surfaces, but they are not the same mechanism. MCP uses configured MCP servers. Connectors use Mistral connector integration through the tool manager.

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

## Configuration Layer

**Valid roles**

- active model selection
- auto-approve and permission defaults
- enabled/disabled tool sets
- custom tool paths
- MCP server configuration
- tool-specific config override, including permission, allowlist, denylist, and sensitive patterns

**Fit checks**

- If a need is "allow this command but ask for that command," prefer `BaseToolConfig` permission patterns before source changes.
- If a need is "make this tool available/unavailable," prefer `enabled_tools`, `disabled_tools`, `tool_paths`, skill `allowed_tools`, or tool config before source changes.

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
| tool `get_result_extra()` + middleware `INJECT_MESSAGE` | Separate post-tool and pre-turn context injection paths | Duplicate or conflicting context |
| tool prompt file + skill | Both add system-prompt guidance | Ordering or conflicting instructions |
| config tool overrides + tool | Config shapes permission and allow/deny behavior | Source patch overbuilt for permission policy |
| middleware injector + STOP/COMPACT middleware | Pre-turn injection plus halt/compact gate | STOP/COMPACT short-circuits later middleware |
| MCP/connectors + tools | Remote tools surfaced through ToolManager | Confusing connector semantics with MCP config |

## Anti-Patterns

- Middleware as `after_tool` / `post_tool` hook.
- Skill prompt text used as hard enforcement when `allowed_tools` or runtime controls are needed.
- Agent profile described as a general autonomous role.
- Source patch for simple permission or tool-availability configuration.
- Tool used to change AgentLoop control policy.
- MCP or connector used as hidden workflow state.
- Workflow branching based on reasoning traces without model/backend support.
- Multiple context injection paths selected without a conflict/ordering rationale.
