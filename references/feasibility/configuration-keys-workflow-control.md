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
- `thinking`
- `compaction_model`
- `[[mcp_servers]]`
- MCP server `prompt`
- MCP server `sampling_enabled`
- tool-specific permission/config overrides, including allowlist, denylist, and sensitive patterns

## Design Implications

- Config can enable/disable tools, register MCP servers, adjust permissions, set model/thinking behavior, set compaction model, add MCP usage hints, and point at tool paths.
- Config cannot change AgentLoop semantics, invent new middleware timing, or add event consumers.
- If the desired behavior is "make an existing capability available," prefer config.
- If the desired behavior is "restrict or permit an existing tool," prefer skill `allowed_tools`, enabled/disabled tools, or tool-specific permission config before source changes.
- If the workflow will be long-running, consider `compaction_model` and compaction threshold behavior.
- If the workflow phase is complex reasoning, consider higher `thinking`; if it is mechanical patching, lower/off thinking may reduce cost.
- If the desired behavior is "change runtime behavior," config is probably insufficient.

## Proof Points

- Config key exists in the real Mistral Vibe settings model.
- Value is loaded at runtime.
- Behavior changes without source patches.
- Validation records the effective config used.
