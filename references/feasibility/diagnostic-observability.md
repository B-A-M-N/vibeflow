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
