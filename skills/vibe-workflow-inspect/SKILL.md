---
name: vibe-workflow-inspect
description: Use when the user wants to inspect a repo or workflow, map existing skills/tools/middleware/config/source surfaces, understand lifecycle artifacts, or audit current setup.
version: 2.0.0
allowed-tools:
  - ReadFile
  - WriteFile
  - EditFile
  - Bash
  - Grep
  - Glob
user-invocable: true
---

Inspect current repo/workflow and map skills, middleware, tools, config, source surfaces, artifacts, and validation state.

1. Read `references/vibe-concepts.md` to understand Vibe workflow model.

2. Locate workflow spec:
   - Check for `workflow.yaml` or `workflow.yml` in `.vibe-workflow/` or current directory
   - If found, read and parse the manifest

3. Map existing components in the repo:
   - **Skills**: Scan `skills/` directories for `SKILL.md` files
   - **Middleware**: Look for middleware configs or hook files
   - **Tools**: Check what tools are referenced in workflow artifacts/skills
   - **Config**: Check Vibe config keys relevant to workflow control
   - **Source surfaces**: Identify source files that would need changes
   - **Artifacts**: Locate `VISION.md`, `PLAN.md`, `WORKFLOW_CONTRACT.json`, `DESIGN.md`, and `ARCHITECTURE.md`

4. Read key source files (if available):
   - AgentLoop implementation
   - Middleware base/interface
   - Skill manager / activation path
   - Tool execution path
   - Config/model definitions
   - Existing ACP-related files

5. After reading, summarize:
   - Where workflow control actually happens
   - Whether middleware behavior belongs at the `before_turn(context)` boundary
   - Where tools are invoked
   - Where state should be stored
   - What extension points are safe to use
   - What extension points require source patches

6. Output inspection report:
   ```
   ## VibeFlow Inspection Report

   ### Workflow Spec: [found/missing]
   - Location: [...]
   - Phases: [count]
   - Gates: [count]
   - Middleware: [list]

   ### Components Found
   - Skills: [list with triggers]
   - Middleware: [list]
   - Tools referenced: [list]
   - Config keys: [list]
   - Source surfaces: [list]

   ### Extension Points
   - Safe (plugin-level): [list]
   - Requires source patch: [list]

   ### State Storage
   - Current: [...]
   - Recommended: [...]

   ### Issues Found
   - [list any problems: missing files, impossible transitions, dead-ends]
   ```

7. Persist the inspection as `INSPECTION.md` and update `WORKFLOW_CONTRACT.json` with inspection status, discovered surfaces, discovered components, missing frontmatter fields, manifest/tooling mismatches, confidence score, and feasibility tier assessment. If `WORKFLOW_CONTRACT.json` does not exist, say so and include the data in `INSPECTION.md` only.

8. Include adversarial review:
   - skill discoverability: each `SKILL.md` has `name`, `description`, `allowed-tools`, and `user-invocable`
   - tool contract: tools referenced by phases are declared in `tooling.requiredTools`
   - middleware contract: middleware uses `before_turn()` only
   - lifecycle drift: approved design surfaces in `WORKFLOW_CONTRACT.json` still match discovered implementation surfaces

9. Ask user if they want to generate a workflow plan based on this inspection.
