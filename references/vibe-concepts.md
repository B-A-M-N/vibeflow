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

### Middleware Hooks
- Intercept behavior between phases
- Examples: checkpoint_enforcer, no_user_deferral_guard, workflow_phase_guard
- Middleware can block, modify, or redirect workflow execution
- Safe extension points vs. requires source patches

### Tool Execution Lifecycle
- Tool call requested → middleware can intercept → tool executes → result returned
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

### Entry/Exit Gates
- Entry: conditions that must be true to start phase
- Exit: conditions that determine phase completion
- Gate types: success, failure, retry, human_deferral, convergence

### Retry/Convergence Rules
- Max retries per phase (prevents infinite loops)
- Convergence: bounded attempts with diagnosis on failure
- Retry delay: optional backoff between attempts

### Sandbox Validation
- Disposable test repo or fixture PR
- No real repo mutation
- Mock tools where possible
- Validate: inspect → plan → patch → test → report

### ACP Automation Target
- Autonomously identify, patch, and validate ACP-related PR work
- Workflow: discover candidate → diagnose issue → apply patch → validate fix
- Evidence: must show commands run, files changed, tests passed/failed

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
