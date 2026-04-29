# Tier Composition Patterns

Many real workflows combine tiers. Classify the whole design by the highest required tier, but explain each component separately.

## A + B: Skill Uses Custom Tool

- Skill describes when/how to use a custom tool.
- Tool implements the external action.
- Overall tier: B.
- Common mistake: pretending tool behavior can control the agent loop.

## A + C: Skill With Middleware Guard

- Skill provides workflow instructions.
- Middleware injects phase state or blocks unsafe continuation before LLM turns.
- Overall tier: C.
- Common mistake: expecting middleware to run after tool execution.

## B + C: Tool With Turn-Level Policy

- Tool performs custom action.
- Middleware controls whether the next LLM turn should continue, stop, compact, or receive injected context.
- Overall tier: C.
- Common mistake: splitting one simple tool into unnecessary runtime machinery.

## C + D: Middleware Needs New Runtime Hook

- Middleware is not enough because the required interception point does not exist.
- Source patch adds or moves the hook.
- Overall tier: D.
- Common mistake: claiming normal middleware can intercept places it cannot.

## D + Event Consumer Changes

- Source emits new event or changes existing event shape.
- TUI/ACP/event handlers must be updated.
- Overall tier: D.
- Common mistake: updating producer only.

## Tier E Escape Hatch

If a user idea is impossible as stated but feasible with a different implementation, do not label the entire goal impossible. Label the stated mechanism Tier E and propose the feasible replacement mechanism with its tier.
