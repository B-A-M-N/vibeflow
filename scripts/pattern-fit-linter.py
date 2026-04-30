#!/usr/bin/env python3
"""Flag suspicious Mistral Vibe runtime surface patterns in workflow contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path
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

    if surface == "source":
        config_terms = ["permission", "allowlist", "denylist", "enabled_tools", "disabled_tools", "tool_paths"]
        if any(term in text for term in config_terms) and "why config is insufficient" not in text:
            findings.append(_finding(
                "source-change-may-be-overbuilt",
                "warning",
                "Permission/tool-availability changes may be solvable with config or BaseToolConfig; justify why source is required.",
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
        "hooks": "hook",
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
        "hook",
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
