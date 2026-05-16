# Mistral Vibe as an Agent Runtime

**Read this first.** Before designing any workflow with VibeFlow, you need to understand what Mistral Vibe *is* — and what it is *not*.

## The Core Distinction

**An agent application** is a system where a language model reasons, calls tools, and produces output. The application *is* the model's behavior. If the model does the right thing, the application works. If the model does the wrong thing, the application fails. The developer's job is to write good prompts.

**An agent runtime** is an execution environment that *surrounds* the model with structure: a turn loop, a tool system, a middleware pipeline, an event system, session persistence, and configuration-driven behavior. The model is one component inside this environment. The runtime constrains what the model can do, observes what it does, and reacts — independently of the model's own reasoning.

Mistral Vibe is an agent runtime. This distinction changes everything about how you design workflows for it.

## The Runtime Architecture

Think of Vibe as a machine with these layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Configuration Layer                       │
│  config.toml — models, tools, permissions, MCP, compaction     │
├─────────────────────────────────────────────────────────────────┤
│                        Agent Profiles                           │
│  Per-phase model + tool set + system prompt                    │
├─────────────────────────────────────────────────────────────────┤
│                        AgentLoop (the engine)                   │
│                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────┐     │
│  │Middleware│───▶│  LLM Backend  │───▶│  Tool Execution   │     │
│  │ Pipeline │    │  (streaming)  │    │  (concurrent)     │     │
│  └──────────┘    └──────────────┘    └───────────────────┘     │
│       │                │                       │                 │
│       ▼                ▼                       ▼                 │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────┐     │
│  │  Events  │    │   Session    │    │   State Files     │     │
│  │  Stream  │    │   Logger     │    │   (on disk)       │     │
│  └──────────┘    └──────────────┘    └───────────────────┘     │
├─────────────────────────────────────────────────────────────────┤
│                        Extension Surfaces                        │
│  Skills (knowledge) │ Tools (actions) │ Hooks (observation)    │
│  MCP/Connectors (remote) │ Source changes (last resort)        │
└─────────────────────────────────────────────────────────────────┘
```

### The AgentLoop Is the Engine

The AgentLoop is not the model. It is the *loop* that:

1. Takes the current message history
2. Runs the middleware pipeline (before every LLM call — not once per user message)
3. Sends the messages to the LLM backend
4. Receives tool calls from the model
5. Executes tools (concurrently when possible)
6. Feeds tool results back into the message history
7. Repeats until the model produces a text response or middleware stops the loop

The model is a *participant* in this loop. It does not control the loop. It cannot decide when to stop, which tools are available, or what middleware runs. The runtime controls all of that.

### Middleware Is a Loop Guard, Not a Phase Orchestrator

This is the single most important thing to understand about Vibe's architecture:

**Middleware runs before every LLM call in the tool loop.** On a turn with 5 tool calls, middleware fires 6 times. It cannot observe what the model just said and react to it — it runs *before* the next call, not after. It has no visibility into which tools the model will call or what arguments they will carry.

This means middleware is fundamentally a **gate**, not a **sequencer**. It can:
- Stop the loop (`STOP`)
- Trigger context compaction (`COMPACT`)
- Inject a message before the next LLM call (`INJECT_MESSAGE`)

It **cannot**:
- Sequence workflow phases
- Inspect or block individual tool calls mid-turn
- React to what the model just produced without a one-turn delay

**If your workflow needs phase sequencing, use the `task` tool, not middleware.** Each phase is a separate `task()` call. The parent agent checks `TaskResult.completed` and dispatches the next phase. This is Tier A/B. Middleware-based phase orchestration is Tier D and still broken.

### Tools Are Actions, Not Behaviors

Tools execute when the AgentLoop calls them. They cannot change when or why they are called. They run, they return a result, and the result goes back into the message history.

A tool can:
- Perform a deterministic action
- Inject extra context via `get_result_extra()`
- Trigger a profile switch via `ctx.switch_agent_callback()`
- Resolve per-invocation permissions via `resolve_permission()`

A tool **cannot**:
- Intercept the message flow
- Run before every LLM turn (that's middleware)
- Change AgentLoop control policy

### Skills Are Knowledge, Not Enforcement

Skills inject instructions into the model's system prompt. They are loaded once per invocation. The model reads them and (hopefully) follows them.

**`allowed_tools` in a skill is advisory only.** It is never used to filter `ToolManager.available_tools`. The model sees all available tools regardless of what the skill declares. If you need actual tool restriction, use agent profile `enabled_tools`.

Skills are the right surface for: guided workflow procedures, domain knowledge, prompt scaffolds, user-invocable behaviors.

Skills are the wrong surface for: enforcing runtime behavior, restricting tool access, changing AgentLoop policy.

### The Config System Is Behavioral Parameterization

`config.toml` is not just settings — it is the primary surface for changing runtime behavior without writing code. Every field in `VibeConfig` can be overridden via `VIBE_*` environment variables.

Key config surfaces:
- **Model selection**: `active_model`, per-model `[[models]]` entries with provider, thinking level, compaction threshold
- **Tool availability**: `enabled_tools`, `disabled_tools` (glob and regex patterns)
- **Permission policy**: `bypass_tool_permissions` (not `auto_approve` — silently ignored), per-tool `permission` overrides
- **Extension paths**: `tool_paths`, `skill_paths`, `agent_paths`
- **Remote tools**: `[[mcp_servers]]`, `[[connectors]]`
- **Compaction**: `compaction_model`, `auto_compact_threshold` (global and per-model)
- **Hooks**: `enable_experimental_hooks` (required — hooks silently do nothing without it)

### Agent Profiles Are Mode Switches

Agent profiles change the model, tool set, and system prompt. They are the correct surface for per-phase behavior differentiation.

When a profile switch happens via `switch_agent_callback`:
1. The backend is rebuilt (new model takes effect)
2. ToolManager is rebuilt (new `enabled_tools`/`disabled_tools`)
3. SkillManager is rebuilt
4. System prompt is regenerated
5. **Message history is preserved** — the new profile sees all prior messages
6. **Middleware pipeline is preserved** — custom middleware from the previous profile remains active
7. **`todo` state is lost** — new ToolManager, new Todo instance

Profile switching is **not** subagent isolation. The context window is shared. For true isolation, use the `task` tool to spawn a fresh AgentLoop with its own message history.

### Hooks Are Post-Turn Observers

`POST_AGENT_TURN` hooks fire after every completed agent turn. They are shell scripts that receive session context on stdin and can:
- Exit 0: no effect
- Exit 2 + non-empty stdout: inject stdout as a user message and retry (max 3 retries per hook per user turn)
- Exit 2 + empty stdout: warning only, no retry
- Any other non-zero: warning, no retry

Hooks are the right surface for: post-turn validation, quality gates, output observation.

Hooks are the wrong surface for: pre-turn interception, tool-level interception, mid-turn control flow, phase sequencing.

### Events Are the Observability Stream

The event system (`BaseEvent` hierarchy) is how the runtime communicates what is happening. Events flow from the AgentLoop to consumers (TUI, ACP, custom handlers).

Events are for observation and UI. They are not a control flow mechanism. Designing workflow logic that depends on specific event types existing will fail if the model/backend doesn't emit those events.

## What This Means for Workflow Design

When you design a workflow for Vibe, you are not writing a prompt. You are **configuring a runtime**:

1. **Choose the smallest sufficient surface for each requirement.** Don't use source changes when config suffices. Don't use middleware when the `task` tool suffices. Don't use a custom tool when a built-in tool suffices.

2. **Respect the architectural boundaries.** Middleware is a gate, not a sequencer. Skills are knowledge, not enforcement. Tools are actions, not behaviors. Hooks are observers, not interceptors.

3. **Design for compaction.** Context *will* be lost. State that must survive goes on disk. The agent profile survives compaction natively. `todo` state does not.

4. **Design for profile switches.** If your workflow has distinct phases with different tool permissions, use agent profiles with `enabled_tools`/`disabled_tools`. The model literally cannot call tools not in its schema.

5. **Design for the turn loop.** Every LLM call triggers middleware. Every tool call goes through permission checking. Every result goes back into the message history. Your workflow operates *within* this loop, not outside it.

## The Tier System

VibeFlow classifies every workflow requirement into one of five tiers:

| Tier | Surface | Source Changes? |
|------|---------|-----------------|
| A | Config + Skills + Hooks + Agent Profiles | No |
| B | Custom Tools (BaseTool subclasses) | No |
| C | Custom Middleware (Protocol, not ABC) | No (but registration is Tier D) |
| D | Source modifications to `vibe/core/` | Yes |
| E | Not feasible — contradicts runtime architecture | N/A |

Most workflows should be Tier A or B. If you find yourself at Tier D, question whether the requirement is real or whether you're fighting the runtime.

## Further Reading

- `extension-point-taxonomy.md` — Detailed tier classification with constraints and feasibility checks
- `runtime-pattern-catalog.md` — Valid patterns, non-obvious behaviors, and anti-patterns for each surface
- `implementation-patterns.md` — Source-verified code recipes for common extension tasks
- `key-interfaces-contracts.md` — Exact contracts for BaseTool, InvokeContext, Middleware, and Events
