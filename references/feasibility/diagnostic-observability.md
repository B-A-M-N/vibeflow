# Diagnostic & Observability

Use this when defining proof points for plan/apply/validate.

## Runtime Surfaces

- `AgentStats`: token, cost, step, tool success/failure, and timing metrics
- `SessionLogger`: session persistence and replay/audit trail
- `SessionLoader`: loading prior session data
- OpenTelemetry: traces/spans where instrumented
- Evidence reports: VibeFlow-generated validation summaries

## Design Implications

- If the workflow must prove behavior, name the metric/log/trace/event that proves it.
- If behavior must survive across sessions, proof must include session write and load.
- If a workflow depends on cost/latency/step bounds, proof should include `AgentStats` or equivalent logs.

## Validation Evidence

Record:

- commands run
- files changed
- tests/checks run
- session/log paths
- stats or trace identifiers when available
- failures with exact cause

## Failure Modes

- "Works" with no evidence.
- Logs exist but do not prove the claimed behavior.
- Session data is written but never loaded.
- Custom events are emitted but no consumer handles them.
- Validation depends on model self-report instead of deterministic checks.
- **`RateLimitError` kills the turn**: no turn-level retry loop exists. A rate-limited API call ends the turn and propagates an error to the UI. Free-tier models will kill mid-phase. Not recoverable within the session.
- **`MissingPromptFileError` on phase transition**: if a phase profile's `system_prompt_id` points to a missing `~/.vibe/prompts/<id>.md`, the agent crashes at config load. Hard blocker — not a warning, not a fallback.
- **Compaction costs 2 API calls, not 1**: `compact()` summarizes history (1 call) then calls `backend.count_tokens()` (1 more call). For GenericBackend/OpenRouter, `count_tokens` is a full LLM call with `max_tokens=16`. Budget-conscious workflows must account for this.
