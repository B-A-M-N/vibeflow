---
name: vibe-workflow-design
description: "Run Phase 2 of VibeFlow: map approved intent onto real Mistral Vibe runtime topology with feasibility checks, component explanations, plain-English diagrams, blunt critique, and user approval."
version: 2.0.0
allowed-tools:
  - ReadFile
  - WriteFile
  - EditFile
  - Bash
  - Grep
  - Glob
user-invocable: true
---

You are running the `design` phase of VibeFlow.

Your job is to help the user understand what is possible, what is not possible, and what architecture is most grounded for the workflow they signed off during init.

## Inputs

Read `VISION.md`, `PLAN.md`, and `WORKFLOW_CONTRACT.json`.

Run environment preflight before claiming a grounded runtime topology:

- detect target repo/path/version
- distinguish installed package from source checkout
- detect plugin profile path and command/skill loader shape where relevant
- identify whether source/docs were actually available

If source/docs are unavailable, label the design assumption-based and record verification tasks for plan/validate.

Then use the feasibility substrate with progressive disclosure. Start with `references/diagrams/diagram-index.json`, identify relevant runtime surfaces, and read only the matching reference files needed to sanity-check the current design.

Do not load every reference file by default. Do not make consulting references part of the user-facing workflow. Use the references internally when they help verify a concrete design claim.

Available feasibility substrate:

- Extension Point Taxonomy
- Key Interfaces & Contracts
- Runtime Pattern Catalog
- Workflow Pattern Library
- Event System Reference
- Configuration Keys for Workflow Control
- Tier Composition Patterns
- Diagnostic & Observability

Reference citations are optional. Include them only when a feasibility claim is risky, surprising, disputed, or helpful for explaining why something is or is not possible.

If init artifacts are missing or unapproved, stop and tell the user to run `vibe-workflow:init`.

## Pre-Design Decomposition

Before mapping requirements to surfaces, decompose the workflow into three distinct layers:

- **LLM reasoning** — what the model decides, plans, or generates
- **Tool execution** — deterministic operations with structured `BaseModel` results
- **Subagent delegation** — isolated sub-tasks with their own context and tool set

Middleware is not a phase orchestrator. Hooks are not tool interceptors. The LLM is not a reliable signal emitter. Any design that blurs these layers will fail — catch it here, not in validate.

## Design Behavior

Open with a recommendation:

```md
Based on what you told me, this is what I would recommend.
```

Then explain:

- components in plain English
- which Mistral Vibe runtime surface each component uses
- why that surface fits
- feasibility tier
- required contracts
- tradeoffs
- likely failure modes
- what needs source modification, if anything

Use simple diagrams when they make the design easier to understand.

## Architecture Sanity Check

Before asking for approval or writing design artifacts, run a blocking sanity check over the proposed architecture. The purpose is to maximize workflow success by choosing the right runtime surfaces, not just the first plausible implementation.

Use `references/feasibility/runtime-pattern-catalog.md` to choose valid patterns and reject invalid ones. The catalog is a selector and anti-pattern guard, not a requirement to include every surface.

Create an internal component matrix with one row per applicable surface:

- skills/prompts: when the behavior is guidance, sequencing, or user-facing workflow instructions
- config: when existing runtime behavior only needs to be enabled, disabled, routed, or constrained
- tools/MCP: when the workflow needs a new executable action, external system call, or structured capability
- built-in workflow tools: `ask_user_question`, `exit_plan_mode`, `todo`, `task`, `webfetch`, and `websearch` when native primitives fit the workflow
- middleware: when behavior must inspect, halt, compact, or inject context before LLM turns
- agents/profiles: when the runtime supports delegated behavior through a real profile/agent/tool surface, not invented persona orchestration
- scratchpad: when intermediate artifacts should be temporary and auto-allowed
- AGENTS.md: when persistent project/workflow context should be injected into every session without making a user-invocable skill
- programmatic mode: when CI/CD or external automation needs machine-readable `--output streaming` or `--output json`
- events/session/state: when the workflow needs durable trace, replay, audit, or lifecycle state
- hooks: when behavior belongs at a supported lifecycle boundary; do not use hooks as a substitute for core workflow logic unless the runtime actually calls them there
- source changes: when the desired behavior changes AgentLoop, tool selection, middleware timing, event schema, persistence, or permission semantics

For each applicable surface, decide:

- selected, rejected, or not applicable
- why it does or does not fit this workflow
- what contract it must obey
- what failure mode it introduces
- what simpler alternative could satisfy the same requirement
- what evidence/source/docs ground the claim

Record these decisions as a design decision contract in `WORKFLOW_CONTRACT.json`. This contract preserves creative freedom: it does not prescribe the exact component shape, but every selected surface must name the capability it provides, why it is necessary, the runtime contract it obeys, planned implementation evidence, and validation proof. Rejected or not-applicable surfaces need rationale and when to reconsider, not implementation.

Every `surfaceDecision` entry written to `WORKFLOW_CONTRACT.json` must use this exact template. Missing any of these fields will fail `design-contract-linter.py`:

```json
{
  "surface": "human-readable surface name",
  "status": "selected | rejected | not-applicable",
  "reason": "why this surface was selected, rejected, or not applicable",
  "requiredCapabilities": ["list of capabilities this surface must provide"],
  "contracts": ["runtime contracts this surface must obey"],
  "implementationEvidence": ["planned files or code evidence that proves implementation"],
  "validationEvidence": ["validation commands or checks that confirm the surface works"],
  "feasibility_confidence": 80
}
```

Specific checks:

- **Middleware is a loop guard, not a phase orchestrator.** If the workflow sequences phases (discover → diagnose → patch → validate), the correct surface is the `task` tool — each phase is a `task()` call and the parent agent checks `TaskResult.completed`. Middleware cannot observe what the LLM just produced and has a structural one-turn delay on every phase transition. Never design a phase state machine in middleware.
- **Text signals are not a valid phase-transition mechanism.** Strings like `PHASE_COMPLETE: X` in LLM output require fragile regex parsing. Use a custom tool call returning a `BaseModel` result instead.
- Middleware only has `before_turn(context)` active behavior plus reset. There is no `after_turn()`. It fires before every LLM call in the tool loop — on a turn with 5 tool calls, it fires 6 times. Middleware that counts turns or accumulates per-turn state will miscount.
- **Middleware cannot intercept individual tool calls mid-turn.** A middleware that "blocks each file edit as it happens" or "checks each tool call" is architecturally impossible. Middleware runs once before the LLM call, not between tool executions. For scope enforcement (blocking writes outside allowed paths), use a custom `BaseTool` subclass with `resolve_permission()` or the `approval_callback` on `AgentLoop`. These are the only two surfaces that see individual tool calls.
- **Phase-gate enforcement requires a tool trigger, not just agent profiles.** Saying "restrict tools per phase via agent profiles" is incomplete without specifying the trigger. The only real enforcement path: a custom tool that the LLM calls (e.g., `advance_phase(from="PLAN", to="IMPLEMENT")`), which validates the transition, writes state to disk, and calls `ctx.switch_agent_callback("implement-profile")`. The new profile's `enabled_tools`/`disabled_tools` then physically prevents the LLM from calling tools not in that set. Without a custom tool calling `switch_agent_callback`, there is no trigger — the LLM just reads skill text and hopes it follows the rules. For the standard plan-to-implement gate, use the built-in `exit_plan_mode` tool.
- **Per-phase model assignment uses profile overrides, not a separate tool.** Agent profile TOML files support flat-top-level override keys including `active_model`, `providers`, and `models`. `AgentProfile.from_toml()` loads these; `VibeConfig.agent_paths` configures custom directories. No custom tool is needed to switch models between phases — just reference the correct profile TOML. Every model name referenced in a profile TOML must already be declared as a model alias in `~/.vibe/config.toml`.
- **Agent TOML files must use flat top-level keys — no nested sections.** `[agent]`, `[agent.system_prompt]`, `[agent.permissions]`, `[agent.subagents]` are invented structures that `from_toml` will not parse. Only `display_name`, `description`, `safety` (`safe`, `neutral`, `destructive`, or `yolo`), and `agent_type` are consumed as profile metadata. Everything else (system prompt, model overrides, tool permissions, enabled_tools) goes as flat top-level keys or `[tools.X]` sub-tables. The agent name is always the filename stem — a `name` key inside the TOML goes into overrides, not the identity.
- **Agents are not configured in config.toml.** There is no `[agents.X]` section in `VibeConfig`. Agents are discovered from `.toml` files in agent directories (`~/.vibe/agents/`, `agent_paths`). Do not write agent definitions or model assignments inside `config.toml` — they will be silently ignored.
- **Skills must be SKILL.md markdown files, not Python SkillInfo constants.** Skills are discovered exclusively from `SKILL.md` files inside subdirectories of skill search paths. `SkillInfo` is an internal Python model — it is not a format you write. The correct artifact is always a directory with a `SKILL.md` containing YAML frontmatter (`name`, `description`, `allowed-tools`, `user-invocable`).
- **Middleware "blocking" is overstated.** `STOP` terminates the entire session — too aggressive for a phase gate. `INJECT_MESSAGE` injects a soft reminder that the agent can ignore. There is no middleware action that "pauses and waits for a gate to be satisfied." If the gate check uses STOP, it kills the session. If it uses INJECT_MESSAGE, the agent may simply continue. Phase-gate enforcement should use tool-triggered profile switching (`ctx.switch_agent_callback`) with `enabled_tools`/`disabled_tools` for actual enforcement, not middleware.
- **AgentLoop does not write workflow state files.** `AgentLoop` has no API to write arbitrary state (`.pr-state.json`, `state.json`, etc.). The only persistence it performs is `SessionLogger` (conversation history). Any workflow state file must be written by the LLM via tool calls (`write_file`, `bash`), not by AgentLoop as a first-class operation.
- **Do not use `state.json` to persist phase across compaction.** The agent profile (and thus the active phase encoded in it) survives compaction automatically — `AgentManager` state is not part of message history, and the system prompt is regenerated from the current profile each turn. Writing phase to `state.json` and reading it back each turn adds fragile coupling and is unnecessary. If the phase is encoded in the active agent profile, it survives compaction natively.
- **Skill names must match the directory name and pattern `^[a-z0-9]+(-[a-z0-9]+)*$`.** A skill named "PRForge" is invalid. The directory must be named `pr` and the `name` field in SKILL.md frontmatter must also be `pr`. The `SkillMetadata.name` field enforces this pattern and the manager warns when it doesn't match the directory.
- **Profile switching is not subagent isolation.** Switching agent profiles within one AgentLoop changes the system prompt but keeps the same context window — the model still sees all prior messages. If a workflow claims "subagent isolation" or "per-phase isolation," it must use the `task` tool to spawn a fresh AgentLoop per phase, each with its own message history. Profile switching alone improves discipline but does not provide isolation. Flag any design that claims isolation without using `task`.
- Any middleware `reset()` implementation must check `ResetReason`: only clear state on `STOP`; preserve it on `COMPACT`. A reset that clears all state silently restarts the workflow on compaction.
- Middleware registration requires modifying `_setup_middleware()` in `vibe/core/agent_loop.py` — this is always Tier D, regardless of how simple the middleware class is.
- Treat `MiddlewareAction.COMPACT` as a distinct action and account for pipeline short-circuiting: `INJECT_MESSAGE` results compose, while `STOP` and `COMPACT` stop later middleware.
- If a design proposes a skill, verify discoverability: it must live in `.vibe/skills/`, `~/.config/vibe/skills/`, or a project `skills/` directory, and its frontmatter must include `name`, `description`, `allowed-tools`, and `user-invocable`.
- **Custom tools must not be placed in `vibe/core/tools/builtins/`.** That directory is core infrastructure (bash, grep, read_file, etc.) — placing workflow-specific tools there is a Tier D source modification. All custom tools must be skill-bundled (in the skill directory) or in a config/tool_paths directory.
- **`enabled_tools` controls which tools the LLM can call — it does NOT control which files those tools can operate on.** If `write_file` is in `enabled_tools`, the LLM can call `write_file` on any path. File-level scope enforcement requires either per-tool allowlist/permission overrides in the agent profile (e.g., `overrides.tools.write_file`), validation logic inside the phase-advance tool (e.g., `git diff --name-only` to reject out-of-scope modifications), or a custom `BaseTool` subclass with `resolve_permission()`. Never claim "scope enforced by enabled_tools" — that is incorrect.
- **Skill-bundled tool discovery works, but verify it loads.** `ToolManager` discovers Python tools from `skill_dir/tools/` and `config.tool_paths` adds explicit directories via `_compute_search_paths`. Both mechanisms work. Tool discovery is recursive (`rglob("*.py")`) — all subdirectories are searched. However, always confirm the tool actually appears in the tool schema before relying on it — placement does not guarantee discovery if the class doesn't inherit `BaseTool` correctly or has import errors.
- **Tool name in `enabled_tools` must match `BaseTool.get_name()` exactly.** `get_name()` converts the class name from CamelCase to snake_case (e.g., `AdvancePhaseTool` → `advance_phase_tool`). If a profile's `enabled_tools` lists `"advance_phase"` but `get_name()` returns `"advance_phase_tool"`, the tool is silently absent from the LLM schema in that phase. Always verify the exact string.
- **Phase switching preserves middleware state.** `switch_agent` calls `reload_with_initial_messages(reset_middleware=False)`, so middleware state (e.g., `AutoCompactMiddleware` token counters) is preserved across phase switches. The rebuild covers `backend`, `ToolManager`, `skill_manager`, and system prompt — but not middleware reset. Design phase transitions assuming middleware accumulates state across the full session.
- If a design uses skill `allowed-tools` / `allowed_tools`, verify it does not conflict with required tools.
- Prefer `ask_user_question` over generic "ask user" prose for approval gates, intake forms, and ambiguity clarification. Use choices, descriptions, multi-select when needed, and `content_preview` for plans or documents.
- Prefer `exit_plan_mode` for plan-to-implementation approval.
- Use `todo` for session-scoped phase tracking, not durable audit records.
- Use scratchpad for temporary drafts/evidence, not canonical workflow records.
- Use `task` subagents for read-only/specialized analysis; the parent agent writes files.
- Use `webfetch` / `websearch` when the workflow needs current external docs, PRs, API references, or web context.
- Use `.vibe/AGENTS.md` / `AGENTS.md` for stable persistent context, not dynamic state.
- Use MCP `prompt` to guide remote tool use and justify `sampling_enabled` if enabled.
- Use `thinking` and `compaction_model` as quality/cost knobs when phases are long or reasoning-heavy.
- Use `POST_AGENT_TURN` hooks only for post-turn validation/observation/retry; retry requires exit code 2 and stdout reinjection. Hooks can read `transcript_path`.
- Use programmatic `--output streaming` / `--output json` for CI evidence where appropriate.
- Do not use a tool when the requirement is to change how tools are selected, authorized, sequenced, or interpreted by AgentLoop.
- **`todo` tool state does not survive a profile switch** — `switch_agent` creates a new `ToolManager` and the todo list is lost. If the design uses `todo` across a profile switch, it must checkpoint progress to a file or `state.json` first.
- **Scratchpad path is non-deterministic across sessions** (`tempfile.mkdtemp()`, OS-assigned per process). Subagents get `scratchpad_dir=None` — the path is never injected into the subagent's system prompt. A subagent cannot use the scratchpad unless the parent passes the path explicitly in the task text.
- **`ask_user_question` has two distinct failure modes**: (1) CLI `-p` and ACP both disable the tool at config level — the model cannot call it at all; (2) `run_programmatic()` direct library use leaves the tool enabled but with no callback wired, so it raises `ToolError` mid-session at invocation time. Design approval gates with the execution context in mind.
- Prefer tool-level mechanisms where they fit: `BaseToolConfig` permission/allowlist/denylist/sensitive_patterns, `resolve_permission()`, `get_result_extra()`, `BaseToolState`, `get_tool_prompt()` / `prompt_path`, and `switch_agent_callback`.
- Do not model agents as autonomous collaborators unless the runtime has a concrete agent/profile/tool mechanism that supports that role.
- Treat Mistral Connectors as a distinct remote tool surface from MCP; do not collapse connector semantics into MCP config.
- Do not depend on visible reasoning traces unless the selected backend/model emits `ReasoningEvent`.
- Do not use hooks for control flow unless their invocation point is verified.
- Prefer the smallest runtime surface that satisfies the success criteria, but include every required surface when the workflow genuinely needs a cohesive multi-surface design.
- If two surfaces could solve the same problem, compare them explicitly and choose one with rationale.

The recommendation must include a short "Architecture Sanity Check" section before the approval question. If a surface is applicable but rejected, include the reason. If a surface is required but unverified, mark the design assumption-based and add verification tasks for plan/validate. Do not write `DESIGN.md` or `ARCHITECTURE.md` until this sanity check has no blocking gaps or the user explicitly approves the known assumptions.

Each surface decision must carry a `feasibility_confidence` score (0–100):
- **≥ 80**: grounded in source or verified reference — proceed normally.
- **50–79**: assumption-based or partially verified — mark the decision as assumption-based, add a verification task for plan/validate.
- **< 50**: insufficient grounding — block and research before proceeding.

## Pre-Approval Pattern-Fit Check

Before presenting the architecture for approval, write a preliminary `WORKFLOW_CONTRACT.json` (or update the existing one) with the proposed `surfaceDecisions`, then run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pattern-fit-linter.py" WORKFLOW_CONTRACT.json
```

If the linter flags violations, address them before showing the architecture to the user. Do not present a design that fails pattern-fit. Warnings may be shown to the user with explanation.

## Blunt Critique

Do not oversimplify and do not over-engineer.

If a proposed design uses excessive agents, phases, tools, middleware, or source patches for a simple outcome, say that it is over-engineered and propose the smaller design. If the user asks for something impossible, say it is not feasible and explain the runtime boundary. If the idea is feasible but should be implemented differently, offer the amended workflow freely.

## User Revision Loop

If the user rejects the recommendation or proposes an alternative:

1. Restate their alternative.
2. Classify feasibility.
3. Explain how it would actually work.
4. Identify impossible or expensive parts.
5. Offer a corrected version if one exists.
6. Ask whether to adopt the amended design.

Do not advance until the user approves a design.

## Outputs

After approval:

- write `DESIGN.md`, including the architecture sanity check decisions and selected/rejected runtime surfaces
- write `ARCHITECTURE.md`, including component placement, middleware/hook/tool/agent boundaries, and data/control flow
- update `WORKFLOW_CONTRACT.json` with design status, selected runtime surfaces, feasibility tier, approved components, `design.requirements`, and `design.surfaceDecisions`
- produce a mermaid diagram of the complete approved workflow as `SystemName-ORIGINAL.md`, showing end-to-end flow including all phases, gates, surfaces, and data/control paths; double-check that the diagram truthfully matches the approved design before writing it

Then hand off to `vibe-workflow:plan`.
