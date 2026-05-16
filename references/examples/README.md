# VibeFlow Examples

**Start with the archetype guide.** Before looking at any example, read the archetype catalog to identify which workflow shape fits your task.

## Read This First

→ [`archetypes/README.md`](archetypes/) — Workflow archetype catalog and decision framework

The archetype guide helps you answer:
- What is the primary action type? (create, analyze, transform, orchestrate, monitor)
- What is the human involvement model? (autonomous, approval-gated, interactive, supervised)
- What is the phase topology? (linear, fan-out, branching, convergent loop, DAG)
- What enforcement level do you need? (advisory, schema, tool-level, loop-level)

## Example Workflows

| Example | Archetype | Phases | Tier | Complexity |
|---------|-----------|--------|------|------------|
| [PR Workflow Lite](pr-workflow-lite/) | Linear Pipeline with Approval Gate | 5 | B | Low |

## Key Principle

**Your workflow should be shaped by YOUR problem, not by PRForgeVibe's structure.** PRForgeVibe is a complex branching pipeline with 3 lanes, 9 execution phases, custom middleware, and source modifications because it solves a complex problem (full PR lifecycle with triage and opportunity discovery). Most workflows are simpler.

A workflow that fixes a typo doesn't need 9 phases. A read-only analysis doesn't need write-file enforcement. A continuous monitor doesn't need phase gating at all.

Start with the simplest archetype that fits, and add complexity only when the task demands it.
