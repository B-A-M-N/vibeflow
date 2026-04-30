# VibeFlow

Claude Code plugin for conceptualizing, designing, implementing, and validating advanced Mistral Vibe workflows.

VibeFlow assumes one Claude Code model runs the process. It is organized around command modes, persistent artifacts, shared Mistral Vibe runtime knowledge, feasibility checks, and deterministic validation gates.

## Lifecycle

1. **init** - interactive intent loop. Completes only after user sign-off and generation of `VISION.md`, `PLAN.md`, and `WORKFLOW_CONTRACT.json`.
2. **design** - maps signed intent onto real Mistral Vibe runtime surfaces. Produces plain-English component breakdowns, diagrams, feasibility classification, and design artifacts for approval.
3. **plan** - researches DeepWiki/source context as needed and produces implementation file targets, contracts, tests, and validation gates.
4. **apply** - writes or patches files according to the approved plan, including generation or repair of required workflow tooling.
5. **validate** - proves the result works through runnable tooling and evidence, or reports exactly why it does not.
6. **update** - modifies or hardens an existing workflow through narrative intake, artifact scan, ambiguity clarification, approved proposal, edits, record updates, and validation.

Executable workflow manifests use one canonical schema in `references/workflow-manifest-schema.json`. Validation tooling accepts YAML or JSON and normalizes legacy aliases with warnings, but generators should emit canonical fields: `phase.id`, `phase.entry`, `phase.exit`, and `phase.retryLimit`.

VibeFlow must produce complete working workflows, not plausible design documents. A workflow is incomplete until artifacts exist, the manifest schema validates, the required tooling contract is present, dry-run execution consumes the generated `workflow.yaml`, evidence is written to `.vibe-workflow/evidence/latest.json` or the manifest's declared evidence output, and the validation report is based on that runnable evidence.

Validation runs through `scripts/validation-runner.py`, which executes checks serially, aggregates all failures, classifies failure domain, and writes evidence even when validation fails.

## Feasibility Model

Every lifecycle phase uses the shared feasibility substrate:

- Extension Point Taxonomy / Tiers A-E
- Key Interfaces & Contracts
- Workflow Pattern Library
- Event System Reference
- Configuration Keys for Workflow Control
- Tier Composition Patterns
- Diagnostic & Observability

The plugin treats source customization as valid, but it must label when a workflow requires Mistral Vibe internals instead of pretending it can be done with normal skills or config.

## Design Stance

Design advice should be grounded and blunt. If a proposal is over-engineered, underspecified, impossible, or possible only through a different implementation shape, VibeFlow should say that plainly and offer the smallest workable alternative.

## Usage

Load the plugin:
```bash
claude --plugin-dir /path/to/VibeFlow
```

### Sync to Claude profiles

Claude Code installs plugins per config root. If you use alternate homes such as `~/.claude-openrouter-1`, sync VibeFlow explicitly:

```bash
python3 /path/to/VibeFlow/scripts/install-to-claude-profiles.py
python3 /path/to/VibeFlow/scripts/install-to-claude-profiles.py --apply --install-cache
```

The first command is a dry run. The second syncs `~/.claude` and detected `~/.claude-openrouter*` profiles, enables `vibe-flow@local`, and refreshes Claude's plugin cache where possible.

### Start a workflow
```
/vibe-workflow-init
```
Run the signed intent loop. This is the first command. It ends only after user approval and generation of `VISION.md`, `PLAN.md`, and `WORKFLOW_CONTRACT.json`.

### Design a workflow
```
/vibe-workflow-design
```
Map the signed intent to a valid Mistral Vibe runtime topology.

### Apply a workflow
```
/vibe-workflow-apply
```
Apply this workflow to PR #123

### Validate a workflow
```
/vibe-workflow-validate
```
Validate this workflow before I use it for ACP PR bot

### Update a workflow
```
/vibe-workflow-update
```
Review an existing workflow against its goal, clarify the requested change, propose edits for approval, apply approved modifications, update lifecycle records, and validate.

### Self-test the plugin
```bash
python3 -m unittest discover -s tests -v
```

## Target Audience

Advanced Mistral Vibe users building:
- Multi-phase command workflows
- Middleware-controlled behavior and tool orchestration
- Automation like PR bots or ACP integrations
- Source-level Mistral Vibe customizations

Not for general Mistral AI users or beginners.

## Files

- `commands/` - user-facing slash command definitions
- `skills/` - command backing instructions loaded by Claude Code
- `references/` - shared Mistral Vibe runtime and feasibility knowledge
- `references/feasibility/` - shared feasibility substrate
- `references/diagrams/` - Mermaid diagrams plus machine-readable diagram index

## Active Commands And Skills

These are the active lifecycle pairs:

| User command | Backing skill | Purpose |
|---|---|---|
| `/vibe-workflow-init` | `skills/vibe-workflow-init/SKILL.md` | lock intent and emit `VISION.md`, `PLAN.md`, `WORKFLOW_CONTRACT.json` |
| `/vibe-workflow-design` | `skills/vibe-workflow-design/SKILL.md` | map intent to feasible runtime topology and diagrams |
| `/vibe-workflow-plan` | `skills/vibe-workflow-plan/SKILL.md` | research source/docs and produce implementation file targets |
| `/vibe-workflow-apply` | `skills/vibe-workflow-apply/SKILL.md` | patch or write files from the approved plan |
| `/vibe-workflow-validate` | `skills/vibe-workflow-validate/SKILL.md` | prove the result works or explain exactly why not |
| `/vibe-workflow-update` | `skills/vibe-workflow-update/SKILL.md` | change-control loop for modifying or hardening existing workflows |
| `/vibe-workflow-inspect` | `skills/vibe-workflow-inspect/SKILL.md` | inspect an existing repo/workflow state |

There is no separate `mistral-vibe-workflow` skill. Mistral Vibe knowledge lives in `references/` so every phase uses the same grounding.

## Future

Once stabilized, could be published to the marketplace for other advanced Vibe users.
