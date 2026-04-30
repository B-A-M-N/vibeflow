# VibeFlow

Claude Code plugin for conceptualizing, designing, implementing, updating, and validating complex Mistral Vibe workflows.

VibeFlow is for workflows where a generic prompt is not enough: multi-phase automation, custom skills, tools, MCP/connectors, middleware, hooks, agent profiles, subagents, source-level changes, and validation evidence. Its job is to preserve design freedom while forcing every selected runtime surface to be grounded in what Mistral Vibe can actually do.

## Core Idea

VibeFlow separates two questions that often get mixed together:

1. What is the best workflow design for this task?
2. Which Mistral Vibe runtime surfaces can honestly implement that design?

The plugin should not tell the agent to use every possible customization point. It should choose the smallest sufficient surface, explain why it fits, reject unnecessary surfaces with rationale, and record enough evidence that implementation oversight is visible later.

## Lifecycle

1. **init** - interactive intent loop. Completes only after user sign-off and generation of `VISION.md`, `PLAN.md`, and `WORKFLOW_CONTRACT.json`.
2. **design** - maps signed intent onto real Mistral Vibe runtime surfaces. Produces component breakdowns, diagrams, feasibility classification, design decisions, rejected alternatives, and approval-ready artifacts.
3. **plan** - researches source/docs as needed and produces implementation targets, component contracts, tests, and validation gates.
4. **apply** - writes or patches files according to the approved plan and preserves the selected runtime surfaces from the contract.
5. **validate** - runs the serial validation chain, writes evidence, classifies failures, detects drift, and reports whether the workflow is ready or needs rework.
6. **update** - modifies or hardens an existing workflow through narrative intake, repo/artifact scan, ambiguity clarification, proposed edits, approval, implementation, record updates, and validation.
7. **inspect** - audits an existing workflow/repo and persists an inspection report for later design/update work.

## Runtime Grounding

VibeFlow’s references model the current Mistral Vibe runtime surfaces, including:

- Skills, including `allowed_tools` as a real partial enforcement boundary.
- Built-in tools such as `ask_user_question`, `exit_plan_mode`, `todo`, `task`, `webfetch`, and `websearch`.
- Tool contracts: `BaseTool` generics, `BaseToolConfig`, `resolve_permission()`, `get_result_extra()`, tool state, and tool prompt files.
- MCP servers and Mistral Connectors as distinct remote tool surfaces.
- Agent profiles and tool-triggered profile switching through `switch_agent_callback`.
- Subagents through the `task` tool, with the constraint that subagents return text and the parent writes files.
- Hooks as `POST_AGENT_TURN` only, including transcript access and exit-code retry semantics.
- Middleware as source/runtime-code components implementing `before_turn(context)` and `reset()`.
- Session scratchpad, AGENTS.md context injection, programmatic JSON/streaming output, model thinking levels, and compaction model settings.

The main reference for this is `references/feasibility/runtime-pattern-catalog.md`.

## Middleware Model

Custom middleware is valid in Mistral Vibe. Multiple middleware can be composed.

The constraint is not whether middleware can exist; it is where it lives and when it runs. Custom middleware must be implemented as runtime/source code and registered with the middleware pipeline. It is not created by a skill, hook, or manifest alone.

Generated middleware must implement:

```python
async def before_turn(self, context: ConversationContext) -> MiddlewareResult: ...
def reset(self, reset_reason: ResetReason = ResetReason.STOP) -> None: ...
```

`before_turn()` runs before every LLM call in the tool loop. It cannot intercept during tool execution, after tool results, or arbitrary events unless the runtime source is changed to add that boundary.

Middleware actions:

- `CONTINUE` - proceed.
- `STOP` - halt the agent turn.
- `COMPACT` - trigger compaction.
- `INJECT_MESSAGE` - inject a user-role message.

Pipeline composition matters: `STOP` and `COMPACT` short-circuit immediately; multiple `INJECT_MESSAGE` results are merged.

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

## Validation

Validation runs through `scripts/validation-runner.py`. It executes checks serially, writes evidence even on failure, and avoids letting stale evidence masquerade as success.

The current validation chain includes:

- workflow schema/lifecycle linting;
- failure classification;
- dry-run simulation with declared tool checks and retry events;
- state invariant checking;
- gate checks;
- design contract linting;
- pattern-fit linting;
- drift detection against approved surfaces;
- convergence scoring;
- evidence report generation.

Relative paths declared in `workflow.yaml` are resolved relative to the manifest location, not the shell’s current working directory. This applies to evidence output, state paths, reports, and contract discovery.

Executable workflow manifests use the canonical schema in `references/workflow-manifest-schema.json`. Tooling accepts YAML or JSON and normalizes legacy aliases with warnings, but generators should emit canonical fields: `phase.id`, `phase.entry`, `phase.exit`, and `phase.retryLimit`.

## Pattern-Fit Checks

VibeFlow includes a linter for common design mistakes, for example:

- using middleware as `after_tool`, `post_tool`, or tool-level interception;
- selecting custom middleware without source/runtime registration;
- assigning file writes to a subagent;
- using hooks for pre-turn or mid-turn behavior;
- selecting plan-mode behavior without `exit_plan_mode`;
- using generic user prompts where `ask_user_question` should provide structured choices;
- treating `todo` as durable audit state;
- treating scratchpad as canonical record storage;
- enabling MCP `sampling_enabled` without justification;
- requiring reasoning visibility without checking model/backend support.

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
| `/vibe-workflow-apply` | `skills/vibe-workflow-apply/SKILL.md` | Patch or write files from the approved plan |
| `/vibe-workflow-validate` | `skills/vibe-workflow-validate/SKILL.md` | Prove the result works or explain exactly why not |
| `/vibe-workflow-update` | `skills/vibe-workflow-update/SKILL.md` | Change-control loop for modifying or hardening existing workflows |
| `/vibe-workflow-inspect` | `skills/vibe-workflow-inspect/SKILL.md` | Inspect an existing repo/workflow state |

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

## Self-Test

```bash
PYTHONPYCACHEPREFIX=/tmp/vibeflow-pycache python3 -m py_compile scripts/*.py
python3 -m json.tool references/manifest-schema.json
python3 -m json.tool references/diagrams/diagram-index.json
PYTHONPYCACHEPREFIX=/tmp/vibeflow-pycache python3 -m unittest discover -s tests -v
```

`PYTHONPYCACHEPREFIX` is useful in restricted environments where the repo cannot write `__pycache__`.

## Repository Layout

- `commands/` - user-facing slash command definitions.
- `skills/` - command backing instructions loaded by Claude Code.
- `references/` - shared Mistral Vibe runtime and feasibility knowledge.
- `references/feasibility/` - runtime contracts, pattern catalog, configuration keys, and composition rules.
- `references/diagrams/` - Mermaid diagrams plus machine-readable diagram index.
- `scripts/` - validators, linters, simulators, drift detection, install/sync tooling.
- `tests/` - regression tests for workflow tooling and plugin guarantees.

## Target Audience

VibeFlow is for advanced Mistral Vibe users building:

- multi-phase workflow commands;
- quality gates and approval loops;
- middleware-backed runtime behavior;
- custom tools and tool orchestration;
- MCP or connector integrations;
- PR bots, ACP automation, and CI validation flows;
- source-level Mistral Vibe customizations.

It is not intended as a beginner Mistral AI guide.

## Status

VibeFlow is still hardening. The current focus is validation integrity, runtime-surface accuracy, update/inspect loops, and prevention of plausible but non-functional designs.
