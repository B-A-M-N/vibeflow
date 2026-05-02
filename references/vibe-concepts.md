# Mistral Vibe Concepts - Context Pack

You are helping build a Claude Code plugin for advanced Mistral Vibe workflow design/validation.

Before proposing code, first build an internal model of Mistral Vibe workflows using the reference files provided.

## Core Concepts

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
