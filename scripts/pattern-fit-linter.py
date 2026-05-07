#!/usr/bin/env python3
"""Flag suspicious Mistral Vibe runtime surface patterns in workflow contracts."""

from __future__ import annotations

import json
import re
import sys
from typing import Any


def lint_pattern_fit(contract_path: str) -> dict[str, Any]:
    with open(contract_path) as f:
        contract = json.load(f)

    decisions = _design_values(contract, "surfaceDecisions")
    requirements = _design_values(contract, "requirements")
    findings: list[dict[str, Any]] = []

    selected = [_normalize_decision(d) for d in decisions if isinstance(d, dict) and d.get("status") == "selected"]
    selected_surfaces = {d["surface"] for d in selected if d["surface"]}

    for decision in selected:
        _check_decision(decision, findings)

    all_text = " ".join(d["text"] for d in selected)
    req_text = " ".join(_flatten_text(r) for r in requirements if isinstance(r, dict)).lower()

    if "skill" in selected_surfaces and "tool" in selected_surfaces:
        skill_text = " ".join(d["text"] for d in selected if d["surface"] == "skill")
        if "allowed_tools" not in skill_text and "allowed-tools" not in skill_text:
            findings.append(_finding(
                "skill-tool-allowed-tools-unchecked",
                "warning",
                "Skill and tool surfaces are both selected, but the design does not mention skill allowed_tools compatibility.",
            ))

    if "middleware" in selected_surfaces and "tool" in selected_surfaces:
        if "get_result_extra" in all_text and "inject_message" in all_text and "ordering" not in all_text and "conflict" not in all_text:
            findings.append(_finding(
                "duplicate-context-injection-risk",
                "warning",
                "Design selects both tool get_result_extra and middleware INJECT_MESSAGE without an ordering/conflict rationale.",
            ))

    if "agent-profile" in selected_surfaces and "tool" not in selected_surfaces:
        findings.append(_finding(
            "agent-profile-without-tool-switch-path",
            "error",
            "Agent/profile selection needs a real profile mechanism; tool-triggered profile orchestration requires a tool surface and switch_agent_callback.",
        ))

    if "connector" in selected_surfaces and "mcp" in selected_surfaces and "distinguish" not in all_text and "different" not in all_text:
        findings.append(_finding(
            "mcp-connector-semantics-unclear",
            "warning",
            "MCP and Mistral Connectors are both selected, but the design does not distinguish their different runtime semantics.",
        ))

    if "plan-mode" in selected_surfaces and "exit_plan_mode" not in all_text:
        findings.append(_finding(
            "plan-mode-without-exit-plan-mode",
            "warning",
            "Plan-to-implementation gates should use exit_plan_mode unless the design justifies a different approval mechanism.",
        ))

    if "hook" in selected_surfaces and "post_agent_turn" not in all_text and "post agent turn" not in all_text:
        findings.append(_finding(
            "hook-type-unverified",
            "error",
            "Mistral Vibe only exposes POST_AGENT_TURN hooks; hook designs must name that boundary.",
        ))

    if "programmatic" in selected_surfaces and "--output streaming" not in all_text and "--output json" not in all_text:
        findings.append(_finding(
            "programmatic-output-mode-missing",
            "warning",
            "Programmatic workflows should specify --output streaming or --output json for machine-readable evidence.",
        ))

    if "mcp" in selected_surfaces:
        has_sampling_disabled = any(
            phrase in all_text for phrase in ["sampling_enabled = false", "sampling_enabled=false", "sampling_enabled: false"]
        )
        has_justification = any(term in all_text for term in ["justify", "justified", "justification", "risk", "sampling needed", "llm completion needed"])
        if not has_sampling_disabled and not has_justification:
            findings.append(_finding(
                "mcp-sampling-default-enabled",
                "warning",
                "MCP sampling_enabled defaults to True — every configured MCP server can request LLM completions using your API key. Explicitly set sampling_enabled = false or document why LLM completions are needed.",
            ))

    # Check for after_turn usage (not in middleware protocol)
    if "middleware" in selected_surfaces:
        after_turn_terms = ["after_turn", "after turn", "run_after_turn", "after-tool", "after tool", "post_tool", "post-tool"]
        for decision in selected:
            if decision["surface"] == "middleware" and any(term in decision["text"] for term in after_turn_terms):
                findings.append(_finding(
                    "middleware-after-turn-not-supported",
                    "error",
                    "The ConversationMiddleware Protocol only defines before_turn(context) and reset(). There is no after_turn(), run_after_turn, after_tool, post_tool, or any post-tool hook. Middleware fires before every LLM call and cannot intercept tool execution or observe tool results. Scope enforcement must use tool-level interception (BaseTool wrapper or approval_callback), not middleware.",
                    "middleware",
                ))
                break

    # Check for scope-guard-as-middleware anti-pattern
    if "middleware" in selected_surfaces:
        scope_guard_terms = ["scope guard", "scope_guard", "scopeguard", "block file edit", "block edit", "fnmatch", "allowed_patterns", "file outside scope"]
        for decision in selected:
            if decision["surface"] == "middleware" and any(term in decision["text"] for term in scope_guard_terms):
                findings.append(_finding(
                    "scope-guard-as-middleware",
                    "error",
                    "Middleware cannot intercept individual tool calls mid-turn. It only runs before_turn once per LLM call. A middleware cannot block, filter, or inspect individual file edits as they happen. Scope enforcement requires a custom BaseTool wrapper with resolve_permission() or the approval_callback mechanism on AgentLoop.",
                    "middleware",
                ))
                break

    # Check for AgentLoop writing state files directly
    if "middleware" in selected_surfaces or "agent-profile" in selected_surfaces:
        agentloop_write_terms = ["agentloop write", "agentloop state", "agentloop writes", "write state.json", "write .pr"]
        if any(term in all_text for term in agentloop_write_terms):
            findings.append(_finding(
                "agentloop-cannot-write-state",
                "error",
                "AgentLoop has no API to write arbitrary state files. The only persistence it performs is via SessionLogger (conversation history). Any workflow state file (.pr-state.json, state.json, etc.) must be written by the LLM via tool calls (write_file, bash), not by AgentLoop as a first-class operation.",
            ))

    # Check for skill name pattern violations
    skill_name_invalid = ["PRForge", "PR-Forge", "PrForge", "MySkill", "My-Skill", "WorkflowSkill"]
    for decision in selected:
        if decision["surface"] == "skill":
            for invalid_name in skill_name_invalid:
                if invalid_name.lower() in decision["text"]:
                    findings.append(_finding(
                        "skill-name-pattern-violation",
                        "warning",
                        f"Skill name '{invalid_name}' does not match the required pattern ^[a-z0-9]+(-[a-z0-9]+)*$. Skill names must be lowercase, match the directory name, and contain only lowercase letters, numbers, and hyphens.",
                        "skill",
                    ))
                    break

    # Check for phase-gate enforcement without tool trigger
    if "agent-profile" in selected_surfaces and "middleware" not in selected_surfaces:
        phase_gate_terms = ["phase gate", "phase transition", "advance phase", "phase enforcement", "restrict tools per phase"]
        if any(term in all_text for term in phase_gate_terms):
            if "switch_agent_callback" not in all_text and "switch agent" not in all_text and "exit_plan_mode" not in all_text:
                findings.append(_finding(
                    "phase-gate-missing-trigger",
                    "warning",
                    "Phase-gate enforcement via agent profiles requires a trigger. The only real enforcement path is a custom tool that calls ctx.switch_agent_callback(profile_name) to change the active profile. Without this tool, the LLM just reads skill text and 'hopes' it follows phase rules — that is guidance, not enforcement. Use exit_plan_mode for the standard plan-to-implement gate, or a custom tool for custom phases.",
                ))

    text_signal_terms = ["phase_complete:", "phase complete:", "verdict: pass", "verdict: fail", "verdict:pass", "verdict:fail", "complete:", "done:"]
    if any(term in all_text for term in text_signal_terms) and "task" not in selected_surfaces and "tool" not in selected_surfaces:
        findings.append(_finding(
            "text-signal-control-flow",
            "warning",
            "Design appears to use LLM text output as control-flow signals. Text signals are fragile — use a custom tool call returning a BaseModel result instead. The task tool with custom subagents is the correct surface for phase sequencing.",
        ))

    if "reasoning" in req_text and "model" not in all_text and "backend" not in all_text and "reasoningevent" not in all_text:
        findings.append(_finding(
            "reasoning-event-runtime-fit-unchecked",
            "warning",
            "A requirement references reasoning, but the design does not verify model/backend ReasoningEvent support.",
        ))

    # Rule 12: agent-profile-wrong-format
    if "agent-profile" in selected_surfaces:
        non_toml_terms = [".yaml", ".json", ".md", ".yml", ".toml.yaml"]
        for decision in selected:
            if decision["surface"] == "agent-profile":
                for ext in non_toml_terms:
                    if ext in decision["text"]:
                        findings.append(_finding(
                            "agent-profile-wrong-format",
                            "warning",
                            f"AgentManager._discover_agents() only globs *.toml files. Agent profiles written as {ext} files in agent search paths are silently ignored — no error, no warning from the runtime. Use .toml extension for all agent profile files.",
                            "agent-profile",
                        ))
                        break

    # enabled-tools-overrides-disabled-tools (cross-surface)
    if "config" in selected_surfaces:
        for decision in selected:
            if decision["surface"] == "config":
                if ("enabled_tools" in decision["text"] and "disabled_tools" in decision["text"]):
                    findings.append(_finding(
                        "enabled-tools-overrides-disabled-tools",
                        "warning",
                        "ToolManager.available_tools checks enabled_tools first. If enabled_tools is non-empty, disabled_tools is completely ignored — the two lists do not combine. Same rule applies to enabled_skills/disabled_skills in SkillManager. Setting both is a silent bug.",
                        "config",
                    ))
                    break

    errors = [f for f in findings if f["severity"] == "error"]
    return {
        "pass": len(errors) == 0,
        "findings": findings,
        "count": len(findings),
    }


def _check_decision(decision: dict[str, str], findings: list[dict[str, Any]]) -> None:
    surface = decision["surface"]
    text = decision["text"]

    if surface == "middleware":
        invalid_hooks = ["after_tool", "post_tool", "pre_tool", "after turn", "after_turn", "on_event", "during tool"]
        if any(token in text for token in invalid_hooks):
            findings.append(_finding(
                "middleware-invalid-hook",
                "error",
                "Middleware only supports before_turn(context) plus reset(); it cannot run pre/post/during tool or on arbitrary events.",
                surface,
            ))
        if "custom" in text and not any(token in text for token in ["source", "runtime-code", "runtime code", "registered", "registration", "agentloop", "pipeline"]):
            findings.append(_finding(
                "custom-middleware-requires-source-change",
                "error",
                "Custom middleware is valid, but it must be implemented/registered as runtime code; it is not a skill/config/hook-only extension.",
                surface,
            ))
        phase_orchestration_terms = ["advance_phase", "advance phase", "phase_complete", "phase complete", "next phase", "phase transition", "phase sequenc", "phase state machine", "phase manager"]
        if any(term in text for term in phase_orchestration_terms):
            findings.append(_finding(
                "middleware-used-as-phase-orchestrator",
                "error",
                "Middleware is a loop guard, not a phase orchestrator. before_turn() cannot observe LLM output and has a structural one-turn delay on every transition. Use the task tool for phase sequencing: each phase is a task() call, the parent checks TaskResult.completed, and dispatches the next phase.",
                surface,
            ))
        if "reset" in text and "compact" in text and "resetreason" not in text and "reset_reason" not in text:
            findings.append(_finding(
                "middleware-reset-compaction-unhandled",
                "warning",
                "Middleware reset() must check ResetReason to distinguish STOP (clear state) from COMPACT (preserve state). A reset() that clears all state will silently restart the workflow when compaction fires.",
                surface,
            ))
        if "compact" in text and "middlewareaction.compact" not in text and "compact action" not in text:
            findings.append(_finding(
                "middleware-compact-action-unclear",
                "warning",
                "Compaction should be modeled as MiddlewareAction.COMPACT, not as generic message injection.",
                surface,
            ))
        if "stop" in text and "inject_message" in text and "ordering" not in text and "short-circuit" not in text:
            findings.append(_finding(
                "middleware-short-circuit-ordering-missing",
                "warning",
                "Middleware STOP/COMPACT short-circuits the pipeline; designs mixing STOP and INJECT_MESSAGE need ordering rationale.",
                surface,
            ))
        # Rule 8: middleware-cannot-switch-agent
        switch_agent_terms = ["switch_agent", "switch agent", "switch_profile", "agent_manager.switch", "agentmanager.switch"]
        if any(term in text for term in switch_agent_terms):
            findings.append(_finding(
                "middleware-cannot-switch-agent",
                "error",
                "ConversationMiddleware.before_turn() receives only ConversationContext (fields: messages, stats, config). switch_agent_callback lives exclusively in InvokeContext, which is only passed to tools during BaseTool.invoke(). Middleware cannot call switch_agent, switch_profile, or agent_manager.switch_profile — none of these are reachable from ConversationContext.",
                surface,
            ))
        # Rule 10: middleware-compact-missing-metadata
        if "compact" in text or "middlewareaction.compact" in text or "compact action" in text:
            if "old_tokens" not in text and "threshold" not in text and "metadata" not in text:
                findings.append(_finding(
                    "middleware-compact-missing-metadata",
                    "error",
                    "AgentLoop._handle_middleware_result() reads result.metadata.get('old_tokens', ...) and result.metadata.get('threshold', ...) when handling MiddlewareAction.COMPACT. Custom middleware returning COMPACT without these keys silently falls back to self.stats.context_tokens and the model's auto_compact_threshold, producing misleading telemetry and CompactStartEvent payloads. Populate metadata={'old_tokens': ..., 'threshold': ...} in the MiddlewareResult.",
                    surface,
                ))

    if surface == "skill":
        enforcement_terms = ["enforce", "prevent", "guarantee", "restrict"]
        if any(term in text for term in enforcement_terms) and "allowed_tools" not in text and "allowed-tools" not in text:
            findings.append(_finding(
                "skill-enforcement-without-allowed-tools",
                "warning",
                "Skills are prompt guidance except for metadata constraints like allowed_tools; enforcement claims should name that mechanism or another runtime control.",
                surface,
            ))
        # Rule 11: skill-allowed-tools-comma-delimited
        if "allowed-tools" in text or "allowed_tools" in text:
            raw = decision.get("text", "")
            # Check for comma-separated values in the original (non-lowered) text
            # Look for patterns like "bash, grep" or "bash,grep" near allowed-tools
            import re
            comma_pattern = re.search(r'allowed[-_\s]tools?\s*[:\s]\s*["\']?([a-z][\s,]*[a-z][^,]*),', raw, re.IGNORECASE)
            if comma_pattern or ", " in raw.split("allowed")[1][:80] if "allowed" in raw.lower() else False:
                findings.append(_finding(
                    "skill-allowed-tools-comma-delimited",
                    "warning",
                    "SkillMetadata.parse_allowed_tools splits on whitespace via .split(), not commas. A frontmatter value of allowed-tools: \"bash, grep\" is parsed as a single tool name \"bash,\" — silently broken, no validation error. Use space-separated values: allowed-tools: bash grep",
                    surface,
                ))

    if surface == "tool":
        if "post-tool" in text or "post tool" in text:
            if "get_result_extra" not in text:
                findings.append(_finding(
                    "tool-post-context-without-result-extra",
                    "warning",
                    "Post-tool context injection should use get_result_extra(), not middleware.",
                    surface,
                ))
        if "permission" in text and not any(token in text for token in ["resolve_permission", "allowlist", "denylist", "sensitive_patterns", "basetoolconfig"]):
            findings.append(_finding(
                "tool-permission-config-unspecified",
                "warning",
                "Tool permission designs should consider resolve_permission() or BaseToolConfig permission/allowlist/denylist/sensitive_patterns.",
                surface,
            ))
        if "ask user" in text and "ask_user_question" not in text:
            findings.append(_finding(
                "generic-user-question-tool",
                "warning",
                "Structured clarification/approval should use ask_user_question with choices and optional content_preview.",
                surface,
            ))
        # Rule 6: tool-class-suffix-produces-wrong-name
        # Detect class names ending in Tool or containing consecutive uppercase (acronyms)
        import re
        tool_class_pattern = re.search(r'(?:class\s+)?([A-Z][a-zA-Z]*Tool)\b', decision.get("text", ""))
        if tool_class_pattern:
            class_name = tool_class_pattern.group(1)
            # Check if it ends with "Tool" (suffix adds _tool to the name)
            if class_name.endswith("Tool") and class_name != "Tool":
                base = class_name[:-4]  # Remove "Tool" suffix
                # Simulate the regex: re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
                derived = re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower()
                findings.append(_finding(
                    "tool-class-suffix-produces-wrong-name",
                    "error",
                    f"BaseTool.get_name() derives the registered name via re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower(). Class '{class_name}' registers as '{derived}' — not '{base.lower()}' or '{base.lower().replace('_', '')}'. The 'Tool' suffix becomes part of the registered name. Avoid the 'Tool' suffix: class WriteFile registers as 'write_file'. For acronyms (PR, MCP, LLM), consecutive uppercase letters each get an underscore prefix: 'PRForgeTool' → 'p_r_forge_tool'. Use a single-word class name or set name explicitly via the ClassVar.",
                    surface,
                ))
        # Also detect acronym patterns without Tool suffix
        acronym_pattern = re.search(r'(?:class\s+)?([A-Z]{2,}[a-zA-Z]+)', decision.get("text", ""))
        if acronym_pattern and not tool_class_pattern:
            class_name = acronym_pattern.group(1)
            if class_name not in ("BaseTool", "ToolResult", "ToolArgs", "ToolError"):
                derived = re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower()
                findings.append(_finding(
                    "tool-class-suffix-produces-wrong-name",
                    "error",
                    f"BaseTool.get_name() inserts underscores before each uppercase letter. Class '{class_name}' registers as '{derived}'. Consecutive uppercase letters (acronyms like PR, MCP, LLM) each get an underscore: 'PRForge' → 'p_r_forge'. Avoid acronyms in class names, or set name explicitly via ClassVar.",
                    surface,
                ))
        # Rule 13: tool-permission-unknown-value
        unknown_permissions = ["conditional", "once", "prompt", "require", "skip", "auto", "manual", "dynamic"]
        for perm in unknown_permissions:
            if f"permission: {perm}" in text or f"permission={perm}" in text or f'"{perm}"' in text:
                findings.append(_finding(
                    "tool-permission-unknown-value",
                    "warning",
                    f"ToolPermission only defines ALWAYS, NEVER, ASK. ToolPermission.by_name() raises ToolPermissionError for anything else. Value '{perm}' is not a valid permission. Use 'always', 'never', or 'ask'.",
                    surface,
                ))
                break

    if surface == "source":
        config_terms = ["permission", "allowlist", "denylist", "enabled_tools", "disabled_tools", "tool_paths"]
        if any(term in text for term in config_terms) and "why config is insufficient" not in text:
            findings.append(_finding(
                "source-change-may-be-overbuilt",
                "warning",
                "Permission/tool-availability changes may be solvable with config or BaseToolConfig; justify why source is required.",
                surface,
            ))

    if surface == "subagent":
        if any(token in text for token in ["write file", "write files", "edit file", "edit files", "create file", "patch file"]):
            findings.append(_finding(
                "subagent-assigned-file-writing",
                "error",
                "Subagents return text; the parent agent must write project files.",
                surface,
            ))
        if "custom" in text and "agent_type" not in text and "subagent" not in text:
            findings.append(_finding(
                "custom-subagent-agent-type-missing",
                "warning",
                "Custom subagents must be configured with agent_type = \"subagent\".",
                surface,
            ))
        # Rule 9: subagent-scratchpad-not-available
        scratchpad_terms = ["scratchpad_dir", "scratchpad", "ctx.scratchpad"]
        if any(term in text for term in scratchpad_terms):
            findings.append(_finding(
                "subagent-scratchpad-not-available",
                "error",
                "AgentLoop.__init__ explicitly sets scratchpad_dir = None when is_subagent=True. InvokeContext.scratchpad_dir will therefore always be None inside subagent tool calls. Any tool run() implementation in a subagent profile that accesses ctx.scratchpad_dir without a null guard will fail. The parent's scratchpad path is passed as text in the task prompt, not via InvokeContext.",
                surface,
            ))
        # Rule 14: subagent-as-primary-agent
        primary_agent_terms = ["--agent", "agent_name", "initial agent", "primary agent", "main agent"]
        if any(term in text for term in primary_agent_terms):
            findings.append(_finding(
                "subagent-as-primary-agent",
                "warning",
                "AgentManager.__init__ raises ValueError at runtime if a profile with agent_type != AgentType.AGENT is passed as the initial agent. A subagent-typed profile cannot be used as the --agent flag or agent_name constructor argument to AgentLoop. Subagents are only valid as task() targets.",
                surface,
            ))

    if surface == "hook":
        invalid_hook_terms = ["pre-turn", "pre turn", "tool hook", "pre_tool", "post_tool", "mid-turn", "mid turn", "per-file"]
        if any(token in text for token in invalid_hook_terms):
            findings.append(_finding(
                "hook-invalid-boundary",
                "error",
                "Hooks are POST_AGENT_TURN only; they cannot intercept pre-turn, tool-level, mid-turn, or per-file behavior.",
                surface,
            ))
        if "retry" in text and "exit 2" not in text and "exit code 2" not in text:
            findings.append(_finding(
                "hook-retry-exit-code-missing",
                "warning",
                "POST_AGENT_TURN retry behavior depends on exit code 2 reinjecting stdout.",
                surface,
            ))
        # Rule 7: hook-type-not-supported
        invalid_hook_types = ["pre_agent_turn", "on_tool_call", "on_error", "pre_turn", "post_tool_call", "on_event", "on_phase"]
        for hook_type in invalid_hook_types:
            if hook_type in text:
                findings.append(_finding(
                    "hook-type-not-supported",
                    "error",
                    f"HookType is a StrEnum with exactly one member: POST_AGENT_TURN. '{hook_type}' is not a valid hook type. Any design referencing pre_agent_turn, on_tool_call, on_error, pre_turn, post_tool_call, or on_event as a hook type will fail at HookConfig validation. Only post_agent_turn is supported.",
                    surface,
                ))
                break
        # Rule 15: hook-command-not-shell-executable
        # Detect Python import paths or callable syntax that won't work as subprocess commands
        import re
        command_value = decision.get("text", "")
        # Look for dotted Python paths like my_package.my_module:handler
        if re.search(r'[a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_.]*:[a-zA-Z_]', command_value):
            findings.append(_finding(
                "hook-command-not-shell-executable",
                "warning",
                "HookConfig.command is a shell command string executed as a subprocess. Python import paths (my_package.my_module:handler) pass validation (non-blank string check only) but fail at subprocess execution. Use an actual shell command: a script path, a CLI tool, or 'python -c \"import x; x.run()\"'.",
                surface,
            ))

    if surface == "todo":
        if any(token in text for token in ["cross-session", "across sessions", "audit", "persistent record", "durable"]):
            findings.append(_finding(
                "todo-used-as-durable-state",
                "warning",
                "todo is session-scoped; durable audit/proof should be written to lifecycle artifacts.",
                surface,
            ))

    if surface == "scratchpad":
        if any(token in text for token in ["canonical", "source of truth", "approval record", "workflow_contract", "plan.md", "design.md"]):
            findings.append(_finding(
                "scratchpad-used-for-canonical-record",
                "warning",
                "Scratchpad is for temporary artifacts, not canonical lifecycle records.",
                surface,
            ))

    if surface == "user-question":
        if "content_preview" not in text and "choice" not in text:
            findings.append(_finding(
                "ask-user-question-schema-underused",
                "warning",
                "ask_user_question should use structured choices and content_preview when appropriate.",
                surface,
            ))

    if surface == "agents-md":
        if any(token in text for token in ["phase status", "approval", "evidence", "dynamic state", "todo"]):
            findings.append(_finding(
                "agents-md-used-for-dynamic-state",
                "warning",
                "AGENTS.md is persistent context injection, not dynamic workflow state or approval evidence.",
                surface,
            ))

    # === Rules from second DeepWiki source analysis ===

    # Tool discovery rules (apply to tool surface)
    if surface == "tool":
        # tool-file-starts-with-underscore
        underscore_tool_terms = ["_helpers", "_my_tool", "_tool", "_private", "_internal", "_.py"]
        if any(term in text for term in underscore_tool_terms):
            findings.append(_finding(
                "tool-file-starts-with-underscore",
                "error",
                "ToolManager._load_tools_from_file() returns None immediately if the filename starts with _. A custom tool in _helpers.py or _my_tool.py is silently ignored — no warning, no error. Rename tool files to not start with underscore.",
                surface,
            ))
        # tool-import-error-silent
        if "import" in text and ("syntax error" in text or "import error" in text or "broken import" in text or "bad import" in text):
            findings.append(_finding(
                "tool-import-error-silent",
                "warning",
                "_load_tools_from_file() wraps spec.loader.exec_module(module) in a bare except Exception: return. A syntax error, bad import, or NameError in a custom tool file causes it to be silently dropped. Verify tool files are importable.",
                surface,
            ))
        # tool-state-shared-across-concurrent-calls
        if "self.state" in text or "self._state" in text or "mutable state" in text or "instance variable" in text:
            if "lock" not in text and "asyncio.Lock" not in text and "thread-safe" not in text and "threadsafe" not in text:
                findings.append(_finding(
                    "tool-state-shared-across-concurrent-calls",
                    "error",
                    "ToolManager.get() caches one tool instance per name per session. _run_tools_concurrently() runs all tool calls in the same LLM turn as parallel asyncio.Tasks. Any mutation of self.state inside run() without an asyncio.Lock is a data race. Use asyncio.Lock for mutable shared state.",
                    surface,
                ))

    # Agent profile rules (apply to agent-profile surface)
    if surface == "agent-profile":
        # agent-name-derived-from-toml-stem
        if "name" in text and ("toml" in text or "profile" in text):
            findings.append(_finding(
                "agent-name-derived-from-toml-stem",
                "error",
                "AgentProfile.from_toml() sets name=path.stem — the filename without extension. A name = \"my-agent\" key inside the TOML is not the agent name — it goes into overrides as an unknown config key. The agent name is always the filename stem (e.g., reviewer.toml → name is \"reviewer\"). To set display name, use display_name in TOML.",
                surface,
            ))
        # agent-safety-unknown-value
        unknown_safety = ["permissive", "strict", "normal", "default", "safe_mode", "cautious", "risky"]
        for val in unknown_safety:
            if f"safety: {val}" in text or f"safety={val}" in text or f'"{val}"' in text:
                findings.append(_finding(
                    "agent-safety-unknown-value",
                    "error",
                    f"AgentSafety only has SAFE, NEUTRAL, DESTRUCTIVE, YOLO. Value '{val}' raises ValueError at agent load time, causing the agent to be silently skipped. Use one of: safe, neutral, destructive, yolo.",
                    surface,
                ))
                break
        # agent-duplicate-name-silently-skipped
        if "duplicate" in text or "same name" in text or "multiple" in text and "search path" in text:
            findings.append(_finding(
                "agent-duplicate-name-silently-skipped",
                "warning",
                "_discover_agents() skips duplicate agent names with only a logger.debug() call — no user-visible warning. If two search paths both contain reviewer.toml, the second is silently dropped. Search path order determines which wins. Avoid placing the same agent stem name in multiple search paths.",
                surface,
            ))

    # Skill discovery rules (apply to skill surface)
    if surface == "skill":
        # skill-not-in-subdirectory
        if "SKILL.md" in text and ("root" in text or "directly" in text or "top-level" in text or "search path root" in text):
            findings.append(_finding(
                "skill-not-in-subdirectory",
                "error",
                "SkillManager._discover_skills_in_dir() iterates base.iterdir(), skips non-directories, then looks for <dir>/SKILL.md. A SKILL.md placed directly at the root of a skill search path (not inside a named subdirectory) is silently ignored. Skills must be in a subdirectory: skills/my-skill/SKILL.md.",
                surface,
            ))
        # skill-name-directory-mismatch
        if "directory" in text and "name" in text and ("differ" in text or "mismatch" in text or "doesn't match" in text or "does not match" in text):
            findings.append(_finding(
                "skill-name-directory-mismatch",
                "warning",
                "_parse_skill_file() logs a warning when metadata.name != skill_path.parent.name but still loads the skill under metadata.name. The skill is registered and invocable by its frontmatter name, not the directory name. The directory name is cosmetic only — but the CLI and skill bus use the frontmatter name for invocation.",
                surface,
            ))
        # builtin-skill-name-reserved
        builtin_names = ["vibe-workflow-init", "vibe-workflow-design", "vibe-workflow-plan",
                         "vibe-workflow-apply", "vibe-workflow-validate", "vibe-workflow-inspect",
                         "vibe-workflow-update", "vibe-workflow-realize"]
        for builtin in builtin_names:
            if builtin in text:
                findings.append(_finding(
                    "builtin-skill-name-reserved",
                    "error",
                    f"_discover_skills_in_dir() silently skips any custom skill whose metadata.name matches a builtin skill name. '{builtin}' is a builtin — choosing this name for a custom skill means it will be silently dropped. Choose a different name.",
                    surface,
                ))
                break

    # === Rules from third DeepWiki full-source analysis ===

    # Tool implementation rules
    if surface == "tool":
        # tool-run-must-yield-not-return
        if "run(" in text and ("return result" in text or "return toolresult" in text or "return toolstream" in text):
            findings.append(_finding(
                "tool-run-must-yield-not-return",
                "error",
                "BaseTool.run() is declared as AsyncGenerator[ToolStreamEvent | ToolResult, None]. A subclass that uses 'return result' instead of 'yield result' produces a coroutine, not an async generator. invoke() does 'async for item in self.run(args, ctx)' — this raises TypeError: 'coroutine' object is not an async generator at call time. Use 'yield' to emit results.",
                surface,
            ))
        # tool-missing-description-classvar
        if "class" in text and "basetool" in text and "description" not in text:
            findings.append(_finding(
                "tool-missing-description-classvar",
                "warning",
                "BaseTool.description defaults to a placeholder string. Not overriding it means the LLM receives this placeholder as the tool's description in the function schema. Define 'description: ClassVar[str] = \"...\"' in every custom tool.",
                surface,
            ))
        # invoke-context-plan-file-path-nullable
        if "plan_file_path" in text or "ctx.plan_file" in text:
            if "null" not in text and "none" not in text and "guard" not in text and "check" not in text:
                findings.append(_finding(
                    "invoke-context-plan-file-path-nullable",
                    "error",
                    "InvokeContext.plan_file_path is Path | None with default=None. It is only populated when the active agent is the plan agent. Tools that access ctx.plan_file_path without a null guard will raise AttributeError or TypeError in every other context.",
                    surface,
                ))
        # invoke-context-approval-callback-nullable
        if "approval_callback" in text or "ctx.approval" in text:
            if "null" not in text and "none" not in text and "guard" not in text and "check" not in text:
                findings.append(_finding(
                    "invoke-context-approval-callback-nullable",
                    "error",
                    "InvokeContext.approval_callback is ApprovalCallback | None with default=None. In programmatic/non-interactive contexts (--output json, subagent calls), it is None. Tools that call await ctx.approval_callback(...) without null-checking will raise TypeError.",
                    surface,
            ))
        # mcp-tool-name-uses-underscore
        if "mcp" in text and ("allowed_tools" in text or "allowed-tools" in text or "enabled_tools" in text or "disabled_tools" in text):
            if "." in text or "/" in text:
                findings.append(_finding(
                    "mcp-tool-name-uses-underscore",
                    "warning",
                    "MCP tools are registered as {server_name}_{tool_name} with underscores. References using dots (fetch_server.get), slashes, or raw remote names won't match in enabled_tools/disabled_tools/allowed_tools patterns. Use underscore-separated names.",
                    surface,
                ))
        # tool-discovery-recursive-rglob
        if "tool_paths" in text or "tool path" in text:
            if "subdirectory" in text or "helpers" in text or "utils" in text or "shared" in text:
                findings.append(_finding(
                    "tool-discovery-recursive-rglob",
                    "warning",
                    "ToolManager._iter_tool_classes() uses base.rglob('*.py') — it recursively searches ALL subdirectories. Any non-abstract BaseTool subclass in helpers/, utils/, or shared/ subdirectories will be registered as a tool, including intermediate base classes. Keep tool files at the top level of tool_paths.",
                    surface,
                ))

    # Agent profile rules
    if surface == "agent-profile":
        # agent-profile-not-flat-directory
        if "subdirectory" in text or "subdir" in text or "nested" in text or "phase1/" in text or "phase2/" in text:
            findings.append(_finding(
                "agent-profile-not-flat-directory",
                "error",
                "AgentManager._discover_agents() uses base.glob('*.toml') — not rglob. Agent TOML files in subdirectories of agent_paths are silently ignored. Place all agent TOML files directly in the search path root.",
                surface,
            ))
        # agent-overrides-disabled-tools-vs-base-disabled
        if "disabled_tools" in text and "override" in text:
            if "base_disabled" not in text:
                findings.append(_finding(
                    "agent-overrides-disabled-tools-vs-base-disabled",
                    "error",
                    "AgentProfile.apply_to_config() uses _deep_merge for override keys. Setting disabled_tools directly replaces the entire list (deep merge overwrites lists). The correct key for additive disabling is base_disabled, which is extracted and unioned with the existing disabled_tools.",
                    surface,
                ))
        # builtin-agent-name-override
        builtin_agent_names = ["default", "plan", "chat", "accept-edits", "auto-approve", "explore", "lean"]
        for builtin in builtin_agent_names:
            if builtin in text and ("toml" in text or "agent" in text or "profile" in text):
                findings.append(_finding(
                    "builtin-agent-name-override",
                    "warning",
                    f"Unlike skills, AgentManager._discover_agents() allows custom TOML files to override builtin agents — logged at INFO only. A custom '{builtin}.toml' silently replaces the builtin agent. Avoid using builtin agent names (default, plan, chat, accept-edits, auto-approve, explore, lean) for custom profiles.",
                    surface,
                ))
                break

    # Hook rules
    if surface == "hook":
        # hook-timeout-default-30s
        if "network" in text or "compile" in text or "test" in text or "build" in text or "http" in text or "api" in text:
            if "timeout" not in text:
                findings.append(_finding(
                    "hook-timeout-default-30s",
                    "warning",
                    "HookConfig.timeout defaults to 30.0 seconds. Hooks involving network calls, compilation, or test suites that exceed this are killed and reported as WARNING — no retry, no error escalation. Set an explicit timeout override for long-running hooks.",
                    surface,
                ))

    # Config-level rules (cross-surface)
    # enabled-tools-overrides-disabled-tools — checked at top level below

    # Middleware pipeline rules (apply to middleware surface)
    if surface == "middleware":
        # middleware-inject-lost-before-stop
        if "inject_message" in text and ("stop" in text or "compact" in text):
            if "ordering" not in text and "order" not in text and "before" not in text and "after" not in text:
                findings.append(_finding(
                    "middleware-inject-lost-before-stop",
                    "warning",
                    "MiddlewarePipeline.run_before_turn() accumulates INJECT_MESSAGE results, but if any middleware returns STOP or COMPACT, it immediately returns — discarding all previously accumulated inject messages. Middleware ordering is load-order-dependent. Place INJECT_MESSAGE middleware AFTER STOP/COMPACT middleware, or document the ordering rationale.",
                    surface,
                ))

    # Hook rules (apply to hook surface)
    if surface == "hook":
        # hook-retry-requires-stdout
        if "retry" in text and "stderr" in text:
            findings.append(_finding(
                "hook-retry-requires-stdout",
                "warning",
                "HooksManager.run() only triggers the retry path when result.exit_code == HookExitCode.RETRY and result.stdout. A hook that exits with code 2 but writes its retry message to stderr instead of stdout falls through to the generic warning handler — no retry, no HookUserMessage injected. Write retry instructions to stdout.",
                surface,
            ))
        # hook-max-retries-is-three
        if "retry" in text and ("unlimited" in text or "infinite" in text or "always" in text or "indefinitely" in text):
            findings.append(_finding(
                "hook-max-retries-is-three",
                "warning",
                "_MAX_RETRIES = 3 is hardcoded. After 3 retries, the hook is marked ERROR and the loop continues without further retries. Retry count resets per user message (via reset_retry_count() at the start of _conversation_loop), not per session. Workflows cannot retry more than 3 times per user turn.",
                surface,
            ))

    # Scratchpad rules (apply to scratchpad surface)
    if surface == "scratchpad":
        # scratchpad-init-can-return-none-for-primary-agent
        if "scratchpad_dir" in text or "ctx.scratchpad_dir" in text:
            if "null" not in text and "none" not in text and "guard" not in text and "check" not in text:
                findings.append(_finding(
                    "scratchpad-init-can-return-none-for-primary-agent",
                    "warning",
                    "init_scratchpad() catches OSError from tempfile.mkdtemp() and returns None. AgentLoop.__init__ assigns this directly: self.scratchpad_dir = init_scratchpad(...). Even primary agents can have scratchpad_dir = None if temp directory creation fails. All tool run() implementations that access ctx.scratchpad_dir must have a null guard, even in non-subagent contexts.",
                    surface,
                ))


def _normalize_decision(decision: dict[str, Any]) -> dict[str, str]:
    surface = _canonical_surface(decision.get("surface"))
    return {
        "surface": surface or "",
        "text": _flatten_text(decision).lower(),
    }


def _design_values(contract: dict[str, Any], key: str) -> list[Any]:
    values = []
    if isinstance(contract.get(key), list):
        values.extend(contract[key])
    design = contract.get("design")
    if isinstance(design, dict) and isinstance(design.get(key), list):
        values.extend(design[key])
    return values


def _flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(v) for v in value)
    return str(value)


def _canonical_surface(surface: Any) -> str | None:
    value = str(surface or "").strip().lower().replace("_", "-")
    aliases = {
        "tools": "tool",
        "tooling": "tool",
        "skills": "skill",
        "mcp-server": "mcp",
        "mcp-servers": "mcp",
        "mistral-connector": "connector",
        "mistral-connectors": "connector",
        "connectors": "connector",
        "agents": "agent-profile",
        "profiles": "agent-profile",
        "agent": "agent-profile",
        "subagents": "subagent",
        "subagent": "subagent",
        "task": "subagent",
        "task-tool": "subagent",
        "hooks": "hook",
        "post-agent-turn": "hook",
        "post_agent_turn": "hook",
        "programmatic-mode": "programmatic",
        "streaming-output": "programmatic",
        "json-output": "programmatic",
        "scratch": "scratchpad",
        "agents.md": "agents-md",
        ".vibe/agents.md": "agents-md",
        "ask-user-question": "user-question",
        "ask_user_question": "user-question",
        "exit-plan-mode": "plan-mode",
        "exit_plan_mode": "plan-mode",
        "events": "event",
        "sessions": "session",
        "source-changes": "source",
    }
    value = aliases.get(value, value)
    known = {
        "config",
        "skill",
        "tool",
        "mcp",
        "connector",
        "middleware",
        "agent-profile",
        "subagent",
        "hook",
        "programmatic",
        "scratchpad",
        "agents-md",
        "todo",
        "user-question",
        "plan-mode",
        "event",
        "session",
        "state",
        "source",
        "backend-boundary",
        "not-feasible",
    }
    return value if value in known else None


def _finding(rule: str, severity: str, message: str, surface: str | None = None) -> dict[str, str]:
    finding = {"rule": rule, "severity": severity, "message": message}
    if surface:
        finding["surface"] = surface
    return finding


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: pattern-fit-linter.py <WORKFLOW_CONTRACT.json>")
        sys.exit(1)

    try:
        result = lint_pattern_fit(sys.argv[1])
    except Exception as exc:
        result = {
            "pass": False,
            "findings": [{"rule": "pattern-fit-parse-error", "severity": "error", "message": str(exc)}],
            "count": 1,
        }
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["pass"] else 1)
