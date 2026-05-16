# PR Workflow Lite — Architecture

## Agent Profiles

### Profile: `wf-intake`

```toml
display_name = "WF-Lite: Intake"
name = "wf-intake"
description = "Initialize workflow — create branch, fetch issue context, clarify ambiguity."
active_model = "nemotron-free"
system_prompt_id = "wf-intake"
enabled_tools = ["bash", "init_state", "advance_phase", "ask_user_question", "webfetch"]
```

**Rationale:** Minimal tool set. The model can create branches, initialize state, fetch URLs, and ask clarifying questions. No read_file/grep — the model should not investigate during INTAKE.

### Profile: `wf-investigate`

```toml
display_name = "WF-Lite: Investigate"
name = "wf-investigate"
description = "Deep analysis — read code, query GitNexus, spawn explore subagents."
active_model = "openrouter/owl-alpha"
system_prompt_id = "wf-investigate"
enabled_tools = ["read_file", "grep", "bash", "task", "write_file", "advance_phase", "webfetch", "gitnexus_*"]
```

**Rationale:** Full read access + GitNexus MCP + task tool for subagents. No write_file/search_replace — investigation should not modify code. write_file is included for writing investigation artifacts to `~/.vibe/runs/`.

### Profile: `wf-implement`

```toml
display_name = "WF-Lite: Implement"
name = "wf-implement"
description = "Code editing — implement the change within scope contract."
active_model = "openrouter/owl-alpha"
system_prompt_id = "wf-implement"
enabled_tools = ["read_file", "grep", "bash", "write_file", "search_replace", "todo", "check_scope", "advance_phase", "gitnexus_*"]
```

**Rationale:** Full code editing capability. todo for tracking progress. check_scope for mid-phase verification. GitNexus for impact analysis before editing shared symbols.

### Profile: `wf-validate`

```toml
display_name = "WF-Lite: Validate"
name = "wf-validate"
description = "Run tests, lint, typecheck. Record results."
active_model = "openrouter/owl-alpha"
system_prompt_id = "wf-validate"
enabled_tools = ["read_file", "grep", "bash", "write_file", "todo", "check_scope", "advance_phase", "gitnexus_detect_changes"]
```

**Rationale:** Test execution + evidence recording. write_file for validation_ledger.md. No search_replace — validation should not modify code (only re-enter IMPLEMENT on failure).

### Profile: `wf-push`

```toml
display_name = "WF-Lite: Push"
name = "wf-push"
description = "Push branch and create PR. Requires human approval."
active_model = "nemotron-free"
system_prompt_id = "wf-push"
enabled_tools = ["bash", "advance_phase", "ask_user_question"]

[tools.bash]
permission = "always"
```

**Rationale:** Minimal tools. bash with permission=always for git push. ask_user_question for approval. No read_file/write_file — the model should only present the approval doc and push.

## Custom Tools

### `init_state`

**Purpose:** Initialize workflow state file and create working branch.

**Inputs:**
- `repo_path`: Absolute path to the repository
- `source_url`: GitHub issue/PR URL
- `branch_name`: Desired branch name

**Behavior:**
1. Validate repo_path is a git repo
2. Fetch source_url context (gh issue view or gh pr view)
3. Create and checkout branch
4. Write initial state JSON to `~/.vibe/runs/<repo-key>/state.json`
5. Return structured result with branch, repo, and initial phase

**Tier:** B (BaseTool subclass)

### `advance_phase`

**Purpose:** Gated phase transition — the only way to move between phases.

**Inputs:**
- `target_phase`: The phase to advance to (optional — defaults to next in sequence)

**Gates checked (in order):**
1. **State exists:** State file must exist for the repo
2. **GitNexus evidence:** Required for INVESTIGATE→IMPLEMENT (query/context/impact with valid_for_gate=true)
3. **Scope check:** All write_evidence paths must be within scope contract
4. **Dirty tree (read-only phases):** No unauthorized source file modifications before IMPLEMENT
5. **Tests passed (VALIDATE→PUSH):** command_evidence must show passing tests

**Behavior on success:**
1. Update state.json with new phase
2. Record phase_history entry
3. Serialize todo_state to state.json
4. Call `ctx.switch_agent_callback(new_profile_name)`
5. Return visible transition message

**Behavior on failure:**
1. Return structured error with specific gate failure
2. Do NOT advance phase
3. Model must fix the issue and retry

**Tier:** B (BaseTool subclass with InvokeContext.switch_agent_callback)

### `check_scope`

**Purpose:** Mid-phase scope verification (preview only — does not gate).

**Inputs:**
- `contract_path`: Path to scope contract (default: `~/.vibe/runs/<repo-key>/contract.md`)

**Behavior:**
1. Read write_evidence from state.json
2. Compare against contract scope
3. Return list of violations (if any)
4. Does NOT block — informational only

**Tier:** B (BaseTool subclass)

## Hooks

### Configuration (`hooks.toml`)

```toml
[hooks.lint]
command = "cd {repo_path} && uv run ruff check . | head -30"
timeout = 30
phases = ["implement", "validate"]
on_failure = "retry"  # exit 2 → inject stdout as user message

[hooks.typecheck]
command = "cd {repo_path} && uv run pyright | head -50"
timeout = 60
phases = ["implement", "validate"]
on_failure = "retry"
```

**Phase filtering:** Lint and typecheck only run in IMPLEMENT and VALIDATE. Running them in INTAKE or INVESTIGATE would produce false positives on unmodified code.

**Retry protocol:** Exit 2 + non-empty stdout → inject as user message → agent fixes → retry. Max 3 retries per hook per turn.

**Cost:** Hooks themselves are subprocesses (no API cost). Only retries cost extra LLM calls.

## GitNexus MCP Integration

### Config

```toml
[[mcp_servers]]
name = "gitnexus"
command = "gitnexus"
args = ["mcp"]
```

### Required Evidence

| Transition | Required Evidence |
|------------|-------------------|
| INVESTIGATE→IMPLEMENT | `gitnexus_query` + `gitnexus_context` or `gitnexus_impact` with `valid_for_gate=true` and `result_has_data=true` |

### Degraded Mode

If GitNexus MCP returns empty/failed results:
1. Record failed attempts in state.json
2. After ≥2 failed attempts, allow escape if investigation artifact documents:
   - Degraded mode marker ("degraded", "fallback", "mcp failed", etc.)
   - Analysis terms ("root cause", "architecture", "risk", "blast radius")

## Artifact Layout

```
~/.vibe/runs/<repo-key>/
  state.json              # Phase, branch, evidence, history, todo_state
  contract.md             # Scope contract (created in INVESTIGATE)
  investigation.md        # Investigation findings + GitNexus evidence
  validation_ledger.md    # Test/lint/typecheck results
  approval.md             # Approval doc with known limitations

~/.vibe/skills/wf-lite/
  SKILL.md                # Skill body (injected as system prompt)
  tools/
    advance_phase.py      # Phase gating + transition
    check_scope.py        # Scope verification
    init_state.py         # State initialization + branch creation

~/.vibe/agents/
  wf-intake.toml
  wf-investigate.toml
  wf-implement.toml
  wf-validate.toml
  wf-push.toml

~/.vibe/prompts/
  wf-intake.md
  wf-investigate.md
  wf-implement.md
  wf-validate.md
  wf-push.md
```

## Corrective Loops

```
VALIDATE → IMPLEMENT  (tests failed — keep branch, fix tests)
```

On VALIDATE failure, the model re-enters IMPLEMENT with the same branch. The state file tracks the retry count. After 3 failed VALIDATE attempts, the workflow stops and asks the user for guidance.

## Recovery Model

| Condition | Detection | Response |
|-----------|-----------|----------|
| Empty response | `content==""` + no tool_calls | Inject retry message, max 5 retries |
| Phase stall | Model outputs text without calling advance_phase | Inject "call advance_phase now", max 5 retries |
| Budget exhausted | recovery_count >= 5 | Loop exits, user sees last message |
