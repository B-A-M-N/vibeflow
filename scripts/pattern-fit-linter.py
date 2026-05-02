#!/usr/bin/env python3
"""Flag suspicious Mistral Vibe runtime surface patterns in workflow contracts."""

from __future__ import annotations

import json
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

    if surface == "skill":
        enforcement_terms = ["enforce", "prevent", "guarantee", "restrict"]
        if any(term in text for term in enforcement_terms) and "allowed_tools" not in text and "allowed-tools" not in text:
            findings.append(_finding(
                "skill-enforcement-without-allowed-tools",
                "warning",
                "Skills are prompt guidance except for metadata constraints like allowed_tools; enforcement claims should name that mechanism or another runtime control.",
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
