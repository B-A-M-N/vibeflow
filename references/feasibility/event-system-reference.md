# Event System Reference

Use this when a design depends on streaming, observability, UI behavior, or validation proof.

## Core Rule

Events are runtime outputs that consumers must understand. Adding new event types is not just a producer change; every relevant consumer must be updated.

## Known Event Surfaces

- `vibe/core/types.py`: `BaseEvent` hierarchy, `LLMMessage`, `AgentStats`
- `vibe/core/agent_loop.py`: emits assistant, reasoning, tool call, tool result, and stats-related events
- `vibe/cli/textual_ui/handlers/event_handler.py`: TUI event consumption
- ACP/server paths: must understand any event surfaced to external clients

## Design Implications

- Existing event usage is usually Tier A-C depending on whether code changes are needed.
- New event classes are Tier D unless the extension surface is already exposed.
- Any design requiring custom UI/ACP behavior must name both producer and consumer changes.

## Proof Points

- Event emitted with expected fields.
- Event consumer handles it without crashing or ignoring critical state.
- Validation report includes trace/log evidence.
- Existing event paths still work.
