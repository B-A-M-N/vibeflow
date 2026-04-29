# Streaming And Event System Diagram

Human-readable Mermaid reconstruction of the streaming/event system.

Source capture:

- `deepwiki-vibe-capture/out/7.6-streaming-and-event-system/context.txt`
- `deepwiki-vibe-capture/out/7.4-type-system-and-events/context.txt`

## Backend To UI Flow

```mermaid
sequenceDiagram
  participant Backend as FakeBackend/MistralBackend
  participant Loop as AgentLoop.act()
  participant Messages as MessageList / LLMMessage
  participant Events as BaseEvent stream
  participant Handler as EventHandler.handle_event()
  participant UI as TUI widgets

  Backend->>Loop: LLMChunk stream
  Loop->>Messages: append/update assistant/tool messages
  Loop->>Events: AssistantEvent / ReasoningEvent
  Loop->>Events: ToolCallEvent / ToolResultEvent / ToolStreamEvent
  Events->>Handler: structured event
  Handler->>UI: mount/update AssistantMessage
  Handler->>UI: mount/update ReasoningMessage
  Handler->>UI: mount/update ToolCallMessage
```

## Event Type Map

```mermaid
classDiagram
  class BaseEvent {
    event_type
    timestamp
  }

  class AssistantEvent {
    content
    is_streaming
  }

  class ReasoningEvent {
    content
  }

  class ToolCallEvent {
    tool_name
    args
    tool_call_id
  }

  class ToolResultEvent {
    result
    error
    duration
  }

  class ToolStreamEvent {
    message
    tool_call_id
  }

  class UserMessageEvent {
    content
    role
  }

  class CompactStartEvent {
    old_context_tokens
  }

  class CompactEndEvent {
    new_context_tokens
  }

  class WaitingForInputEvent

  BaseEvent <|-- AssistantEvent
  BaseEvent <|-- ReasoningEvent
  BaseEvent <|-- ToolCallEvent
  BaseEvent <|-- ToolResultEvent
  BaseEvent <|-- ToolStreamEvent
  BaseEvent <|-- UserMessageEvent
  BaseEvent <|-- CompactStartEvent
  BaseEvent <|-- CompactEndEvent
  BaseEvent <|-- WaitingForInputEvent
```

## Design Constraints

- Adding a new event type is not enough; relevant consumers must handle it.
- TUI and ACP/JSON-RPC paths are part of the real feasibility boundary.
- For validation, event traces can prove that tool calls, results, compaction, and waiting states happened.
