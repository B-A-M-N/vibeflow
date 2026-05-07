# Mistral Vibe Concepts - Context Pack

You are helping build a Claude Code plugin for advanced Mistral Vibe workflow design/validation.

Before proposing code, first build an internal model of Mistral Vibe workflows using the reference files provided.

## Core Concepts

### Design Decomposition
Before designing a workflow, separate the work into three distinct layers:
- **LLM reasoning** — what the model decides, plans, or generates
- **Tool execution** — deterministic operations with structured results
- **Subagent delegation** — isolated sub-tasks with their own context and tool set

Every design mistake in advanced workflows comes from blurring these layers. Middleware is not a phase orchestrator. Hooks are not tool interceptors. The LLM is not a reliable signal emitter.

### Agent Loop
- Workflows run as loops with phases (discover → diagnose → patch → validate)
- Each loop iteration: check entry criteria → execute actions → evaluate exit criteria → gate decision
- Loops must have convergence gates (retry limits, success conditions)
- Anti-pattern: agent asking user instead of continuing autonomously

### Skills
- Injected into agent context based on trigger conditions
- Skills provide specialized knowledge or user-invoked actions
- Skill activation: description matching → load SKILL.md → execute instructions
- Skills can reference scripts/, references/, examples/
- **`allowed-tools` in skill frontmatter is advisory only** — it is never used to filter `ToolManager.available_tools`. The model sees all available tools regardless of what the skill declares. Use `enabled_tools` in an agent profile TOML for actual runtime tool restriction.

### Middleware
- **Middleware is a loop guard, not a phase orchestrator.** It enforces turn limits, budget caps, read-only reminders, and compaction policy. It is not the right surface for sequencing workflow phases — use the `task` tool for that.
- Active behavior is `before_turn(context)` only — fires before every LLM call in the tool loop, including after tool results. On a turn with 5 tool calls, middleware fires 6 times. Any middleware that counts "turns" or accumulates per-turn state will miscount.
- There is no `after_turn()`. The `ConversationMiddleware` Protocol has exactly two methods: `before_turn()` and `reset()`. Nothing else exists.
- `reset()` receives a `ResetReason` — `STOP` (session end) or `COMPACT` (context compaction). Middleware must check the reason: only clear state on `STOP`; preserve it on `COMPACT`.
- Multiple middleware can be composed, but ordering matters because STOP and COMPACT short-circuit later middleware
- Middleware cannot intercept during tool execution, after tool results, or arbitrary events
- **Registration is always Tier D**: there is no config, skill, or hook path to register middleware. The only path is `middleware_pipeline.add(mw)` in `_setup_middleware()` in `vibe/core/agent_loop.py`. The middleware class itself may be Tier C, but wiring it in always requires a source modification. A workflow that defines middleware but never registers it in `_setup_middleware()` has no effect — it silently never runs.

### Tool Execution Lifecycle
- Tool call requested → permission/config checked → tool executes → result returned
- Middleware has already run before the LLM produced the tool call; it does not wrap the tool call itself
- Tools: Bash, Read, Write, Edit, WebFetch, LSP, etc.
- Mock tools for dry-run: capture calls without executing

### State Persistence
- Workflow state stored in `.vibe-workflow/state.json`
- State includes: current phase, retry counts, evidence log, gate decisions
- Session-only or persistent based on workflow config
- **`todo` tool state does not survive a profile switch.** `switch_agent` calls `reload_with_initial_messages()` which creates a new `ToolManager`. The `todo` list is instance state on the old `ToolManager` and is lost. Workflows that use `todo` across a profile switch must persist progress to a file or state.json before switching.
- **Scratchpad path is non-deterministic across processes/restarts.** `init_scratchpad()` uses `tempfile.mkdtemp()` — the path is OS-assigned per process. Within a single session it is idempotent. Subagents get `scratchpad_dir=None`, which means `_get_scratchpad_section(None)` returns `None` and the path is **never injected into the subagent's system prompt**. A subagent cannot discover the scratchpad path without being told it explicitly in the task text. If a subagent somehow had the path, `is_scratchpad_path()` checks globally and would grant `ALWAYS` permission — the failure is absent context, not permission denied.
- **`ask_user_question` has two distinct failure modes.** CLI `-p` and ACP both disable the tool at the config level (added to `disabled_tools` before the session starts) — the model simply cannot call it. When `run_programmatic()` is used directly as a library, the tool is available in the registry but `user_input_callback` is never wired, so the tool raises `ToolError` at invocation time mid-session. Workflows with approval gates using `ask_user_question` must be designed knowing which contexts they'll run in.

### Prompt Injection / Skill Activation
- Skills activate when description matches task context
- Prompt injection: injecting skill content into agent's system prompt
- Activation path: task analysis → description match → load skill → merge instructions

### Workflow Phases
- Defined by: id, entry criteria, exit criteria, runtime surfaces, actions, and evidence requirements
- Phases transition via gates (continue, retry, stop, rework)
- Each phase logs evidence (commands, files, tests, results)
- **Phase sequencing belongs in the task tool-call graph, not in middleware.** The parent agent issues a `task()` call per phase, checks `TaskResult.completed`, and dispatches the next phase. This is Tier A/B. Middleware is a loop guard — it cannot observe what the LLM produced and cannot advance phases reactively without a structural one-turn delay on every transition.
- **Text signals are not a valid phase-transition mechanism.** Strings like `PHASE_COMPLETE: implement` in LLM output require fragile regex parsing. Use a custom tool call returning a `BaseModel` result instead — structured, machine-readable, and not dependent on exact LLM wording.

### Entry/Exit Gates
- Entry: conditions that must be true to start phase
- Exit: conditions that determine phase completion
- Gate types: success, failure, retry, human_deferral, convergence
- **Gate evaluation must be deterministic.** Prefer tool calls with structured results over LLM text for gate decisions. `ask_user_question` for human-deferral gates; `complete_phase` custom tool for automated gates.

### Retry/Convergence Rules
- Max retries per phase (prevents infinite loops)
- Convergence: bounded attempts with diagnosis on failure
- Retry delay: optional backoff between attempts

### Hooks
- `POST_AGENT_TURN` is the only hook type — fires once per completed agent turn
- Use for: post-turn validation, linting output, writing evidence, retrying on failure
- **Retry protocol**: exit 2 + non-empty stdout → inject stdout as user message + retry; exit 2 + empty stdout → warning only; timeout (default 30s) → warning, no retry
- **3-retry ceiling**: the runtime tracks `_MAX_RETRIES = 3` retries per hook name per user turn. After 3 retries the hook stops retrying for that turn. Retry count resets on new user message. Workflows using hooks as quality gates must account for this hard ceiling.
- Chain breaks on first retrying hook — later hooks in the chain do not run that turn
- Hooks never run in subagents; they only run for the primary agent turn

### Sandbox Validation
- Disposable test repo or fixture PR
- No real repo mutation
- Mock tools where possible
- Validate: inspect → plan → patch → test → report


## Extension Points

### Safe to Use (Plugin-level)
- Skills (SKILL.md)
- Plugin manifest (plugin.json)
- Keybindings (~/.claude/keybindings.json)
- State files (.vibe-workflow/state.json)
- References and scripts in plugin directory

### Requires Source Patches
- Core agent loop behavior
- Middleware registration (if not plugin-exposed)
- New tool types
- Gate condition engine changes
