---
name: vibe-workflow:init
description: Start a VibeFlow workflow. Runs an interactive intent loop with confidence scoring, adversarial review, contradiction checks, and explicit user sign-off before writing VISION.md, PLAN.md, and WORKFLOW_CONTRACT.json.
---

Initialize a Mistral Vibe workflow intent contract.

This command is Phase 1 of the lifecycle. It does not design runtime architecture. It captures and locks what the user wants, why it matters, what is in scope, and what success means.

## Hard Rule

Do not complete this command until the user has explicitly approved the final interpretation and these three artifacts exist:

- `VISION.md`
- `PLAN.md`
- `WORKFLOW_CONTRACT.json`

Do not create `ARCHITECTURE_D.md` or architecture diagrams here. Architecture belongs to `/vibe-workflow-design`.

## Intake Loop

Ask one question at a time. After each answer:

1. Restate the interpretation in plain English.
2. Assign confidence:
   - `<50%` blocks progress.
   - `50-70%` may continue only with an explicit uncertainty marker.
   - `>70%` may continue normally.
3. Show a short adversarial pass:
   - what might be misunderstood
   - what might be missing
   - what might become infeasible later
4. Check contradictions against earlier answers.
5. Let the user correct or refine before proceeding.

## Required Inputs

Collect and lock:

- Goal: what the workflow should accomplish.
- User/context: who uses it and when.
- Scope: what is in scope and explicitly out of scope.
- Desired behavior: how the workflow should act at a high level.
- Non-goals: what the user does not want built.
- Success criteria: how the user will know it worked.
- Constraints: runtime, repo, safety, data, human approval, automation level.
- Assumptions: anything not yet proven against Mistral Vibe internals.

## Sign-Off Gate

Before writing artifacts, present:

```md
## Intent Review

### My Understanding
[plain-English summary]

### Scope
[in/out]

### Success Criteria
[measurable outcomes]

### Known Risks or Unknowns
[items design must validate]

### Adversarial Pass
[short blunt critique]

Approve this intent contract? If not, tell me what to change.
```

Only proceed after the user clearly approves.

## Artifacts

Write `VISION.md`:

- concise goal
- user/problem context
- desired outcome
- scope boundaries
- success definition

Write `PLAN.md`:

- signed implementation intent
- required capabilities
- known constraints
- lifecycle status
- open feasibility questions for design
- validation expectations

Write `WORKFLOW_CONTRACT.json`:

- machine-readable version of the signed intent
- confidence scores
- scope boundaries
- success criteria
- assumptions
- open feasibility questions
- artifact status

## Final Response

Summarize the three artifacts and tell the user the next step is `/vibe-workflow-design`, where the intent is mapped onto real Mistral Vibe runtime topology.
