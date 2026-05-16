# Workflow Archetypes

**Do not copy PRForgeVibe.** It is one specific workflow for one specific problem (PR creation). Your workflow should be shaped by YOUR problem, not by PRForgeVibe's structure.

This guide helps you decompose your task and identify the right workflow archetype before you start designing.

## The Decomposition Process

Before choosing an archetype, answer these questions about your task:

### 1. What is the primary action type?

| Action Type | Description | Example |
|-------------|-------------|---------|
| **Create** | Produce a new artifact (code, doc, PR) | "Fix issue #123" |
| **Analyze** | Investigate and report without changing things | "Review our open PRs" |
| **Transform** | Modify existing artifacts in place | "Refactor the auth module" |
| **Orchestrate** | Coordinate multiple sub-tasks | "Deploy the full stack" |
| **Monitor** | Watch and react to changes | "Watch for test failures" |

### 2. What is the human involvement model?

| Model | Description | Implication |
|-------|-------------|-------------|
| **Autonomous** | No human in the loop | Needs strong automated gates |
| **Approval-gated** | Human approves at specific points | Use `ask_user_question` at gate points |
| **Interactive** | Human collaborates throughout | Design for back-and-forth |
| **Supervised** | Human reviews after completion | Focus on evidence collection |

### 3. What is the phase topology?

| Topology | When to Use | Example |
|----------|-------------|---------|
| **Linear pipeline** | Each phase depends on the previous one's output | INTAKE → INVESTIGATE → IMPLEMENT → VALIDATE |
| **Fan-out/fan-in** | Multiple independent sub-tasks that converge | Parallel investigation of subsystems |
| **Branching** | Conditional paths based on analysis | Triage → Execution OR Opportunity |
| **Convergent loop** | Retry until success criteria met | IMPLEMENT ↔ VALIDATE (loop until tests pass) |
| **DAG** | Complex dependency graph | Build → Test → Deploy with parallel test suites |

### 4. What enforcement level do you need?

| Level | Mechanism | Cost |
|-------|-----------|------|
| **Advisory** | Skills + prompts tell the model what to do | Zero — model can ignore |
| **Schema enforcement** | `enabled_tools` in agent profiles | Low — model physically cannot call tools not in schema |
| **Tool-level gating** | Custom tools validate before advancing | Medium — deterministic checks in tool code |
| **Loop-level guards** | Source modifications to agent_loop.py | High — requires Tier D changes |

**Start with the lowest level that suffices.** Most workflows need schema enforcement + tool-level gating (Tier B). Only reach for Tier D if you need guards that apply regardless of which tool the model calls.

## Archetype Catalog

### 1. Linear Pipeline

**Shape:** `A → B → C → D → E`
**When:** Clear sequential phases, each producing artifacts the next needs.
**Example:** PR creation (INTAKE → INVESTIGATE → IMPLEMENT → VALIDATE → PUSH)
**Enforcement:** Agent profiles with `enabled_tools` + `advance_phase` tool
**Tier:** A/B

```
INTAKE ──▶ INVESTIGATE ──▶ IMPLEMENT ──▶ VALIDATE ──▶ PUSH
```

### 2. Linear Pipeline with Approval Gate

**Shape:** `A → B → C → [HUMAN] → D`
**When:** Same as linear, but a human must approve before a destructive action.
**Example:** PR creation with approval before push
**Enforcement:** Same as linear, plus `ask_user_question` in the approval phase
**Tier:** A/B

```
INTAKE ──▶ INVESTIGATE ──▶ IMPLEMENT ──▶ APPROVAL ──▶ PUSH
                                  ▲              │
                                  └──────────────┘ (reject → rework)
```

### 3. Branching Pipeline

**Shape:** `INTAKE → ROUTE → [Lane A | Lane B | Lane C]`
**When:** The task type determines which path to take. Different lanes have different phase graphs.
**Example:** PRForgeVibe (Execution | Triage | Opportunity)
**Enforcement:** Routing tool at INTAKE + separate agent profiles per lane
**Tier:** A/B

```
                    ┌──▶ EXECUTION ──▶ INTAKE → ... → PUSH
INTAKE → ROUTE ────┤
                    ├──▶ TRIAGE ────▶ INTAKE → ... → REPORT
                    │
                    └──▶ OPPORTUNITY ▶ INTAKE → ... → REPORT
```

### 4. Fan-Out/Fan-In

**Shape:** `DISCOVER → [Subagent 1, Subagent 2, ...] → SYNTHESIZE`
**When:** Multiple independent sub-tasks can run in parallel.
**Example:** Investigate a bug across multiple subsystems simultaneously
**Enforcement:** `task` tool with subagent profiles + result aggregation
**Tier:** A/B

```
DISCOVER ──▶ ┌── Subagent A (subsystem 1) ──┐
             ├── Subagent B (subsystem 2) ──┤──▶ SYNTHESIZE
             └── Subagent C (subsystem 3) ──┘
```

### 5. Convergent Loop

**Shape:** `ATTEMPT → EVALUATE → [retry | done]`
**When:** The task requires iteration until success criteria are met.
**Example:** Fix tests until they all pass
**Enforcement:** `advance_phase` tool with retry counting + max retry limit
**Tier:** A/B

```
ATTEMPT ──▶ EVALUATE ──▶ FAIL ──▶ ATTEMPT (retry)
                          │
                          └──▶ PASS ──▶ DONE
```

### 6. Read-Only Analysis

**Shape:** `INTAKE → INVESTIGATE → REPORT`
**When:** The task is to analyze and report without modifying anything.
**Example:** PR triage, code review, security audit
**Enforcement:** Agent profiles with NO write tools + bash mutation guard (Tier D)
**Tier:** A/B (or D if you need loop-level mutation guards)

```
INTAKE ──▶ INVESTIGATE ──▶ REPORT ──▶ COMPLETE
```

### 7. Continuous Monitor

**Shape:** `WATCH → DETECT → REACT → WATCH`
**When:** The task runs continuously, reacting to external events.
**Example:** Monitor CI failures, watch for new issues
**Enforcement:** Hooks (POST_AGENT_TURN) + event-driven re-invocation
**Tier:** A

```
     ┌─── WATCH ◄───┐
     │               │
     ▼               │
   DETECT ──▶ REACT ─┘
```

## Decision Flowchart

```
Start
  │
  ├─ Does the task modify files?
  │   ├─ NO  → Read-Only Analysis or Continuous Monitor
  │   └─ YES ↓
  │
  ├─ Are there multiple independent sub-tasks?
  │   ├─ YES → Fan-Out/Fan-In
  │   └─ NO  ↓
  │
  ├─ Does the task type determine different paths?
  │   ├─ YES → Branching Pipeline
  │   └─ NO  ↓
  │
  ├─ Does the task need iteration until success?
  │   ├─ YES → Convergent Loop (possibly within a Linear Pipeline)
  │   └─ NO  ↓
  │
  ├─ Does a human need to approve before a destructive action?
  │   ├─ YES → Linear Pipeline with Approval Gate
  │   └─ NO  → Linear Pipeline
  │
  └─ What's the minimum enforcement level?
      ├─ Advisory only → Skills + prompts (Tier A)
      ├─ Schema enforcement → Agent profiles (Tier A)
      ├─ Tool-level gating → Custom tools (Tier B)
      └─ Loop-level guards → Source modifications (Tier D)
```

## Anti-Patterns

### ❌ Over-engineering
Don't build a branching pipeline with 3 lanes when a single linear pipeline suffices. Start simple and add complexity only when the task demands it.

### ❌ Copying PRForgeVibe's structure
PRForgeVibe has 9 phases, 3 lanes, custom middleware, and source modifications because it solves a complex problem (full PR lifecycle with triage). Your "fix a typo" workflow doesn't need that.

### ❌ Using middleware for phase sequencing
Middleware is a loop guard, not a phase orchestrator. If you find yourself wanting middleware to "move to the next phase," use the `task` tool or a custom `advance_phase` tool instead.

### ❌ Tier D when Tier B suffices
Source modifications to `vibe/core/` are hard to maintain across upstream updates. If agent profiles + custom tools can enforce your gates, don't modify the core loop.

### ❌ Ignoring compaction
If your workflow runs long enough to trigger compaction (switching from a large-context model to a small-context one), state in memory is lost. Persist everything important to disk.

## Examples in This Directory

| Example | Archetype | Phases | Tier |
|---------|-----------|--------|------|
| `pr-workflow-lite/` | Linear Pipeline with Approval Gate | 5 | B |

For a full-scale reference implementation, see [PRForgeVibe](https://github.com/example/prforge-vibe) — a Branching Pipeline with 3 lanes, 9 execution phases, custom middleware, and source modifications (Tier D). But remember: PRForgeVibe is the exception, not the rule.
