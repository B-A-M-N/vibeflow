---
name: vibe-workflow:design
description: Map signed VibeFlow intent to real Mistral Vibe runtime topology with feasibility checks, plain-English components, diagrams, blunt design critique, and user approval gates.
---

Design the workflow described by `VISION.md`, `PLAN.md`, and `WORKFLOW_CONTRACT.json`.

This phase exists because the user may know what they want conceptually but not what Mistral Vibe can actually support or how the pieces should fit together.

## Inputs

Read:

- `VISION.md`
- `PLAN.md`
- `WORKFLOW_CONTRACT.json`
- `references/diagrams/diagram-index.json`

Use references with progressive disclosure:

1. Read `references/diagrams/diagram-index.json` first.
2. Use the index to identify only the feasibility/runtime surfaces relevant to the proposed design.
3. Read the matching feasibility and diagram files only when needed to sanity-check a concrete design claim.
4. Do not load every reference file by default.
5. Do not tell the user to consult the references unless they ask; use them internally to ground the design.

Available feasibility substrate:

- Extension Point Taxonomy / Tiers A-E
- Key Interfaces & Contracts
- Workflow Pattern Library
- Event System Reference
- Configuration Keys for Workflow Control
- Tier Composition Patterns
- Diagnostic & Observability

If required context is missing, stop and tell the user to run `/vibe-workflow-init`.

## Design Loop

Start with:

```md
Based on what you told me, this is what I recommend.
```

Then show:

- each required component in plain English
- the runtime surface it maps to
- why that surface is appropriate
- the feasibility tier
- constraints and tradeoffs
- what can be done with config/skills/tools/middleware/source changes
- what cannot be done as stated

Reference citations are optional. Include them only when a claim is risky, surprising, disputed, or needed to explain a feasibility boundary.

Use simple text diagrams when useful. Keep diagrams explanatory, not decorative.

## Blunt Feasibility Review

Give grounded opinions. Do not flatter bad architecture.

Call out:

- over-engineering
- underspecified behavior
- impossible runtime assumptions
- places where the user's idea is feasible only if implemented differently
- cheaper/smaller designs that satisfy the same goal
- cases where source modification is the honest answer

If the user proposes an alternative, reflect it honestly:

1. Is it feasible?
2. What tier does it require?
3. What would have to change?
4. Is there a simpler equivalent implementation?
5. Should the design be amended?

## Approval Gate

Do not advance until the user approves a design.

If approved, write:

- `DESIGN.md` - human-readable runtime topology and component explanation
- `ARCHITECTURE.md` - diagrams, file/component map, and data/control flow
- update `WORKFLOW_CONTRACT.json` with design status and selected feasibility tier

Then tell the user the next step is `/vibe-workflow-plan`.
