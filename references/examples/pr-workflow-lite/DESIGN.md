# PR Workflow Lite — Design

## Selected Archetype: Linear Pipeline with Approval Gate

This workflow follows a **linear pipeline** archetype — a single chain of phases with deterministic forward progress and one human approval gate. This is the simplest archetype that still demonstrates VibeFlow's core enforcement capabilities.

**Why linear pipeline:**
- The task has a clear start (issue/request) and end (PR created)
- Each phase produces artifacts the next phase depends on
- No branching, parallel lanes, or conditional routing needed
- Human approval is a single synchronization point before the final action

**Alternatives considered:**
- **Fan-out/fan-in** (parallel subagents converge): Overkill for single-repo changes. PRForgeVibe uses this for INVESTIGATE with explore subagents, but that's optional.
- **Branching pipeline** (conditional paths): Not needed — no triage/opportunity lanes. See PRForgeVibe for a branching example.
- **Convergent loop** (retry until success): VALIDATE can loop back to IMPLEMENT, but the overall structure is still linear.

## Capability Graph

```
                    ┌──────────────────────────────────────────────────────┐
                    │                    CONFIG LAYER                       │
                    │  config.toml — models, tools, hooks, MCP, compaction │
                    └──────────────────────┬───────────────────────────────┘
                                           │
                    ┌──────────────────────▼───────────────────────────────┐
                    │                 AGENT PROFILES                        │
                    │  5 profiles: intake, investigate, implement,         │
                    │  validate, push                                       │
                    │  Each: model + enabled_tools + system_prompt_id       │
                    └──────────────────────┬───────────────────────────────┘
                                           │
          ┌────────────────────────────────┼────────────────────────────────┐
          │                                │                                │
          ▼                                ▼                                ▼
┌──────────────────┐           ┌──────────────────┐           ┌──────────────────┐
│   CUSTOM TOOLS   │           │   GITNEXUS MCP   ││      HOOKS           │
│                  │           │                  │           │                  │
│ advance_phase    │           │ gitnexus_query   │           │ lint (impl+val)  │
│ check_scope      │           │ gitnexus_context │           │ typecheck (impl+  │
│ init_state       │           │ gitnexus_impact  │           │                  │
│                  │           │                  │           │ POST_AGENT_TURN   │
│ Gates: phase,    │           │ Required for     │           │ Exit 2 → retry   │
│ scope, git,      │           │ INVESTIGATE→     │           │ Phase-filtered   │
│ gitnexus         │           │ IMPLEMENT gate   │           │ Timeout: 30-60s  │
└──────────────────┘           └──────────────────┘           └──────────────────┘
```

## Phase Model

```
INTAKE ──▶ INVESTIGATE ──▶ IMPLEMENT ──▶ VALIDATE ──▶ PUSH ──▶ COMPLETE
              │                               │
              │         (corrective loop)      │
              └────────────────────────────────┘
```

| Phase | Model | Key Tools | Gates to Advance |
|-------|-------|-----------|-------------------|
| INTAKE | nemotron-free | bash, init_state, advance_phase, ask_user_question | Branch created, state initialized, clean tree |
| INVESTIGATE | owl-alpha | read_file, grep, bash, task, advance_phase, gitnexus_* | GitNexus evidence (query/context/impact), investigation artifact written |
| IMPLEMENT | owl-alpha | read_file, grep, bash, write_file, search_replace, todo, check_scope, advance_phase, gitnexus_* | Scope contract respected, code + tests written |
| VALIDATE | owl-alpha | read_file, grep, bash, write_file, todo, check_scope, advance_phase, gitnexus_detect_changes | Tests pass, lint pass, typecheck pass, detect_changes evidence |
| PUSH | nemotron-free | bash (permission=always), advance_phase | Human approval recorded, push succeeds |

## Model Tier Strategy

| Model | Context | Threshold | Used For |
|-------|---------|-----------|----------|
| owl-alpha | 1M | 800K | INVESTIGATE, IMPLEMENT, VALIDATE (heavy reasoning, code editing) |
| nemotron-free | ~262K | 204K | INTAKE, PUSH (structured work, deterministic ops) |

**Compaction behavior:** When switching from owl-alpha (800K threshold) to nemotron (204K threshold), AutoCompactMiddleware fires automatically because `old_context_tokens >= new_threshold`. The compaction summary is generated with the new system prompt, so the incoming phase context is preserved.

## State Schema

```json
{
  "phase": "IMPLEMENT",
  "branch": "user/feat-123",
  "repo": "owner/repo",
  "repo_path": "/path/to/repo",
  "source_url": "https://github.com/owner/repo/issues/123",
  "approval_granted": false,
  "gitnexus_used": true,
  "gitnexus_evidence": [
    {
      "phase": "investigate",
      "tool": "gitnexus_query",
      "valid_for_gate": true,
      "result_has_data": true,
      "ts": "2026-05-16T00:00:00Z"
    }
  ],
  "write_evidence": [
    {
      "phase": "implement",
      "tool": "write_file",
      "path": "/path/to/repo/src/feature.py",
      "bytes": 1234,
      "success": true,
      "ts": "2026-05-16T00:00:00Z"
    }
  ],
  "phase_history": [
    {"from": "INTAKE", "to": "INVESTIGATE", "summary": "Issue #123: add feature X"},
    {"from": "INVESTIGATE", "to": "IMPLEMENT", "summary": "Root cause: missing handler in src/feature.py"}
  ],
  "todo_state": [],
  "updated_at": "2026-05-16T00:00:00Z"
}
```

## Compaction Survival

| State | Survives Compaction? | How |
|-------|---------------------|-----|
| Agent profile | Yes | In-memory, survives natively |
| Message history | No | Reset to [system_prompt, summary] |
| State JSON | Yes | On disk, independent of messages |
| todo_state | Restored | Serialized to state.json before advance, restored by next phase |
| GitNexus evidence | Yes | In state.json on disk |
| Write evidence | Yes | In state.json on disk |
| Hook retry counts | No | Reset on compaction (acceptable — hooks restart) |

## Feasibility Tier: B

All requirements are met with Tier A (config/skills/hooks/MCP) plus Tier B (custom tools). No source modifications needed.

**Tier justification:**
- Phase enforcement via `enabled_tools` in agent profiles (Tier A)
- GitNexus integration via MCP config (Tier A)
- Quality gates via hooks config (Tier A)
- Phase gating logic via `advance_phase` custom tool (Tier B)
- Scope checking via `check_scope` custom tool (Tier B)
- State initialization via `init_state` custom tool (Tier B)
