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
  - Generated skills use a discoverable path and frontmatter with `name`, `description`, `allowed-tools`, and `user-invocable`. Note: `allowed-tools` is advisory only and does not restrict what tools the model can call — use `enabled_tools` in an agent profile TOML for actual restriction.
  - Generated tool classes inherit `BaseTool` with `ToolArgs`, `ToolResult`, `BaseToolConfig`, and state typing. If the tool's permission is `"ask"` and there is no `approval_callback` wired (programmatic mode, subagent without allowlist), the tool is **silently skipped** — `ToolResultEvent.skipped = True`, no exception. Tools that must execute in these contexts must use `permission: "always"` or override `resolve_permission()` to return `"always"`.
  - Generated middleware implements `async before_turn(self, context: ConversationContext) -> MiddlewareResult` and `reset(self, reset_reason: ResetReason = ResetReason.STOP) -> None`, returns `MiddlewareResult()` as the CONTINUE fallback, and does not claim pre-tool/post-tool hooks.
  - MCP server entries use `[[mcp_servers]]` with `name`, `command` or `url`, and transport type.
  - Generated skills must have a `name` field that matches the directory name and follows the pattern `^[a-z0-9]+(-[a-z0-9]+)*$`. Names like "PRForge" or "MySkill" are invalid. The skill directory name and frontmatter `name` must match exactly.
  - If the design requires scope enforcement (blocking file edits outside allowed patterns), this must be implemented as a custom `BaseTool` subclass with `resolve_permission()` or via the `approval_callback` mechanism — **never** as middleware. Middleware cannot intercept individual tool calls. **`enabled_tools` does NOT enforce file scope** — it only controls which tools the LLM can call, not which paths those tools can access. File-level scope requires per-tool allowlist/permission overrides in the agent profile, validation logic inside the phase-advance tool (e.g., `git diff --name-only` to reject out-of-scope modifications), or `resolve_permission()` on the tool.
  - If the design requires phase-gate enforcement, the phase transition must be triggered by a custom tool that calls `ctx.switch_agent_callback(profile_name)`. The new profile's `enabled_tools`/`disabled_tools` provides the actual enforcement. Do not rely on middleware or skill text alone for phase enforcement.
  - Custom tools must be skill-bundled or in config/tool_paths — **never** in `vibe/core/tools/builtins/`. That directory is core infrastructure; placing workflow-specific tools there is a Tier D source modification. Skill-bundled tool discovery works via `skill_dir/tools/` and `config.tool_paths` (recursive `rglob`), but always verify the tool actually loads — check the tool schema to confirm it appears.
  - **Tool name in `enabled_tools` must match `BaseTool.get_name()` exactly.** `get_name()` converts CamelCase to snake_case. A mismatch means the tool is silently absent from the LLM schema in that phase.
  - Do not implement a `state.json` mechanism for persisting phase across compaction. The active agent profile survives compaction automatically. If the design calls for phase to survive compaction, encode the phase in the active agent profile, not in a state file read each turn.
  - If the design claims subagent or per-phase isolation, verify it uses the `task` tool to spawn a fresh AgentLoop — not just profile switching within one loop.
- Set validation to serial, evidence-bearing, and non-mutating: `serial: true`, `evidenceRequired: true`, `mutatesWorkflow: false`.
- Ensure the generated workflow can be consumed by its generated or required tools with no parser/schema mismatch.
- If validation tooling would fail because the workflow/tooling contract is incomplete, fix that during apply.
- Apply is not complete unless the generated manifest parses through `workflow_manifest.py` and passes `workflow-linter.py`. If full validation cannot run, mark implementation attempted, not complete.
- Apply is not complete unless `design-contract-linter.py` passes or reports only that `WORKFLOW_CONTRACT.json` is unavailable for a standalone manifest check.

## Post-Implementation Diagram Check

Before handing off to validate, check whether `SystemName-ORIGINAL.md` exists:

- If it exists: verify the diagram still truthfully represents the as-built workflow; update it if implementation diverged from the design
- If it does not exist: produce it now, showing the complete end-to-end workflow as implemented
- If the diagram cannot truthfully represent the workflow, flag the discrepancy as an unresolved risk

## Evidence

Record:

- guard run count and final result
- files changed
- commands run
- tests/checks run
- failures found
- unresolved risks
- diagram status: updated / created / flagged

After implementation, hand off to `vibe-workflow:validate`.
