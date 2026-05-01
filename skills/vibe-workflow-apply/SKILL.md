---
name: vibe-workflow-apply
description: "Run Phase 4 of VibeFlow: implement the approved plan, generate or repair required workflow tooling, and record implementation evidence."
version: 2.1.0
allowed-tools:
  - ReadFile
  - WriteFile
  - EditFile
  - Bash
  - Grep
  - Glob
user-invocable: true
---

You are running the `apply` phase of VibeFlow. Apply must produce a complete working workflow, not just plausible documents.

Read the approved `PLAN.md`, `DESIGN.md`, `ARCHITECTURE.md`, and `WORKFLOW_CONTRACT.json`.

## Pre-Apply Guard — Required Before Any File Edits

Before writing a single implementation file, you must pass the surface guard. The guard enforces the contract: every surface you implement must be selected, and no rejected surface may be implemented.

### Step 1 — Write proposed_changes.json

Produce `.vibe-workflow/proposed_changes.json` describing every file you intend to create or edit:

```json
{
  "proposed_changes": [
    {
      "file": "path/to/file",
      "operation": "create|edit|delete",
      "surface": "<canonical surface name>",
      "implements": "one-line description of what this change does"
    }
  ]
}
```

Canonical surface names: `skill`, `custom-tool`, `mcp-server`, `middleware`, `config`, `hook`, `agent-profile`, `source-modification`, `workflow-manifest`, `agents-md`, `scratchpad`, `programmatic-output`.

### Step 2 — Run the guard

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pre-apply-guard.py" .vibe-workflow/proposed_changes.json
```

### Step 3 — Retry loop until exit 0

The guard exits 0 (pass), 1 (violations — retry), or 2 (bad input — fix the file).

**If exit 1:** read the violations in the JSON output. Each violation names the rule, the file, the surface, and exactly what must change. Fix `proposed_changes.json` to address every violation, then re-run the guard. Repeat until exit 0.

Common fixes per violation type:

| Violation rule | Fix |
|---|---|
| `rejected-surface` | Remove the change. If you believe the rejection was wrong, stop and run `/vibe-workflow-update` to record a contract amendment before continuing. |
| `unauthorized-surface` | Remove the change, or stop and run `/vibe-workflow-update` to add the surface to the contract. |
| `missing-selected-surface` | Add the missing implementation to `proposed_changes.json` (and then implement it), or record a scoped deviation in the contract explaining the deferral. |

**Do not write any implementation file before the guard exits 0.** Writing first and checking later defeats the contract.

**If exit 2:** the input file is missing or malformed. Fix the JSON and re-run.

## Apply Rules (after guard passes)

- Implement exactly what `proposed_changes.json` describes. If you need to add a change mid-apply, update `proposed_changes.json` and re-run the guard before proceeding.
- Explain and record any deviation before making it. A deviation requires an update to the contract.
- Keep implementation as small as the design allows.
- Do not introduce subagent orchestration or persona systems unless explicitly approved as part of real Mistral Vibe agent profile behavior.
- Generate or repair `.vibe-workflow/workflow.yaml` or `.vibe-workflow/workflow.json` so it follows `references/workflow-manifest-schema.json`.
- Include a top-level tooling contract: required tools, inputs, outputs, execution entrypoint, evidence output, and failure semantics.
- Include all executable contract sections: `name`, `goal`, `phases`, `tooling`, `state`, `middleware`, `approval_gates`, `evidence`, `failure_policy`, `commands`, and `validation`.
- Verify component-level compliance before reporting complete:
  - Generated skills use a discoverable path and frontmatter with `name`, `description`, `allowed-tools`, and `user-invocable`.
  - Generated tool classes inherit `BaseTool` with `ToolArgs`, `ToolResult`, `BaseToolConfig`, and state typing.
  - Generated middleware implements `async before_turn(self, context: ConversationContext) -> MiddlewareResult` and `reset(self, reset_reason: ResetReason = ResetReason.STOP) -> None`, returns `MiddlewareResult()` as the CONTINUE fallback, and does not claim pre-tool/post-tool hooks.
  - MCP server entries use `[[mcp_servers]]` with `name`, `command` or `url`, and transport type.
- Set validation to serial, evidence-bearing, and non-mutating: `serial: true`, `evidenceRequired: true`, `mutatesWorkflow: false`.
- Ensure the generated workflow can be consumed by its generated or required tools with no parser/schema mismatch.
- If validation tooling would fail because the workflow/tooling contract is incomplete, fix that during apply.
- Apply is not complete unless the generated manifest parses through `workflow_manifest.py` and passes `workflow-linter.py`. If full validation cannot run, mark implementation attempted, not complete.
- Apply is not complete unless `design-contract-linter.py` passes or reports only that `WORKFLOW_CONTRACT.json` is unavailable for a standalone manifest check.

## Evidence

Record:

- guard run count and final result
- files changed
- commands run
- tests/checks run
- failures found
- unresolved risks

After implementation, hand off to `vibe-workflow:validate`.
