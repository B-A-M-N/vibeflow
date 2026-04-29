# Feasibility Substrate Diagram

This is the top-level machine/human-readable map for the seven feasibility areas VibeFlow must use in every lifecycle phase.

## Seven-Part Feasibility Model

```mermaid
flowchart TB
  Intent["Signed Intent\nVISION.md + PLAN.md + WORKFLOW_CONTRACT.json"]

  Tiers["1. Extension Point Taxonomy\nTiers A-E"]
  Interfaces["2. Key Interfaces & Contracts\nBaseTool, InvokeContext,\nMiddlewareAction, ConversationContext"]
  Patterns["3. Workflow Pattern Library\npattern -> surface -> tier"]
  Events["4. Event System Reference\nBaseEvent hierarchy + consumers"]
  Config["5. Configuration Keys\nworkflow control knobs"]
  Composition["6. Tier Composition Patterns\ncombined surfaces and highest tier"]
  Diagnostics["7. Diagnostic & Observability\nAgentStats, OpenTelemetry, SessionLogger"]

  Design["Approved Runtime Design"]
  Plan["Implementation Plan"]
  Validate["Validation Proof"]

  Intent --> Tiers
  Intent --> Interfaces
  Intent --> Patterns
  Tiers --> Design
  Interfaces --> Design
  Patterns --> Design
  Events --> Design
  Config --> Design
  Composition --> Design
  Diagnostics --> Validate
  Design --> Plan
  Plan --> Validate
```

## Lifecycle Use

- `init` uses the model to detect impossible assumptions and open feasibility questions.
- `design` uses the model to map intent to real Mistral Vibe surfaces.
- `plan` uses the model to choose files, classes, contracts, and tests.
- `apply` uses the model to stay inside the approved surfaces.
- `validate` uses the model to define proof points, logs, traces, events, and tests.
