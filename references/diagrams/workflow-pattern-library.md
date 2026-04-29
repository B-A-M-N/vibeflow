# Workflow Pattern Library Diagram

Maps common patterns to runtime surfaces and tiers.

Source reference: `references/feasibility/workflow-pattern-library.md`

```mermaid
flowchart TB
  Pattern["Workflow Pattern"] --> SkillGuided["Skill-guided workflow"]
  Pattern --> ExternalTool["External service tool"]
  Pattern --> PhaseGuard["Phase / policy guard"]
  Pattern --> EventAware["Event-aware UX or telemetry"]
  Pattern --> SessionBacked["Session-backed continuity"]
  Pattern --> SourceRuntime["Source-level runtime change"]
  Pattern --> Impossible["Impossible assumption"]

  SkillGuided --> A["Tier A\nskills + config"]
  ExternalTool --> B["Tier B\ntool or MCP"]
  PhaseGuard --> C["Tier C\nmiddleware"]
  EventAware --> CD["Tier C or D\nevents + consumers"]
  SessionBacked --> ACD["Tier A/C/D\nsession logging or source"]
  SourceRuntime --> D["Tier D\nvibe/core source"]
  Impossible --> E["Tier E\nnot feasible as stated"]
```

## Design Rule

Use the pattern library to prevent over-engineering. A simple skill-guided workflow should not become middleware or source modification unless a real runtime boundary requires it.
