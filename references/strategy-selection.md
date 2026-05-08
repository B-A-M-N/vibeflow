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

## Scoring

Each candidate scores 0-10 on:

- `effectiveness`: how directly it satisfies the signed success criteria.
- `groundedness`: how much the design is supported by verified runtime surfaces and source/reference evidence.
- `cost`: implementation effort, where 10 means cheap and 0 means expensive.
- `maintainability`: expected durability across Vibe updates and user workflow changes.
- `observability`: quality of evidence, diagnostics, and failure classification.
- `convergence`: likelihood of reaching a bounded success/failure verdict without user rescue.

High effectiveness with low groundedness is a warning sign. Tier D/source-change candidates must explain why lower-tier surfaces cannot satisfy the same requirement.

## Selection Rule

Pick the candidate that dominates on the user's actual objective function, not the one with the most runtime surfaces.

Prefer the smallest sufficient runtime surface when scores are otherwise close. Prefer the higher-control design only when the task has real enforcement, audit, or convergence needs that native surfaces cannot satisfy.

The selected winner must become the source for `DESIGN.md`, `ARCHITECTURE.md`, and `WORKFLOW_CONTRACT.json` surface decisions. Rejected candidates should be summarized as alternatives with reasons, not implemented.
