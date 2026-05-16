# Grounded Strategy Selection

VibeFlow should not accept the first feasible architecture as the best architecture. During design, it must briefly search the design space, reject ungrounded candidates, and choose the candidate that best serves the signed intent.

This is a bounded design-search loop, not brainstorming. A candidate is valid only when it connects:

1. requirement
2. runtime surface
3. concrete mechanism
4. implementation or validation proof
5. known failure mode

If that chain is missing, the candidate is not creative. It is ungrounded.

## Candidate Archetypes

Generate 3-5 candidates when the design space is non-trivial:

- `minimal-native` — prefer built-in tools, skills, profile behavior, and existing workflow surfaces.
- `high-control` — add custom tools, profile switching, state, or hooks where enforcement matters.
- `high-throughput` — optimize for automation, programmatic output, subagent analysis, and reduced user blocking.
- `low-maintenance` — minimize source changes, custom runtime code, and long-term update burden.
- `unusual-grounded` — try a less obvious combination, but only if every capability edge has proof.

Do not force all archetypes if the workflow is simple. A narrow design may produce fewer candidates, but the linter will warn so the designer has to be conscious about it.

## Candidate Generation Process

### Step 1: Decompose the Intent

Before generating candidates, decompose the signed intent into concrete dimensions:

| Dimension | Question |
|-----------|----------|
| **Action type** | Is this read-only analysis, transformative write, or mixed? |
| **Human involvement** | Does the user need to approve between phases, or is full automation desired? |
| **Phase topology** | Is the workflow linear, branching, convergent, or fan-out/fan-in? |
| **Enforcement level** | Must phase transitions be enforced by tool schema, or is prompt guidance sufficient? |
| **State durability** | Does state need to survive compaction? Across sessions? |
| **Failure handling** | Should failures retry, escalate to user, or halt? |
| **Evidence needs** | What proof must exist that each phase completed correctly? |

Map each dimension to a workflow archetype from `references/examples/archetypes/README.md`. The archetype constrains which candidates are worth generating.

### Step 2: Generate Candidates Along the Enforcement Spectrum

For most non-trivial workflows, generate at least these three candidates spanning the enforcement spectrum:

**Candidate A — Prompt-Guided (Lowest Enforcement)**
- All phase logic in system prompt / skill instructions
- Single agent profile, no profile switching
- `todo` for progress tracking
- User gates via `ask_user_question`
- No custom tools, no middleware, no hooks
- *When to generate*: Always. This is the baseline. If it satisfies all requirements, it wins on simplicity.
- *When to reject*: When phase skipping would cause real damage, when tool misuse would corrupt state, or when audit evidence must be machine-checkable.

**Candidate B — Profile-Enforced (Medium Enforcement)**
- Agent profiles with `enabled_tools`/`disabled_tools` per phase
- Custom tools for state transitions (e.g., `advance_phase` with `switch_agent_callback`)
- Hooks for automated quality gates (lint, typecheck, test)
- State persisted to disk for compaction survival
- *When to generate*: When the workflow has 3+ phases with distinct tool requirements, or when skipping a phase would be costly.
- *When to reject*: When the workflow is linear with no branching and prompt guidance suffices.

**Candidate C — Fully Instrumented (Highest Enforcement)**
- Everything in B, plus:
- Custom middleware for cross-cutting concerns (logging, rate limiting, invariant checks)
- Subagent delegation for parallel analysis
- MCP servers for external tool integration
- Programmatic output mode for CI/CD consumption
- *When to generate*: When the workflow is a production pipeline, requires audit trails, or must integrate with external systems.
- *When to reject*: When the user is building a one-off or prototype. When Tier D source changes would be required without clear justification.

### Step 3: Add Specialized Candidates When Warranted

Add additional candidates only when the intent has specific characteristics:

- **Fan-out candidate**: When the task has independent sub-problems that can be analyzed in parallel. Uses `task` subagents with result aggregation.
- **Convergent-loop candidate**: When the workflow must iterate until a quality threshold is met. Needs a custom convergence tool with retry budget and exit criteria.
- **Approval-gate candidate**: When a human must review intermediate output before proceeding. Uses `ask_user_question` with structured response options.
- **Source-modification candidate**: Only when a requirement genuinely cannot be met by Tier A/B/C surfaces. Must document why each lower tier fails.

### Step 4: Validate Each Candidate Against the Grounding Chain

For every candidate, explicitly verify each link in the grounding chain:

```
Requirement: "Phase 3 must not start until Phase 2 passes lint"
  → Runtime surface: POST_AGENT_TURN hook
  → Mechanism: Hook runs `ruff check .`, exit 2 on failure
  → Proof: Hook exit-code semantics documented in runtime-pattern-catalog.md §Hooks
  → Failure mode: Hook times out → 3-retry ceiling → turn ends → user sees error
  → Verdict: GROUNDED
```

If any link is missing, the candidate is ungrounded. Either fix the gap or reject the candidate.

## Scoring

Each candidate scores 0-10 on:

- `effectiveness`: how directly it satisfies the signed success criteria.
- `groundedness`: how much the design is supported by verified runtime surfaces and source/reference evidence.
- `cost`: implementation effort, where 10 means cheap and 0 means expensive.
- `maintainability`: expected durability across Vibe updates and user workflow changes.
- `observability`: quality of evidence, diagnostics, and failure classification.
- `convergence`: likelihood of reaching a bounded success/failure verdict without user rescue.

High effectiveness with low groundedness is a warning sign. Tier D/source-change candidates must explain why lower-tier surfaces cannot satisfy the same requirement.

### Scoring Rubric

| Score | Effectiveness | Groundedness | Cost | Maintainability | Observability | Convergence |
|-------|--------------|--------------|------|-----------------|---------------|-------------|
| 9-10 | All critical requirements met | Every surface verified in source/docs | Config + skills only | No custom code; survives Vibe updates | Full evidence chain; machine-checkable | Bounded; no user rescue needed |
| 6-8 | Most requirements met | Surfaces verified but some assumptions | Custom tools or hooks | Minor custom code; update-tolerant | Partial evidence; some manual checks | Likely bounded; occasional user input |
| 3-5 | Core requirements met | Some surfaces unverified or assumed | Middleware or MCP | Moderate custom code; may break on updates | Limited evidence; mostly manual | Uncertain; may loop or stall |
| 0-2 | Requirements partially met | Heavy reliance on unverified assumptions | Tier D source changes | Heavy custom code; fragile | Little to no evidence | Unbounded; frequent user rescue |

## Selection Rule

Pick the candidate that dominates on the user's actual objective function, not the one with the most runtime surfaces.

Prefer the smallest sufficient runtime surface when scores are otherwise close. Prefer the higher-control design only when the task has real enforcement, audit, or convergence needs that native surfaces cannot satisfy.

The selected winner must become the source for `DESIGN.md`, `ARCHITECTURE.md`, and `WORKFLOW_CONTRACT.json` surface decisions. Rejected candidates should be summarized as alternatives with reasons, not implemented.

## Anti-Patterns in Strategy Selection

- **Generating only one candidate**: If you only produce one architecture, you are not searching — you are rationalizing.
- **Scoring after selection**: Score all candidates before picking. Do not pick then justify.
- **Ignoring the minimal-native baseline**: Always generate the prompt-guided candidate. If it wins, that is a valid outcome.
- **Inflating groundedness**: If you cannot point to a specific section in `runtime-pattern-catalog.md` or source code, the groundedness score drops.
- **Tier D by default**: Source modification is the last resort, not the power move.
