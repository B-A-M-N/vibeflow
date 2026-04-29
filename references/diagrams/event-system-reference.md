# Event System Reference Diagram

Maps event producers, event types, and consumers.

Source references:

- `references/feasibility/event-system-reference.md`
- `references/diagrams/event-system.md`

```mermaid
flowchart LR
  Backend["LLM Backend\nMistralBackend / GenericBackend"] --> AgentLoop["AgentLoop\nEvent producer"]
  AgentLoop --> Events["BaseEvent hierarchy"]

  Events --> Assistant["AssistantEvent"]
  Events --> Reasoning["ReasoningEvent"]
  Events --> ToolCall["ToolCallEvent"]
  Events --> ToolResult["ToolResultEvent"]
  Events --> ToolStream["ToolStreamEvent"]
  Events --> Compact["CompactStartEvent / CompactEndEvent"]
  Events --> Waiting["WaitingForInputEvent"]

  Events --> TUI["Textual UI\nEventHandler"]
  Events --> ACP["ACP / JSON-RPC consumers"]
  Events --> Logs["Session / trace / validation evidence"]
```

## Boundary Rule

New event producers are not enough. A design that changes event shape or event classes must account for every relevant consumer.
