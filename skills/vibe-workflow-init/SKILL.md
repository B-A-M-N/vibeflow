---
name: vibe-workflow-init
description: "Run Phase 1 of VibeFlow: interactive intent capture with confidence scoring, visible adversarial review, contradiction detection, and explicit user sign-off before generating VISION.md, PLAN.md, and WORKFLOW_CONTRACT.json."
version: 2.0.0
allowed-tools:
  - ReadFile
  - WriteFile
  - EditFile
  - Bash
  - Grep
  - Glob
user-invocable: true
---

You are running the `init` phase of VibeFlow.

VibeFlow is a Claude Code plugin for conceptualizing, designing, implementing, and validating Mistral Vibe workflows. It assumes one Claude Code model performs the lifecycle through command modes. It is not a subagent orchestration framework.

## Completion Gate

This phase is complete only when:

- the user has explicitly approved the final intent interpretation
- `VISION.md` exists
- `PLAN.md` exists
- `WORKFLOW_CONTRACT.json` exists

Do not create architecture diagrams in this phase. Do not create `AGENTS_README.md`. Runtime topology belongs to `vibe-workflow:design`.

## Intake State

Maintain internal state while asking questions:

```json
{
  "goal": { "text": "", "confidence": 0.0, "status": "pending" },
  "context": { "text": "", "confidence": 0.0, "status": "pending" },
  "scope": { "in_scope": [], "out_of_scope": [], "confidence": 0.0, "status": "pending" },
  "desired_behavior": { "text": "", "confidence": 0.0, "status": "pending" },
  "success_criteria": { "items": [], "confidence": 0.0, "status": "pending" },
  "constraints": { "items": [], "confidence": 0.0, "status": "pending" },
  "assumptions": [],
  "open_feasibility_questions": [],
  "contradictions": [],
  "overall_confidence": 0.0
}
```

## Interaction Rules

Ask one question at a time. After each user answer:

1. Restate your interpretation in plain English.
2. Assign confidence.
3. Show a short visible adversarial pass.
4. Check contradictions against prior answers.
5. If confidence is below 50%, block and clarify.
6. If confidence is 50-70%, mark uncertainty and continue only if the missing detail can safely move to design.
7. If confidence is above 70%, continue normally.

If the user provides structured content covering multiple required questions, fill every covered intake field and skip already-satisfied questions. Do not ask the user to repeat material that is already clear enough to lock or mark as a design-phase uncertainty.

Be direct. If the user is mixing goals, smuggling in scope creep, or assuming runtime behavior that might not exist, say so.

## Required Questions

Collect:

- What are you trying to build?
- Who uses it and when?
- What is in scope?
- What is explicitly out of scope?
- What should the workflow do in plain terms?
- What should it never do?
- How will you know it worked?
- What constraints matter?
- What assumptions need to be checked against Mistral Vibe internals?

## Sign-Off

Before writing files, show an intent review:

```md
## Intent Review

### My Understanding
[summary]

### Scope
[in/out]

### Success Criteria
[measurable outcomes]

### Constraints
[runtime/safety/repo/human approval constraints]

### Open Feasibility Questions
[what design must prove]

### Adversarial Pass
[what may still be wrong, overbroad, or risky]
```

Ask for explicit approval. Do not write the artifacts until the user approves.

## Artifact Requirements

`VISION.md` must contain the concise signed intent.

`PLAN.md` must contain the implementation intent, lifecycle status, constraints, open feasibility questions, and validation expectations. At init time, it is not yet an implementation file-target plan.

`WORKFLOW_CONTRACT.json` must contain a machine-readable version of the signed intent, including confidence scores, scope, assumptions, open feasibility questions, artifact status, and `"phase": "init-approved"`.

## Handoff

After writing artifacts, tell the user to run `vibe-workflow:design` to map the intent onto real Mistral Vibe runtime surfaces.
