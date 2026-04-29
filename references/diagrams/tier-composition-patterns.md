# Tier Composition Patterns Diagram

Shows how multiple runtime surfaces combine into one design classification.

Source reference: `references/feasibility/tier-composition-patterns.md`

```mermaid
flowchart TB
  A["Tier A\nSkill/config"] --> AB["A + B\nSkill uses custom tool"]
  B["Tier B\nTool"] --> AB

  A --> AC["A + C\nSkill with middleware guard"]
  C["Tier C\nMiddleware"] --> AC

  B --> BC["B + C\nTool with turn-level policy"]
  C --> BC

  C --> CD["C + D\nMiddleware needs new runtime hook"]
  D["Tier D\nSource modification"] --> CD

  D --> DE["D + Event Consumer Changes\nproducer + TUI/ACP consumers"]
  Events["Event consumers"] --> DE

  AB --> Highest["Classify whole design by highest required tier"]
  AC --> Highest
  BC --> Highest
  CD --> Highest
  DE --> Highest
```

## Design Rule

Explain each component separately, then classify the whole design by the highest required tier.
