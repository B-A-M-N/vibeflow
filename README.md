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
2. **design** — maps signed intent onto real Mistral Vibe runtime surfaces. Compares grounded candidate architectures, lints the candidate set, then promotes the winning candidate into component breakdowns, diagrams, feasibility classification, design decisions, rejected alternatives, and approval-ready artifacts.
3. **plan** — researches source/docs as needed and produces implementation targets, component contracts, tests, and validation gates.
4. **apply** — writes or patches files according to the approved plan. Runs a pre-apply surface guard to enforce the contract before any file is touched.
5. **validate** — runs the serial validation chain, writes evidence, classifies failures, detects drift, and reports whether the workflow is ready or needs rework.
6. **update** — modifies or hardens an existing workflow through narrative intake, repo/artifact scan, ambiguity clarification, proposed edits, approval, implementation, record updates, and validation.
7. **inspect** — audits an existing workflow/repo and persists an inspection report for later design/update work.
8. **realize** — ingests existing conceptual workflows, skillsets, plugin drafts, partially implemented repos, or design documents and converts them into working, runtime-grounded implementations.

## Runtime Grounding

VibeFlow's references model the current Mistral Vibe runtime surfaces. Key points:

- **Skills:** `allowed_tools` is advisory only. Use agent profile `enabled_tools` for actual restriction.
- **Middleware:** A loop guard, not a phase orchestrator. `before_turn()` fires before every LLM call in the tool loop (N+1 times per multi-tool turn). Registration requires source modification (Tier D).
- **Hooks:** `POST_AGENT_TURN` only. Exit 2 + non-empty stdout = retry. 3-retry ceiling per hook per turn.
- **Agent profiles:** Per-phase tool enforcement via `enabled_tools`/`disabled_tools`. Profile switching is NOT subagent isolation.
- **Compaction:** Agent profile survives natively. `todo` state does not. Persist important state to disk.

**Full reference:** `references/feasibility/runtime-pattern-catalog.md`

**Agent runtime model:** `references/feasibility/agent-runtime-model.md`

**Implementation patterns:** `references/feasibility/implementation-patterns.md`

**Key interfaces:** `references/feasibility/key-interfaces-contracts.md`

## Phase I/O Contract

Every phase produces a machine-checkable artifact set that the next phase consumes without re-interpreting intent.

| Phase | Consumes | Produces |
|-------|----------|----------|
| init | User interaction | `VISION.md`, `PLAN.md`, `WORKFLOW_CONTRACT.json` |
| design | `WORKFLOW_CONTRACT.json`, `references/feasibility/*` | `DESIGN_CANDIDATES.json`, `DESIGN.md`, `ARCHITECTURE.md`, diagram |
| plan | `WORKFLOW_CONTRACT.json`, `DESIGN.md`, `ARCHITECTURE.md` | Updated `PLAN.md` with file targets, contracts, validation gates |
| apply | `PLAN.md`, `DESIGN.md`, `ARCHITECTURE.md`, `WORKFLOW_CONTRACT.json` | Implementation files, workflow manifest |
| validate | Repo state, manifest, `WORKFLOW_CONTRACT.json` | Validation report, evidence, drift classification |
| realize | Existing artifacts, `references/feasibility/*` | `REALIZATION_CONTRACT.json`, implementation patches, report |

## Design Contract

`WORKFLOW_CONTRACT.json` is the durable contract between phases. It records signed intent, selected/rejected runtime surfaces, rationale, capabilities, contracts, evidence targets, and change-control records.

The schema does not force every workflow to include every surface. It forces the workflow to justify the surfaces it selects and explain why others are unnecessary.

**Schema:** `references/manifest-schema.json`

## Contract-Drift Rules

1. `apply` must fail if it implements a surface not selected in the contract.
2. `apply` must fail if it omits a selected surface without a recorded amendment.
3. `validate` must classify drift (missing surface, unauthorized surface, wrong surface, impossible assumption, stale evidence, validation gap).
4. `update` is the only phase allowed to amend the contract after initial sign-off.

## Examples

See `references/examples/` for workflow examples and the archetype catalog. **Start with the archetype guide** (`references/examples/archetypes/`) to identify which workflow shape fits your task before looking at any specific example.

## Usage

Load the plugin directly:

```bash
claude --plugin-dir /path/to/VibeFlow
```

### Sync To Claude Profiles

```bash
python3 /path/to/VibeFlow/scripts/install-to-claude-profiles.py
python3 /path/to/VibeFlow/scripts/install-to-claude-profiles.py --apply --install-cache
```

## Commands and Skills

VibeFlow uses two layers of instructions:

- **`commands/`** — User-facing slash command definitions. Each command file has YAML frontmatter (`name`, `description`) that Claude Code uses to decide when to offer the command. The command body is a brief pointer to the backing skill. These files are **not** the detailed instructions; they are the entry point.
- **`skills/`** — Detailed behavioral instructions loaded by Claude Code when a command is invoked. Each skill is a `SKILL.md` with YAML frontmatter (`name`, `description`, `allowed-tools`, `user-invocable`) plus the full step-by-step procedure the agent follows.

The command's `description` field is the **contextual trigger** — it tells Claude when this command is relevant. The skill's `description` provides additional matching context. Keep descriptions specific to avoid false triggers:

| Command | Trigger context | Backing skill |
|---|---|---|
| `/vibe-workflow-init` | Starting a new Mistral Vibe workflow from scratch | `skills/vibe-workflow-init/SKILL.md` |
| `/vibe-workflow-design` | Mapping workflow intent to runtime topology | `skills/vibe-workflow-design/SKILL.md` |
| `/vibe-workflow-plan` | Creating implementation targets from a design | `skills/vibe-workflow-plan/SKILL.md` |
| `/vibe-workflow-apply` | Writing/patching files from an approved plan | `skills/vibe-workflow-apply/SKILL.md` |
| `/vibe-workflow-validate` | Proving a workflow works with evidence | `skills/vibe-workflow-validate/SKILL.md` |
| `/vibe-workflow-update` | Modifying or hardening an existing workflow | `skills/vibe-workflow-update/SKILL.md` |
| `/vibe-workflow-inspect` | Auditing an existing repo or workflow | `skills/vibe-workflow-inspect/SKILL.md` |
| `/vibe-workflow-realize` | Converting a concept/partial into a working workflow | `skills/vibe-workflow-realize/SKILL.md` |

**Trigger design principle:** Descriptions should mention "Mistral Vibe" and "workflow" to avoid firing on unrelated tasks. They should not mention generic terms like "design" or "plan" alone, which would trigger on non-VibeFlow work.

Example sequence:

```text
/vibe-workflow-init
/vibe-workflow-design
/vibe-workflow-plan
/vibe-workflow-apply
/vibe-workflow-validate
```

## Self-Test

```bash
PYTHONPYCACHEPREFIX=/tmp/vibeflow-pycache python3 -m py_compile scripts/*.py
python3 -m json.tool references/manifest-schema.json
PYTHONPYCACHEPREFIX=/tmp/vibeflow-pycache python3 -m unittest discover -s tests -v
```

## Repository Layout

- `commands/` — user-facing slash command definitions.
- `skills/` — command backing instructions loaded by Claude Code.
- `references/` — shared Mistral Vibe runtime and feasibility knowledge.
- `references/feasibility/` — runtime contracts, pattern catalog, implementation patterns, key interfaces, and Mermaid diagrams.
- `references/examples/` — workflow examples and archetype catalog.
- `scripts/` — validators, linters, simulators, drift detection, contract enforcement, install/sync tooling.
- `tests/` — regression tests for workflow tooling and plugin guarantees.

## Target Audience

VibeFlow is for advanced Mistral Vibe users building multi-phase workflow commands, quality gates, custom tools, MCP integrations, middleware-backed behavior, and source-level customizations.

It is not intended as a beginner Mistral AI guide.

## Status

VibeFlow is still hardening. The current focus is validation integrity, runtime-surface accuracy, update/inspect loops, prevention of plausible but non-functional designs, and pattern-fit enforcement.
