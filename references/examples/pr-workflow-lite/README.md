# PR Workflow Lite — Example Workflow

**⚠️ Important:** This is ONE example of ONE archetype. Do not treat it as a template for all workflows. See [`../archetypes/`](../archetypes/) for the archetype catalog and decision framework first.

This is a complete example of a **Linear Pipeline with Approval Gate** archetype — the simplest workflow shape that demonstrates VibeFlow's core enforcement capabilities.

**What this example covers:**
- A 5-phase PR creation workflow (INTAKE → INVESTIGATE → IMPLEMENT → VALIDATE → PUSH)
- Agent profiles with per-phase tool enforcement
- Custom tools for phase advancement and scope checking
- POST_AGENT_TURN hooks for quality gates
- State persistence and compaction survival
- GitNexus MCP integration for code intelligence

**Archetype:** Linear Pipeline with Approval Gate
**Based on (loosely):** A simplified version of PRForgeVibe's execution lane. PRForgeVibe is a **Branching Pipeline** with 3 lanes and 9 phases — much more complex than this example.

## Artifact Map

| File | Purpose |
|------|---------|
| `VISION.md` | Goals, scope, success criteria |
| `WORKFLOW_CONTRACT.json` | Machine-readable contract (phase, intent, artifacts, design) |
| `DESIGN.md` | Runtime surface decisions, capability graph, feasibility tier |
| `ARCHITECTURE.md` | Agent profiles, tools, hooks, state schema, artifact layout |
| `profiles/` | Agent profile TOML files |
| `tools/` | Custom tool implementations |
| `hooks/` | Hook configuration |

## Tier Classification

| Component | Tier | Surface |
|-----------|------|---------|
| Agent profiles | A | Config |
| Skills (phase instructions) | A | Skill |
| Hooks (lint, typecheck) | A | Hook |
| `advance_phase` tool | B | Custom Tool |
| `check_scope` tool | B | Custom Tool |
| `init_state` tool | B | Custom Tool |
| GitNexus MCP integration | A | MCP |
| **Overall** | **B** | Custom tools needed |

## How to Read This Example

1. Start with `VISION.md` to understand the workflow's purpose
2. Read `WORKFLOW_CONTRACT.json` for the machine-readable contract
3. Read `DESIGN.md` for the runtime surface decisions
4. Read `ARCHITECTURE.md` for the full implementation blueprint
5. Review `profiles/` for agent profile configurations
6. Review `tools/` for custom tool implementations
