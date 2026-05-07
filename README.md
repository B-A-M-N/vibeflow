# VibeFlow

Claude Code plugin for conceptualizing, designing, implementing, updating, and validating complex Mistral Vibe workflows.

VibeFlow is for workflows where a generic prompt is not enough: multi-phase automation, custom skills, tools, MCP/connectors, middleware, hooks, agent profiles, subagents, source-level changes, and validation evidence. Its job is to preserve design freedom while forcing every selected runtime surface to be grounded in what Mistral Vibe can actually do.

## Core Idea

VibeFlow separates two questions that often get mixed together:

1. What is the best workflow design for this task?
2. Which Mistral Vibe runtime surfaces can honestly implement that design?

The plugin should not tell the agent to use every possible customization point. It should choose the smallest sufficient surface, explain why it fits, reject unnecessary surfaces with rationale, and record enough evidence that implementation oversight is visible later.

## Lifecycle

1. **init** — interactive intent loop. Completes only after user sign-off and generation of `VISION.md`, `PLAN.md`, and `WORKFLOW_CONTRACT.json`.
2. **design** — maps signed intent onto real Mistral Vibe runtime surfaces. Produces component breakdowns, diagrams, feasibility classification, design decisions, rejected alternatives, and approval-ready artifacts.
3. **plan** — researches source/docs as needed and produces implementation targets, component contracts, tests, and validation gates.
4. **apply** — writes or patches files according to the approved plan. Runs a pre-apply surface guard to enforce the contract before any file is touched.
5. **validate** — runs the serial validation chain, writes evidence, classifies failures, detects drift, and reports whether the workflow is ready or needs rework.
6. **update** — modifies or hardens an existing workflow through narrative intake, repo/artifact scan, ambiguity clarification, proposed edits, approval, implementation, record updates, and validation.
7. **inspect** — audits an existing workflow/repo and persists an inspection report for later design/update work.
8. **realize** — ingests existing conceptual workflows, skillsets, plugin drafts, partially implemented repos, or design documents and converts them into working, runtime-grounded implementations.

## Runtime Grounding

VibeFlow's references model the current Mistral Vibe runtime surfaces, including:

- **Skills.** `allowed_tools` is advisory only — it is never used to filter `ToolManager.available_tools`. The model sees all available tools regardless. Use agent profile flat-TOML `enabled_tools` for actual restriction.
- **Built-in tools:** `ask_user_question`, `exit_plan_mode`, `todo`, `task`, `webfetch`, `websearch`. `ask_user_question` is disabled in programmatic (`-p`) and ACP execution contexts.
- **Tool contracts:** `BaseTool` class variables (`name`, `description` are `ClassVar[str]`), `invoke()` → `run()` call chain (no `__call__`), `BaseToolConfig`, `resolve_permission()`, `get_result_extra()`, `get_file_snapshot()`, `is_available()`, tool state (`BaseToolState`), and tool prompt files.
- **Tool placement:** Custom tools must be skill-bundled or in `config.tool_paths` — never in `vibe/core/tools/builtins/`. That directory is core infrastructure (bash, grep, read_file, etc.); placing workflow-specific tools there is a Tier D source modification.
- **Tool discovery:** Search path order is `[builtins, config.tool_paths, project .vibe/tools/, ~/.vibe/tools/]` — later entries override earlier ones. Discovery is recursive. Tool files whose filename starts with `_` are silently skipped.
- **MCP servers and Mistral Connectors** as distinct remote tool surfaces. Per-server `disabled` and `disabled_tools` controls.
- **Agent profiles:** `default`, `plan`, `accept-edits`, `auto-approve`, `chat`, and opt-in `lean`. The `chat` profile restricts to a fixed tool list (`grep`, `read_file`, `ask_user_question`, `task`) via `bypass_tool_permissions + enabled_tools` overrides — not a generic "read-only" mode. Profile overrides use flat TOML keys, not a nested `[overrides]` section. The `base_disabled` key merges with existing `disabled_tools` without replacing it. Agent TOML files must be directly in the search path root (not subdirectories), must use `.toml` extension, and the agent name is always the filename stem.
- **Per-phase model assignment** via agent profile `overrides` (`active_model`, `providers`, `models`) — no separate tool needed. Every model name referenced in a profile TOML must be declared as a model alias in `~/.vibe/config.toml` first.
- **Tool-triggered profile switching** through `ctx.switch_agent_callback`. `AgentProfileChangedEvent` is silently dropped by the ACP layer. Profile switching changes the system prompt but keeps the same context window — it is **not** subagent isolation.
- **Subagents** through the `task` tool. The built-in `explore` subagent is read-only by profile — this is not a hard runtime constraint on all subagents. Custom subagent profiles with write tools can write. Subagents never run hooks. `TaskResult.completed = False` on middleware stop or skipped tool call. True subagent isolation requires `task` to spawn a fresh AgentLoop with its own message history.
- **Hooks** as `POST_AGENT_TURN` only, via `hooks.toml` + `enable_experimental_hooks = true` (Tier A — no Python required). Exit-code semantics: `exit 2` + non-empty stdout = retry; `exit 2` + empty stdout = warning only, no retry. 3-retry ceiling per hook per user turn. Chain breaks on first retrying hook.
- **Middleware** as a duck-typed `ConversationMiddleware` Protocol (not an ABC). Must implement `before_turn(context)` and `reset(reset_reason)`. Registration requires modifying `_setup_middleware()` in source — Tier D. Stateless middleware may use `pass` for `reset()`.
- **Compaction:** `compact()` resets messages to `[system_message, summary_message]`. The system prompt is regenerated from the current agent profile each turn. Agent profile state survives compaction automatically — do not use `state.json` to persist phase across compaction. Middleware `reset()` receives `ResetReason.COMPACT` and must preserve state (only clear on `ResetReason.STOP`).
- **Config:** `bypass_tool_permissions` (not `auto_approve` — silently ignored), `system_prompt_id`, `enable_experimental_hooks`, `context_warnings`, `auto_compact_threshold` (global and per-model), `api_timeout`. `thinking` is per-model inside `[[models]]`. `session_prefix` lives under `[session_logging]`. All fields overridable via `VIBE_*` env vars.
- **Session scratchpad** (temp directory, non-deterministic path), AGENTS.md context injection, programmatic JSON/streaming output, and compaction model settings.

The main reference for this is `references/feasibility/runtime-pattern-catalog.md`.

## Middleware Model

Custom middleware is valid in Mistral Vibe. Multiple middleware can be composed.

The constraint is not whether middleware can exist; it is where it lives and when it runs. Middleware is a duck-typed `ConversationMiddleware` Protocol — no ABC to subclass. Registration requires modifying `_setup_middleware()` in `AgentLoop` source (Tier D). It cannot be registered through config, skills, or hooks alone.

Middleware must implement:

```python
async def before_turn(self, context: ConversationContext) -> MiddlewareResult: ...
def reset(self, reset_reason: ResetReason = ResetReason.STOP) -> None: ...
```

`before_turn()` runs before **every LLM call** in the tool loop — not once per user message. On a multi-tool turn it fires once per tool batch plus once for the final response. A hook retry also triggers another `before_turn()` on the next loop iteration.

`reset()` may be a no-op (`pass`) for stateless middleware. Stateful middleware must handle both `ResetReason.STOP` and `ResetReason.COMPACT`.

Middleware actions:

- `CONTINUE` — proceed.
- `STOP` — halt the agent turn entirely. No compaction.
- `COMPACT` — trigger context compaction, then **continue** the loop. Not the same as `STOP`.
- `INJECT_MESSAGE` — collect a message; all collected injections are joined with `\n\n` and injected before the LLM call.

Pipeline: `STOP` and `COMPACT` short-circuit and discard any previously accumulated `INJECT_MESSAGE` results. The default pipeline is `AutoCompactMiddleware` + two `ReadOnlyAgentMiddleware` instances (plan and chat). `TurnLimitMiddleware`, `PriceLimitMiddleware`, and `ContextWarningMiddleware` are conditional on their respective config flags.

## Phase I/O Contract

Every phase produces a machine-checkable artifact set that the next phase consumes without re-interpreting intent. No phase is allowed to silently upgrade, downgrade, or reinterpret the workflow.

**init produces:**
- `VISION.md` — locked intent, success criteria, scope boundary
- `PLAN.md` — signed phased plan
- `WORKFLOW_CONTRACT.json` — initial surface selections and rejections

**design consumes:** `WORKFLOW_CONTRACT.json`, `references/feasibility/*`
**design produces:** `DESIGN.md`, `ARCHITECTURE.md`, `SystemName-ORIGINAL.md` (mermaid diagram), `selected_surfaces[]`, `rejected_surfaces[]`, feasibility classification

**plan consumes:** `WORKFLOW_CONTRACT.json`, `DESIGN.md`, `ARCHITECTURE.md`
**plan produces:** updated `PLAN.md` with file targets, contracts, validation gates, expected evidence

**apply consumes:** `PLAN.md`, `DESIGN.md`, `ARCHITECTURE.md`, `WORKFLOW_CONTRACT.json`
**apply produces:** implementation files, `.vibe-workflow/workflow.yaml` or `.vibe-workflow/workflow.json`
**apply must not** change selected runtime surfaces unless it records a contract amendment first

**validate consumes:** repo state, `workflow.yaml` / manifest, `WORKFLOW_CONTRACT.json`, expected evidence
**validate produces:** validation report, evidence artifacts, drift classification

**realize consumes:** existing repo/artifacts/concepts, `references/feasibility/*`
**realize requires:** user confirmation of candidate selection → scope confirmation → fix plan approval before any file edits
**realize produces:** `REALIZATION_CONTRACT.json` (authoritative contract for this run), `CONCEPT_MAP.json`, `WORKFLOW_CONTRACT.json` stub if absent, implementation patches, `REALIZATION_REPORT.md`, `SystemName-ORIGINAL.md` (mermaid diagram), validation evidence

**update consumes:** existing artifacts, repo state, `WORKFLOW_CONTRACT.json`
**update produces:** `SystemName-PROPOSED#.md` or overwrites existing PROPOSED diagram, contract amendments, updated implementation files, `CHANGE_REQUEST.md`

## Design Contract

`WORKFLOW_CONTRACT.json` is the durable contract between phases. It records:

- signed intent and confidence;
- selected runtime surfaces;
- rejected or not-applicable surfaces;
- rationale for each decision;
- capability each selected surface provides;
- runtime contract each selected surface must obey;
- expected implementation evidence;
- validation proof requirements;
- update/change-control records.

This is how VibeFlow keeps creative freedom without allowing implementation drift. The schema does not force every workflow to include middleware, tools, hooks, agents, or MCP. It forces the workflow to justify the surfaces it does select and explain why others are unnecessary.

## Contract-Drift Rules

These rules are enforced by `apply`, `validate`, and `update`. They are what separates a governed workflow compiler from a prompt pack.

1. **`apply` must fail** if it implements a runtime surface not selected in `WORKFLOW_CONTRACT.json`. Record a contract amendment first or stop.
2. **`apply` must fail** if it omits a selected surface without a recorded contract amendment.
3. **`validate` must classify drift** as one of:
   - `missing_selected_surface` — a contracted surface has no implementation evidence
   - `unauthorized_surface_added` — an uncontracted surface was implemented
   - `wrong_runtime_surface` — the wrong Vibe extension point was used for a contracted capability
   - `impossible_runtime_assumption` — the implementation assumes a Vibe behavior that does not exist
   - `stale_evidence` — evidence artifacts exist but do not match current repo state
   - `validation_gap` — a contracted validation target has no corresponding check
4. **`update` is the only phase allowed to amend the contract** after initial sign-off.
5. **Every amendment must record:**
   - old surface
   - new surface
   - reason
   - affected files
   - required revalidation targets

## Pre-Apply Guard

Before `apply` writes any file, it must pass the surface guard (`scripts/pre-apply-guard.py`). The guard reads a `proposed_changes.json` describing every intended file edit, then verifies:

- every proposed surface is in the contract's selected surfaces
- no rejected surface is being implemented
- no selected surface is missing without a recorded deviation

The guard exits 0 (pass), 1 (violations — retry), or 2 (bad input). Apply runs the guard in a retry loop until exit 0. Writing implementation files before the guard passes defeats the contract.

## Validation

Validation runs through `scripts/validation-runner.py`. It executes checks serially, writes evidence even on failure, and avoids letting stale evidence masquerade as success.

The current validation chain includes:

- workflow schema/lifecycle linting (`workflow-linter.py`)
- failure classification (`failure-classifier.py`)
- dry-run simulation with declared tool checks and retry events (`dry-run-simulator.py`)
- state invariant checking (`state-invariant-checker.py`)
- gate checks (`gate-engine.py`)
- design contract linting (`design-contract-linter.py`)
- pattern-fit linting (`pattern-fit-linter.py`)
- drift detection against approved surfaces (`drift-detector.py`)
- convergence scoring (`convergence-scorer.py`)
- evidence report generation (`evidence-reporter.py`)
- auto-rework generation on `NEEDS_REWORK` verdicts (`auto-rework-generator.py`)

Relative paths declared in `workflow.yaml` are resolved relative to the manifest location, not the shell's current working directory. This applies to evidence output, state paths, reports, and contract discovery.

Executable workflow manifests use the canonical schema in `references/workflow-manifest-schema.json`. Tooling accepts YAML or JSON and normalizes legacy aliases with warnings, but generators should emit canonical fields: `phase.id`, `phase.entry`, `phase.exit`, and `phase.retryLimit`.

## Pattern-Fit Checks

VibeFlow includes a linter (`scripts/pattern-fit-linter.py`) for common design mistakes, for example:

- using middleware as `after_tool`, `post_tool`, or tool-level interception;
- assuming `before_turn()` fires once per user message — it fires before every LLM call in the tool loop;
- selecting custom middleware without source/runtime registration in `_setup_middleware()`;
- treating `allowed_tools` in a skill as a hard tool-access boundary — it is advisory only;
- using `auto_approve` instead of `bypass_tool_permissions` in config;
- using hooks for pre-turn or mid-turn behavior — hooks are `POST_AGENT_TURN` only;
- writing `exit 2` in a hook without printing stdout — empty stdout is a warning, not a retry;
- assuming subagents inherit parent hooks — subagents never run hooks;
- selecting plan-mode behavior without `exit_plan_mode`;
- using `ask_user_question` in a workflow that runs headless or via ACP — it is disabled in both contexts;
- using generic user prompts where `ask_user_question` should provide structured choices;
- treating `todo` as durable audit state;
- treating scratchpad as canonical record storage or a project-relative path;
- enabling MCP `sampling_enabled` without justification;
- requiring reasoning visibility without checking model/backend support;
- designing interactive workflows without asking whether headless execution is required;
- placing custom workflow tools in `vibe/core/tools/builtins/` — that is core infrastructure, not a skill extension point;
- using `state.json` to persist phase across compaction — agent profile survives compaction natively;
- claiming subagent isolation while only switching profiles — profile switching keeps the same context window;
- referencing model names in agent profile TOMLs that are not declared in `~/.vibe/config.toml`.

## Mermaid Diagram Convention

VibeFlow produces mermaid diagrams as a sanity check that workflows actually work end-to-end, and to track what was tried across iterations.

**Naming:**
- `SystemName-ORIGINAL.md` — produced after initial workflow completion (design, apply, or realize)
- `SystemName-PROPOSED#.md` — produced before update work begins, where `#` is the iteration number

**When to overwrite vs. create new PROPOSED:**
- **Overwrite** the existing PROPOSED diagram when the update is an architectural fix within the same intent direction (e.g., fixing tool placement, correcting compaction behavior).
- **Create a new PROPOSED#** when the update represents a genuine change in intent direction (e.g., adding phases, changing fundamental topology).

**Validation:** Every diagram must be double-checked to ensure it truthfully represents the actual workflow end-to-end. If it doesn't match, fix the diagram or the implementation before proceeding.

## Concept Realization Mode

VibeFlow can ingest existing conceptual workflows, skillsets, plugin drafts, partially implemented repos, or design documents and convert them into working, runtime-grounded implementations.

This is not `init`. It starts from existing artifacts, not a blank intake. It is interactive: the user confirms what to work on, confirms the scope and intent, reviews the feasibility reflection, approves the fix plan, then the system executes.

The realization flow:

1. **Scan** — silently scan the repo, group findings into named candidates, display them, ask the user to choose one
2. **Scope confirmation** — present interpretation of the selected candidate's intent, ask targeted clarifying questions, wait for explicit user confirmation
3. **Feasibility reflection** — classify each component against real Vibe runtime surfaces using `references/feasibility/`; surface what cannot be implemented as stated and the nearest alternative
4. **Proposed fix plan** — present a numbered, file-specific list of changes; wait for user approval or adjustments
5. **Contract bootstrap** — write `REALIZATION_CONTRACT.json` as the authoritative contract for this run; create or stub `WORKFLOW_CONTRACT.json` if absent (partial implementations will not have one)
6. **Apply** — execute only the approved plan; record any deviations before making them
7. **Validate** — run validation against the realization contract; classify failures with the drift taxonomy; report honestly if validation cannot run

Because partial implementations will not have a complete `WORKFLOW_CONTRACT.json`, `realize` bootstraps one from what it finds. Validation uses `REALIZATION_CONTRACT.json` as the authoritative contract source rather than failing on a missing or incomplete prior contract.

Classification buckets:

| Bucket | Example |
|---|---|
| `implemented` | Valid skill prompt, valid command file already wired |
| `maps_to_existing_surface` | Approval loop via plan profile + `exit_plan_mode` |
| `requires_custom_tool` | Evidence writer, manifest generator |
| `requires_mcp_connector` | Remote knowledge server, external API bridge |
| `requires_source_modification` | Middleware registration, custom AgentLoop hook |
| `not_implementable_as_stated` | "middleware after every tool call" — no Vibe hook exists for this |

## Usage

Load the plugin directly:

```bash
claude --plugin-dir /path/to/VibeFlow
```

### Sync To Claude Profiles

Claude Code installs plugins per config root. If you use alternate homes such as `~/.claude-openrouter-1`, sync VibeFlow explicitly:

```bash
python3 /path/to/VibeFlow/scripts/install-to-claude-profiles.py
python3 /path/to/VibeFlow/scripts/install-to-claude-profiles.py --apply --install-cache
```

The first command is a dry run. The second syncs `~/.claude` and detected `~/.claude-openrouter*` profiles, enables `vibe-flow@local`, and refreshes Claude's plugin cache where possible.

## Commands

| User command | Backing skill | Purpose |
|---|---|---|
| `/vibe-workflow-init` | `skills/vibe-workflow-init/SKILL.md` | Lock intent and emit `VISION.md`, `PLAN.md`, `WORKFLOW_CONTRACT.json` |
| `/vibe-workflow-design` | `skills/vibe-workflow-design/SKILL.md` | Map intent to feasible runtime topology and diagrams |
| `/vibe-workflow-plan` | `skills/vibe-workflow-plan/SKILL.md` | Research source/docs and produce implementation file targets |
| `/vibe-workflow-apply` | `skills/vibe-workflow-apply/SKILL.md` | Patch or write files from the approved plan (with pre-apply guard) |
| `/vibe-workflow-validate` | `skills/vibe-workflow-validate/SKILL.md` | Prove the result works or explain exactly why not |
| `/vibe-workflow-update` | `skills/vibe-workflow-update/SKILL.md` | Change-control loop for modifying or hardening existing workflows |
| `/vibe-workflow-inspect` | `skills/vibe-workflow-inspect/SKILL.md` | Inspect an existing repo/workflow state |
| `/vibe-workflow-realize` | `skills/vibe-workflow-realize/SKILL.md` | Realize a conceptual workflow, skillset, or partial implementation |

Example sequence:

```text
/vibe-workflow-init
/vibe-workflow-design
/vibe-workflow-plan
/vibe-workflow-apply
/vibe-workflow-validate
```

For existing workflows:

```text
/vibe-workflow-inspect
/vibe-workflow-update
/vibe-workflow-validate
```

For conceptual or partially implemented work:

```text
/vibe-workflow-realize
/vibe-workflow-validate
```

## Self-Test

```bash
PYTHONPYCACHEPREFIX=/tmp/vibeflow-pycache python3 -m py_compile scripts/*.py
python3 -m json.tool references/manifest-schema.json
python3 -m json.tool references/diagrams/diagram-index.json
PYTHONPYCACHEPREFIX=/tmp/vibeflow-pycache python3 -m unittest discover -s tests -v
```

`PYTHONPYCACHEPREFIX` is useful in restricted environments where the repo cannot write `__pycache__`.

## Repository Layout

- `commands/` — user-facing slash command definitions.
- `skills/` — command backing instructions loaded by Claude Code.
- `references/` — shared Mistral Vibe runtime and feasibility knowledge.
- `references/feasibility/` — runtime contracts, pattern catalog, configuration keys, composition rules, implementation patterns, and event system reference.
- `references/diagrams/` — Mermaid diagrams plus machine-readable diagram index.
- `scripts/` — validators, linters, simulators, drift detection, contract enforcement, install/sync tooling.
- `tests/` — regression tests for workflow tooling and plugin guarantees.

## Target Audience

VibeFlow is for advanced Mistral Vibe users building:

- multi-phase workflow commands;
- quality gates and approval loops;
- middleware-backed runtime behavior;
- custom tools and tool orchestration;
- MCP or connector integrations;
- CI validation flows and programmatic automation;
- source-level Mistral Vibe customizations.

It is not intended as a beginner Mistral AI guide.

## Status

VibeFlow is still hardening. The current focus is validation integrity, runtime-surface accuracy, update/inspect loops, prevention of plausible but non-functional designs, and pattern-fit enforcement.
