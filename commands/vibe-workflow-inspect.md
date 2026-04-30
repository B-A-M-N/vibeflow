---
name: vibe-workflow:inspect
description: Inspect a repo or workflow — map existing skills, tools, middleware, config, source surfaces, artifacts, and validation state.
---

Inspect current repo/workflow and map runtime surfaces, artifacts, and validation state.

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

7. Persist the report as `INSPECTION.md` and update `WORKFLOW_CONTRACT.json` with inspection status, discovered surfaces/components, manifest/tooling mismatches, confidence score, and feasibility tier assessment when the contract exists.

8. Include adversarial checks for skill discoverability frontmatter (`name`, `description`, `allowed-tools`, `user-invocable`), declared tool usage, middleware `before_turn()` compatibility, and lifecycle drift against approved runtime surfaces.

9. Ask user if they want to generate a workflow plan based on this inspection.
