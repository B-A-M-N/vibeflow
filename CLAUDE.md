# VibeFlow Contextual Activation

This file activates VibeFlow knowledge when the user's task involves Mistral Vibe workflows.

## When This Knowledge Is Active

This plugin is loaded. Use its knowledge when the user's task involves:

- Designing or implementing Mistral Vibe workflows (multi-phase, quality gates, custom tools, MCP, middleware, hooks, agent profiles)
- Working with `WORKFLOW_CONTRACT.json`, `VISION.md`, `PLAN.md`, `DESIGN.md`, `ARCHITECTURE.md`, or `REALIZATION_CONTRACT.json`
- Referencing VibeFlow lifecycle phases: init, design, plan, apply, validate, update, inspect, realize
- Building custom `BaseTool` subclasses, middleware, hooks, or agent profiles for Mistral Vibe
- Configuring MCP servers or Mistral Connectors for Vibe workflows
- Debugging Vibe workflow convergence, compaction survival, or phase-gate enforcement

## When This Knowledge Should NOT Activate

Do not use VibeFlow references for:

- General Claude Code usage or configuration
- Non-Vibe workflow tasks (simple prompts, single-turn tool calls, basic file editing)
- Other agent frameworks (LangChain, CrewAI, AutoGen, etc.) unless the user explicitly asks to compare with Vibe
- Mistral AI API usage (chat completions, embeddings) — VibeFlow is about the Vibe agent runtime, not the API

## Activation Strategy

When context matches the "active" set above:

1. **Do not** dump all references into context. Use progressive disclosure.
2. Start with `references/feasibility/runtime-pattern-catalog.md` for runtime surface questions.
3. Use `references/examples/archetypes/README.md` for workflow shape questions.
4. Use `references/strategy-selection.md` for design candidate questions.
5. Load specific reference files only when needed to verify a concrete claim.

## Command Routing

If the user's request maps to a VibeFlow lifecycle phase, offer the corresponding command:

| User intent | Command |
|-------------|---------|
| "I want to build a Vibe workflow" | `/vibe-workflow-init` |
| "Help me design the runtime topology" | `/vibe-workflow-design` |
| "Create an implementation plan" | `/vibe-workflow-plan` |
| "Build the workflow from the plan" | `/vibe-workflow-apply` |
| "Verify the workflow works" | `/vibe-workflow-validate` |
| "Change the existing workflow" | `/vibe-workflow-update` |
| "Look at what's already here" | `/vibe-workflow-inspect` |
| "Make this concept real" | `/vibe-workflow-realize` |

Do not force the command if the user just wants information. Offer it when they are ready to act.
