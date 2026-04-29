# Extension Point Taxonomy Diagram

Maps feasibility tiers A-E to runtime surfaces and implementation boundaries.

Source reference: `references/feasibility/extension-point-taxonomy.md`

```mermaid
flowchart LR
  Request["Workflow Request"] --> ACheck{"Can config/skills/MCP\nhandle it?"}
  ACheck -->|yes| A["Tier A\nNative config / skill-only"]
  ACheck -->|no| BCheck{"Needs new executable\naction only?"}
  BCheck -->|yes| B["Tier B\nTool-level extension"]
  BCheck -->|no| CCheck{"Needs before-turn\nmessage/policy control?"}
  CCheck -->|yes| C["Tier C\nMiddleware-level extension"]
  CCheck -->|no| DCheck{"Needs AgentLoop/tool/event/\nsession/source behavior changed?"}
  DCheck -->|yes| D["Tier D\nSource modification required"]
  DCheck -->|no| E["Tier E\nNot feasible as stated"]

  A --> ASurface["config.toml\nSKILL.md\nbuilt-in tools\nMCP config"]
  B --> BSurface["BaseTool\nToolManager\nMCP proxy tools"]
  C --> CSurface["MiddlewarePipeline\nMiddlewareAction\nbefore_turn()"]
  D --> DSurface["vibe/core/agent_loop.py\nvibe/core/types.py\nvibe/core/session/\nvibe/core/tools/"]
  E --> ESurface["contradicts runtime\nor lacks implementable signal"]
```

## Machine Meaning

- A design is classified by the highest tier required.
- Tier E can apply to a proposed mechanism even when the user goal has a feasible alternative.
