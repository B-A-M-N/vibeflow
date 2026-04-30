---
name: vibe-workflow-update
description: "Run VibeFlow workflow change control: clarify requested changes, scan current artifacts, compare generated workflow against the goal, propose approved edits, apply them, and update lifecycle records."
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

You are running the `update` phase of VibeFlow.

Use this when the user wants to modify an existing workflow, harden a generated workflow, resolve a mismatch between the goal and implementation, or review what was generated against what the workflow was supposed to accomplish.

The update phase is interactive change control. It must help the user articulate the problem before changing files, then preserve the design decision contract and lifecycle records after changes.

## Inputs

Read available artifacts before proposing edits:

- `VISION.md`
- `PLAN.md`
- `WORKFLOW_CONTRACT.json`
- `DESIGN.md`
- `ARCHITECTURE.md`
- `INSPECTION.md`
- `.vibe-workflow/workflow.yaml` or `.vibe-workflow/workflow.json`
- `.vibe-workflow/evidence/latest.json`
- latest `.vibe-workflow/reports/*.md`

If some artifacts are missing, continue with the best available evidence and say exactly what is missing.

## Change Intake

Start with narrative intake. The user may describe symptoms imprecisely, so help translate the concern into an actionable change request.

Capture:

- observed problem or desired adjustment
- where it appears: intent, design, plan, implementation, validation, generated workflow, runtime behavior, or documentation
- expected behavior after the update
- constraints and non-goals
- urgency and blast radius
- evidence the user has already seen
- suspected cause, if any

If the user already gave enough context, do not ask redundant questions. Move to scan.

## Scan

Scan the directory and artifacts before deciding whether the request is clear enough.

Look for:

- current lifecycle phase in `WORKFLOW_CONTRACT.json`
- signed intent and success criteria
- selected, rejected, and not-applicable `design.surfaceDecisions`
- `design.requirements` and their selected surfaces
- plan file targets and deviations
- generated workflow manifest sections
- tools/middleware/skills/config/source surfaces that were selected but not implemented
- implemented surfaces that were not selected
- validation failures, stale evidence, or drift reports
- canonical schema or frontmatter problems
- missed native runtime primitives such as `ask_user_question`, `exit_plan_mode`, `todo`, scratchpad, `task`, `webfetch`, `websearch`, AGENTS.md, `POST_AGENT_TURN` hooks, or programmatic output

Use existing scripts when applicable:

- `workflow-linter.py`
- `dry-run-simulator.py`
- `validation-runner.py`
- `design-contract-linter.py`
- `drift-detector.py`
- `state-invariant-checker.py`

## Ambiguity Gate

After scanning, decide whether the request has enough information to propose a high-quality solution.

If ambiguity is blocking, stop and ask targeted clarification before proposing edits. Explain:

- what is ambiguous
- why it affects the design or implementation
- what would go wrong if guessed
- 2-3 contextual examples of possible meanings

Ask one focused question at a time unless multiple ambiguities are tightly coupled. Continue the clarification loop until ambiguity is mitigated to a reasonable degree.

Examples of blocking ambiguity:

- The user says a workflow is "too complex" but not which behavior should be simplified.
- The user says validation is "wrong" but does not identify whether the generated workflow, validator, or original goal is wrong.
- The user asks to "add tools" but the scan shows the requirement may be satisfied with a skill or config change.
- The user asks to change middleware behavior that would actually require source modification.

## Diagnosis

Compare current artifacts against the user's stated update goal.

Classify the update type:

- intent correction: signed goal/scope/success criteria must change
- design correction: runtime surfaces or feasibility tier must change
- plan correction: file targets, validation gates, or contracts are incomplete
- implementation correction: planned files or surfaces were not implemented correctly
- validation correction: validation tooling or evidence is incomplete/wrong
- documentation correction: records are stale but behavior is correct

Do not assume every update requires redesign. Choose the smallest lifecycle layer that can honestly resolve the issue.

When hardening an existing workflow, explicitly check whether an invented mechanism should be replaced by a native one:

- generic approval prompt -> `ask_user_question` or `exit_plan_mode`
- file-based session checklist -> `todo`
- project-directory temporary output -> scratchpad
- delegated file writer -> parent writes, subagent returns text
- custom pre/tool hook -> impossible without source change; `POST_AGENT_TURN` only
- manual CI evidence -> programmatic `--output streaming` / `--output json`

## Proposed Update

Before editing, present a proposal and ask for explicit approval.

The proposal must include:

- problem summary
- evidence found during scan
- root cause or best-supported hypothesis
- proposed edits by file/artifact
- design decision contract changes, if any
- validation commands to run
- risks and rollback/rework notes
- what will intentionally not change

Use this format:

```md
## Proposed Workflow Update

### Problem
[what is wrong or changing]

### Evidence
[files/checks/artifacts that support the diagnosis]

### Proposed Edits
- [file]: [change and reason]

### Decision Contract Impact
- selected surfaces added/removed/unchanged
- rejected/not-applicable surfaces affected
- requirements and proof affected

### Validation
[commands/checks]

Approve these edits?
```

Do not edit implementation or lifecycle files until the user approves.

## Apply Approved Update

After approval:

- edit only files named in the approved update proposal unless a scoped deviation becomes necessary
- preserve rejected/not-applicable surfaces unless the approved change reclassifies them
- update selected surfaces with implementation and validation evidence when changed
- update `WORKFLOW_CONTRACT.json` with a change record
- update `PLAN.md` if file targets, validation gates, contracts, or deviations changed
- update `DESIGN.md` / `ARCHITECTURE.md` if runtime surfaces, feasibility tier, or component placement changed
- update `.vibe-workflow/workflow.yaml` or `.vibe-workflow/workflow.json` if executable behavior changed
- write or update `CHANGE_REQUEST.md` with the intake, ambiguity resolution, approved proposal, files changed, and validation result

Add a change record to `WORKFLOW_CONTRACT.json`:

```json
{
  "updates": [
    {
      "summary": "short description",
      "reason": "why the update was needed",
      "approved": true,
      "files_changed": [],
      "surface_decisions_changed": [],
      "validation": {
        "commands": [],
        "verdict": "READY | NEEDS_REWORK | FAILED"
      }
    }
  ]
}
```

## Validation

Run validation appropriate to the update.

Prefer:

```bash
python3 scripts/validation-runner.py .vibe-workflow/workflow.yaml
```

If full validation is not possible, run the most relevant deterministic subset and record the blocker. Never mark the update complete with unverified selected surfaces.

## Report

Final response must include:

- what changed
- which ambiguity was clarified, if any
- files updated
- validation result
- remaining risks or next action
