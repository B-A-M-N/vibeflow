# Configuration Keys For Workflow Control Diagram

Maps configuration keys to workflow-control capability.

Source reference: `references/feasibility/configuration-keys-workflow-control.md`

```mermaid
flowchart TB
  Config["VibeConfig"] --> Model["active_model\nmodels\nproviders"]
  Config --> Permission["auto_approve\npermission"]
  Config --> Tools["enabled_tools\ndisabled_tools\ntool_paths"]
  Config --> Session["session_prefix\nsession logging"]
  Config --> MCP["[[mcp_servers]]"]

  Model --> Capability["Select backend/model behavior\nwithin existing backend boundary"]
  Permission --> Capability
  Tools --> Capability
  Session --> Capability
  MCP --> Capability

  Capability --> Limit["Cannot change AgentLoop semantics,\nmiddleware timing, event consumers,\nor source-level behavior"]
```

## Design Rule

Prefer config for exposing or constraining existing behavior. Do not use config as a fake explanation for runtime changes it cannot perform.
