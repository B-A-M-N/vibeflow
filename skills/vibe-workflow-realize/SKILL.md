---
name: vibe-workflow-realize
description: Realize a conceptual workflow, partial implementation, skillset, or design document into a working, runtime-grounded Mistral Vibe implementation. Interactive: scans repo, presents candidates, confirms scope and intent, reflects on feasibility, proposes a fix plan, gets approval, then applies and validates.
version: 1.0.0
allowed-tools:
  - ReadFile
  - WriteFile
  - EditFile
  - Bash
  - Grep
  - Glob
user-invocable: true
---

You are running the `realize` phase of VibeFlow.

Your job is to take existing conceptual or partial work and turn it into a working, runtime-grounded implementation. You do not generate a new workflow from scratch. You start from what is already here.

This phase is interactive. Do not skip ahead to file edits until every confirmation gate below has passed.

---

## Step 1 — Scan

Silently scan the repo before saying anything. Look for:

- Skill files (`SKILL.md`, `skills/*/`)
- Command definitions (`commands/*.md`)
- Hook files (`hooks.toml`, `*.sh`)
- Tool class files (subclasses of `BaseTool`)
- Config files (`.vibe/*.toml`, `vibe.toml`, `config.toml`)
- Design documents (`VISION.md`, `PLAN.md`, `DESIGN.md`, `README.md`, `*.md` with workflow intent)
- Lifecycle artifacts (`WORKFLOW_CONTRACT.json`, `REALIZATION_CONTRACT.json`, `.vibe-workflow/workflow.yaml`)
- Any other files that describe intended behavior

Group findings into named candidates. A candidate is a coherent unit of intent — for example, a skill + its command + any referenced tools is one candidate; a half-built middleware implementation is another.

Then display:

```
## Scanning Repo

Found the following candidates:

1. [name] — [one-line description of what it seems to intend]
   Files: [list]
   Status: [partial / conceptual-only / mostly implemented / unclear]

2. [name] — ...

Which would you like to realize? (Enter a number, or describe something else.)
```

Wait for the user to respond. If they correct your grouping or rename a candidate, update your model and confirm the correction before continuing.

---

## Step 2 — Scope and Intent Confirmation

Once the user selects a candidate, present your interpretation of its intent and ask for confirmation:

```
## Scope Check

Selected: [candidate name]

**My interpretation:**
[2–4 sentences: what this appears to be trying to do, what runtime surfaces it seems to assume, what it looks partially or fully implemented]

**Files in scope:**
[list]

**Files I will not touch:**
[list — be explicit]

**Questions before I continue:**
[ask 1–3 targeted questions if intent is ambiguous: e.g. "Is this meant to run headless or interactively?", "Should this preserve the existing skill name or rename it?", "Is X part of the intent or a leftover artifact?"]

Does this match what you want? Confirm or correct.
```

Wait. Do not proceed until the user confirms the scope or gives corrections. If they correct, restate your updated interpretation and confirm again.

**Max-question limit:** Ask at most 3 targeted questions per confirmation round. If after 2 rounds (6+ exchanges) the scope is still unresolved, pause and summarize:

- what has been confirmed
- what is still unclear
- three concrete options: (a) proceed under the most plausible interpretation and flag the assumption in `REALIZATION_CONTRACT.json`, (b) provide a short clarification now, (c) abort and return when the candidate is better defined

Do not ask additional questions. Offer the summary and wait for the user to choose.

---

## Step 3 — Feasibility Reflection

Read `references/feasibility/runtime-pattern-catalog.md`, `references/feasibility/extension-point-taxonomy.md`, and relevant sections of `references/feasibility/key-interfaces-contracts.md` now.

For each component in the selected candidate, classify it:

| Bucket | Meaning |
|---|---|
| `implemented` | Already working as-is; no changes needed |
| `maps_to_existing_surface` | Conceptual but directly implementable via a known Vibe surface |
| `requires_custom_tool` | Needs a new `BaseTool` subclass |
| `requires_mcp_connector` | Needs an MCP server or Mistral Connector |
| `requires_source_modification` | Needs changes to Vibe source (Tier D) — only assign after ruling out Tier A/B/C |
| `not_implementable_as_stated` | Assumes a Vibe runtime behavior that does not exist |

For `not_implementable_as_stated`, identify the nearest alternative if one exists.

Then display the feasibility reflection:

```
## Feasibility Reflection

[For each component, show:]

**[component name]**
- Intent: [what it's trying to do]
- Current state: [conceptual / partial / broken / ok]
- Classification: [bucket]
- Grounded in: [which Vibe surface or reference supports this]
- Issue (if any): [what assumption is wrong or missing]
- Proposed fix: [what change makes it real]

---

**Cannot be realized as stated:**
[List any `not_implementable_as_stated` items with reason and nearest alternative]

**Requires source modification (Tier D):**
[List any, with justification for why lower tiers cannot satisfy the requirement]
```

---

## Step 4 — Proposed Fix Plan

Before presenting the plan, write a draft `REALIZATION_CONTRACT.json` with the proposed `required_runtime_surfaces` and run the pattern-fit linter:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pattern-fit-linter.py" REALIZATION_CONTRACT.json
```

If it flags violations, revise the proposed surfaces to address them before showing the plan to the user. Include any warnings in the plan with explanation.

Then present a concrete, numbered list of changes. Be specific: file path, what changes, and why.

```
## Proposed Fix Plan

1. [file path]
   Change: [what to add/edit/create]
   Reason: [why this makes the surface real]

2. [file path]
   Change: ...

...

**Not addressed (out of scope or not implementable):**
[List anything excluded and why]

**Contract bootstrap:**
[Explain that REALIZATION_CONTRACT.json will be created as the authoritative contract for this run, since no prior WORKFLOW_CONTRACT.json exists / is incomplete. This file will drive validation.]

Shall I proceed with this plan? (yes / adjust [item] / skip [item])
```

Wait. Do not begin editing until the user approves. Accept targeted adjustments ("skip item 3", "rename that file to X") and restate the updated plan before proceeding.

---

## Step 5 — Bootstrap the Contract

Before any edits, write `REALIZATION_CONTRACT.json`. This file is the authoritative contract for this realize run. It serves the role of `WORKFLOW_CONTRACT.json` for all subsequent validation.

```json
{
  "mode": "realize_existing_concept",
  "phase": "realize-approved",
  "source_artifacts": [],
  "preserved_intent": "",
  "scope_confirmed_by_user": true,
  "conceptual_claims": [
    {
      "claim": "",
      "bucket": "",
      "surface": "",
      "tier": "",
      "rationale": "",
      "not_implementable_reason": ""
    }
  ],
  "approved_fix_plan": [
    {
      "file": "",
      "change": "",
      "reason": ""
    }
  ],
  "excluded": [],
  "required_runtime_surfaces": [],
  "source_changes_required": [],
  "expected_evidence": [],
  "validation_plan": []
}
```

Also write `CONCEPT_MAP.json` mapping each conceptual component to its realization target (file, surface, tier).

If `WORKFLOW_CONTRACT.json` does not exist, also write a stub version pointing to `REALIZATION_CONTRACT.json` as the active contract source:

```json
{
  "phase": "realize-approved",
  "contract_source": "REALIZATION_CONTRACT.json",
  "note": "This workflow was realized from a partial implementation. See REALIZATION_CONTRACT.json for the authoritative contract."
}
```

If `WORKFLOW_CONTRACT.json` already exists, do not overwrite it. Add a `"realize_amendment"` key to it recording the realization run.

---

## Step 6 — Apply

Execute the approved fix plan exactly. Follow the contract.

Rules:
- Only modify files in the approved plan unless a blocker requires a scoped deviation.
- If a deviation is required, state it clearly and record it in `REALIZATION_CONTRACT.json` under `"deviations"` before editing.
- Do not implement a surface not in the approved plan.
- Generate or repair `.vibe-workflow/workflow.yaml` if the workflow is executable. Use `references/workflow-manifest-schema.json`.
- If workflow.yaml does not exist, create a minimal but schema-valid one from what the realized surfaces provide.

After each edit, state what changed and why.

---

## Step 7 — Validate

Run or prepare validation. Because this run started from a partial implementation, validation must use `REALIZATION_CONTRACT.json` as the contract source rather than expecting a fully populated `WORKFLOW_CONTRACT.json`.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validation-runner.py" .vibe-workflow/workflow.yaml
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design-contract-linter.py"
```

If a script fails because required artifacts are missing or the contract is incomplete, that is a legitimate finding — record it as a `validation_gap`, explain what is missing and why, and do not mark validation passed.

Classify any failures using the drift taxonomy:
- `missing_selected_surface` — a contracted surface has no implementation evidence
- `unauthorized_surface_added` — an uncontracted surface was implemented
- `wrong_runtime_surface` — wrong Vibe extension point used
- `impossible_runtime_assumption` — assumes a Vibe behavior that does not exist
- `stale_evidence` — evidence artifacts do not match current repo state
- `validation_gap` — a contracted validation target has no corresponding check

Report results honestly. If validation cannot run due to missing tooling, say so explicitly rather than claiming success.

---

## Evidence

At the end, write or append to `REALIZATION_REPORT.md`:

- Candidate selected and user-confirmed scope
- Feasibility classification for each component
- Fix plan (approved and executed)
- Deviations recorded (if any)
- Items excluded and reason
- Validation results
- Unresolved gaps

## Post-Realization Diagram

After validation, produce a mermaid diagram of the complete realized workflow as `SystemName-ORIGINAL.md`, showing end-to-end flow including all phases, gates, surfaces, and data/control paths. Double-check that the diagram truthfully matches the as-built implementation before writing it. If the diagram reveals gaps or contradictions, flag them as unresolved risks.

---

## Hard Rules

- Do not write a single implementation file before Step 5 (contract bootstrap) is complete.
- Do not skip Step 2 (scope confirmation) even if intent seems obvious.
- Do not mark a component `not_implementable_as_stated` without citing the specific Vibe reference that rules it out.
- Do not assign Tier D without ruling out Tier A/B/C first.
- Do not claim validation passed if the validator could not run or produced errors.
- `ask_user_question` is unavailable in non-interactive contexts in three distinct ways: (1) CLI `-p` adds it to `disabled_tools`; (2) ACP disables it via `disabled_tools`; (3) `run_programmatic()` direct API does not add it to `disabled_tools` but passes no callback — it fails at runtime when invoked. Flag all three if the realized workflow uses it.
- Subagents never run hooks — flag this if the concept assumes subagent hook behavior.
- `allowed_tools` in skills is advisory only — flag this if the concept treats it as an access boundary.
