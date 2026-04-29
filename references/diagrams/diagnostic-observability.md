# Diagnostic & Observability Diagram

Maps validation proof surfaces to evidence outputs.

Source reference: `references/feasibility/diagnostic-observability.md`

```mermaid
flowchart TB
  Runtime["Workflow Runtime"] --> Stats["AgentStats\ntokens, cost, steps,\ntool success/failure, timing"]
  Runtime --> SessionLogger["SessionLogger\nmessages.jsonl + meta.json"]
  Runtime --> OTel["OpenTelemetry\ntraces/spans where instrumented"]
  Runtime --> Events["BaseEvent stream"]
  Runtime --> Evidence["VibeFlow evidence report"]

  Stats --> Proof["Validation Proof"]
  SessionLogger --> Proof
  OTel --> Proof
  Events --> Proof
  Evidence --> Proof

  Proof --> Verdict["READY / NEEDS_REWORK / FAILED"]
```

## Validation Rule

Do not accept "it worked" without evidence. Name the stat, log, trace, event, file, or command output that proves the behavior.
