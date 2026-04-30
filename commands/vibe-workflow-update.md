---
name: vibe-workflow:update
description: Modify or harden an existing VibeFlow workflow through narrative intake, artifact scan, ambiguity clarification, approved proposal, edits, lifecycle record updates, and validation.
---

Update an existing VibeFlow workflow or review generated artifacts against the original goal and propose changes.

Use this command when:

- a generated workflow does not match the signed intent
- a workflow needs to change because the user's goal changed
- validation surfaced a problem that needs diagnosis and repair
- implementation is missing something selected by the design
- a previously established workflow needs hardening while VibeFlow itself is still evolving

## Inputs

Read available artifacts:

- `VISION.md`
- `PLAN.md`
- `WORKFLOW_CONTRACT.json`
- `DESIGN.md`
- `ARCHITECTURE.md`
- `INSPECTION.md`
- `.vibe-workflow/workflow.yaml` or `.vibe-workflow/workflow.json`
- `.vibe-workflow/evidence/latest.json`
- `.vibe-workflow/reports/`

Missing artifacts do not automatically block the update. Continue with best available evidence and name the missing proof.

## Flow

1. Intake the user's problem or requested adjustment in narrative form.
2. Scan the directory and lifecycle artifacts.
3. Compare current artifacts against the signed goal, success criteria, design decision contract, implementation evidence, and validation evidence.
4. Check whether the workflow missed native runtime primitives: `ask_user_question`, `exit_plan_mode`, `todo`, scratchpad, `task`, `webfetch`, `websearch`, AGENTS.md, `POST_AGENT_TURN` hooks, MCP `prompt`/`sampling_enabled`, thinking/compaction settings, or programmatic output.
5. Decide whether ambiguity blocks a high-quality proposal.
6. If blocked, ask focused clarification:
   - what is ambiguous
   - why it matters
   - what might go wrong if guessed
   - 2-3 contextual examples of possible meanings
7. After ambiguity is reasonably resolved, present proposed edits and ask for approval.
8. Only after approval, edit files and update lifecycle records.
9. Run relevant validation and report the result.

## Update Types

Classify the requested change:

- intent correction
- design correction
- plan correction
- implementation correction
- validation correction
- documentation/state correction

Use the smallest lifecycle layer that honestly resolves the issue. Do not redesign when a plan or implementation repair is enough. Do not implement new tools, middleware, agents/profiles, hooks, or source changes unless the approved design decision contract selects them or the approved update changes that contract.

## Approval Gate

Before editing, show:

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

Do not edit until the user approves.

## Records

After approval and edits:

- update `WORKFLOW_CONTRACT.json` with an `updates[]` change record
- update `PLAN.md` for file target, validation gate, contract, or deviation changes
- update `DESIGN.md` and `ARCHITECTURE.md` for runtime surface or component placement changes
- update `.vibe-workflow/workflow.yaml` or `.vibe-workflow/workflow.json` for executable behavior changes
- write or update `CHANGE_REQUEST.md` with intake, ambiguity resolution, approved proposal, files changed, validation result, and remaining risks

## Validation

Prefer:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validation-runner.py" .vibe-workflow/workflow.yaml
```

If full validation cannot run, run the relevant deterministic subset and record the blocker. Do not call the update complete if selected surfaces lack implementation or validation proof.
