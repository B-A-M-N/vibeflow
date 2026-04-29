# Configuration Keys for Workflow Control

Use this when deciding whether a workflow can be achieved through configuration rather than code.

## Known Relevant Keys

- `api_key`
- `active_model`
- `auto_approve`
- `permission`
- `enabled_tools`
- `disabled_tools`
- `tool_paths`
- `session_prefix`
- `[[mcp_servers]]`

## Design Implications

- Config can enable/disable tools, register MCP servers, adjust permissions, and point at tool paths.
- Config cannot change AgentLoop semantics, invent new middleware timing, or add event consumers.
- If the desired behavior is "make an existing capability available," prefer config.
- If the desired behavior is "change runtime behavior," config is probably insufficient.

## Proof Points

- Config key exists in the real Mistral Vibe settings model.
- Value is loaded at runtime.
- Behavior changes without source patches.
- Validation records the effective config used.
