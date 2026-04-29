# AgentLoop Execution Diagram

Human-readable Mermaid reconstruction of the DeepWiki AgentLoop execution model.

Source capture:

- `deepwiki-vibe-capture/out/3.3-agent-loop-and-execution-model/context.txt`
- `deepwiki-vibe-capture/out/3.3-agent-loop-and-execution-model/diagram-00.png`

## Turn Cycle

```mermaid
flowchart LR
  Entry["AgentLoop.act(prompt)"] --> Messages["MessageList\nLLMMessage history"]
  Messages --> Middleware["MiddlewarePipeline.before_turn()"]
  Middleware -->|CONTINUE| Backend["BackendLike.stream_completion()"]
  Middleware -->|INJECT_MESSAGE| Messages
  Middleware -->|STOP or COMPACT| Stop["Stop / early return"]

  Backend --> Chunk["LLMChunk stream"]
  Chunk --> Events["BaseEvent stream\nAssistantEvent, ReasoningEvent, ToolCallEvent"]
  Chunk --> Resolver["APIToolFormatHandler.resolve_tool_calls()"]
  Resolver --> ToolCall["ResolvedToolCall"]
  ToolCall --> Execute["AgentLoop._execute_tool_call()"]
  Execute --> ToolManager["ToolManager"]
  Execute --> ToolResult["ToolResult"]
  ToolResult --> Messages
  ToolResult --> Events

  Messages --> Stats["AgentStats"]
  Events --> UI["TUI / ACP event consumers"]
```

## Orient / Plan / Execute

```mermaid
stateDiagram-v2
  [*] --> Orient
  Orient: get_universal_system_prompt()\nproject context, tools, environment
  Orient --> Plan: plan-mode middleware active
  Orient --> Execute: normal execution
  Plan: planning-first instructions\nPLAN_AGENT_EXIT / reminders
  Plan --> Execute: exit plan mode
  Execute: tool loop and backend turns
  Execute --> Execute: tool result added to messages
  Execute --> [*]: stop, compact, or final response
```

## Design Constraints

- Middleware runs before LLM turns, not during tool execution.
- Tool execution occurs when the AgentLoop resolves tool calls.
- Parallel tool execution is supported by the AgentLoop async/threading model, but designs must use that supported path.
- Persistence is not automatic memory; it must flow through session/state surfaces.
