#!/usr/bin/env python3
"""Validate VibeFlow design decision traceability without constraining implementation shape."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from workflow_manifest import load_workflow_manifest


SELECTED = "selected"
REJECTED = {"rejected", "not_applicable"}
APPLIED_PHASES = {"applied", "validated"}
VALIDATED_PHASES = {"validated"}
RUNTIME_REQUIREMENT_STATUSES = {"", "runtime"}


def lint_design_contract(manifest_path: str, contract_path: str | None = None) -> dict[str, Any]:
    manifest, warnings = load_workflow_manifest(manifest_path)
    resolved_contract = _resolve_contract_path(manifest_path, contract_path)
    if not resolved_contract:
        return {
            "pass": True,
            "violations": [],
            "warnings": ["WORKFLOW_CONTRACT.json not found; design decision contract was not checked"],
            "contract_path": None,
            "normalization_warnings": warnings,
        }

    with resolved_contract.open() as f:
        contract = json.load(f)

    violations: list[dict[str, Any]] = []
    phase = contract.get("phase", "")
    decisions = _design_values(contract, "surfaceDecisions")
    requirements = _design_values(contract, "requirements")

    if not decisions:
        violations.append({
            "rule": "design-decisions-missing",
            "message": "WORKFLOW_CONTRACT.json must record surfaceDecisions for design traceability",
        })

    for idx, decision in enumerate(decisions):
        _check_surface_decision(decision, idx, phase, manifest, violations)

    selected_surfaces: set[str] = {
        s
        for decision in decisions
        if isinstance(decision, dict) and decision.get("status") == SELECTED
        for s in (_canonical_surface(decision.get("surface")),)
        if s is not None
    }

    for idx, requirement in enumerate(requirements):
        _check_requirement(requirement, idx, selected_surfaces, violations)

    for idx, amendment in enumerate(contract.get("amendments", [])):
        _check_amendment(amendment, idx, violations)

    return {
        "pass": len(violations) == 0,
        "violations": violations,
        "warnings": [],
        "contract_path": str(resolved_contract),
        "phase": phase,
        "normalization_warnings": warnings,
    }


def _resolve_contract_path(manifest_path: str, contract_path: str | None) -> Path | None:
    candidates = []
    manifest_dir = Path(manifest_path).resolve().parent
    if contract_path:
        supplied = Path(contract_path)
        candidates.append(supplied if supplied.is_absolute() else manifest_dir / supplied)
    candidates.extend([
        manifest_dir / "WORKFLOW_CONTRACT.json",
        manifest_dir.parent / "WORKFLOW_CONTRACT.json",
        Path.cwd() / "WORKFLOW_CONTRACT.json",
    ])
    for candidate in candidates:
        if candidate.exists():
            # Follow contract_source pointer for realize-mode contracts.
            try:
                stub = json.loads(candidate.read_text())
                source_ref = stub.get("contract_source")
                if source_ref:
                    resolved = candidate.parent / source_ref
                    if resolved.exists():
                        return resolved
            except (json.JSONDecodeError, OSError):
                pass
            return candidate
    return None


def _design_values(contract: dict[str, Any], key: str) -> list[Any]:
    values = []
    if isinstance(contract.get(key), list):
        values.extend(contract[key])
    design = contract.get("design")
    if isinstance(design, dict) and isinstance(design.get(key), list):
        values.extend(design[key])
    return values


def _check_surface_decision(
    decision: Any,
    idx: int,
    phase: str,
    manifest: dict[str, Any],
    violations: list[dict[str, Any]],
) -> None:
    if not isinstance(decision, dict):
        violations.append({
            "rule": "surface-decision-invalid",
            "decision": idx,
            "message": "surfaceDecisions entries must be objects",
        })
        return

    surface = _canonical_surface(decision.get("surface"))
    status = decision.get("status")
    if not surface:
        violations.append({
            "rule": "surface-decision-missing-surface",
            "decision": idx,
            "message": "Surface decision must name a known runtime surface",
        })
    if status not in {SELECTED, *REJECTED}:
        violations.append({
            "rule": "surface-decision-invalid-status",
            "surface": decision.get("surface"),
            "message": "Surface decision status must be selected, rejected, or not_applicable",
        })
        return
    if not _nonempty_text(decision.get("reason")):
        violations.append({
            "rule": "surface-decision-missing-reason",
            "surface": decision.get("surface"),
            "message": "Every surface decision needs a rationale",
        })

    if status in REJECTED:
        return

    if not _nonempty_list(decision.get("requiredCapabilities")):
        violations.append({
            "rule": "selected-surface-missing-capabilities",
            "surface": surface,
            "message": f"Selected surface '{surface}' must explain the capability it provides",
        })
    if not _nonempty_list(decision.get("contracts")):
        violations.append({
            "rule": "selected-surface-missing-contracts",
            "surface": surface,
            "message": f"Selected surface '{surface}' must name the runtime contract it obeys",
        })
    if phase in APPLIED_PHASES and not _nonempty_list(decision.get("implementationEvidence")):
        violations.append({
            "rule": "selected-surface-missing-implementation-evidence",
            "surface": surface,
            "message": f"Applied workflow selected '{surface}' but recorded no implementation evidence",
        })
    if phase in VALIDATED_PHASES and not _nonempty_list(decision.get("validationEvidence")):
        violations.append({
            "rule": "selected-surface-missing-validation-evidence",
            "surface": surface,
            "message": f"Validated workflow selected '{surface}' but recorded no validation proof",
        })
    if surface and not _manifest_supports_surface(manifest, surface):
        violations.append({
            "rule": "selected-surface-missing-manifest-support",
            "surface": surface,
            "message": f"Manifest does not expose expected support for selected surface '{surface}'",
        })


def _check_requirement(
    requirement: Any,
    idx: int,
    selected_surfaces: set[str],
    violations: list[dict[str, Any]],
) -> None:
    if not isinstance(requirement, dict):
        violations.append({
            "rule": "requirement-invalid",
            "requirement": idx,
            "message": "requirements entries must be objects",
        })
        return
    req_id = requirement.get("id", idx)
    status = str(requirement.get("status", "runtime")).strip()
    surfaces: set[str] = {
        s
        for surface in requirement.get("selected_surfaces", [])
        for s in (_canonical_surface(surface),)
        if s is not None
    }

    if status in RUNTIME_REQUIREMENT_STATUSES and not surfaces:
        violations.append({
            "rule": "requirement-missing-selected-surface",
            "requirement": req_id,
            "message": "Runtime requirement must map to at least one selected surface",
        })
    missing = sorted(surfaces - selected_surfaces)
    if missing:
        violations.append({
            "rule": "requirement-surface-not-selected",
            "requirement": req_id,
            "surfaces": missing,
            "message": "Requirement references surface(s) that are not selected in surfaceDecisions",
        })
    if status in RUNTIME_REQUIREMENT_STATUSES and not _nonempty_text(requirement.get("success_proof")):
        violations.append({
            "rule": "requirement-missing-success-proof",
            "requirement": req_id,
            "message": "Runtime requirement must describe how success will be proven",
        })


def _check_amendment(amendment: Any, idx: int, violations: list[dict[str, Any]]) -> None:
    if not isinstance(amendment, dict):
        violations.append({"rule": "amendment-invalid", "amendment": idx, "message": "amendments entries must be objects"})
        return
    for field in ("old_surface", "new_surface", "reason", "affected_files", "revalidation_targets"):
        if not amendment.get(field):
            violations.append({
                "rule": "amendment-missing-field",
                "amendment": idx,
                "field": field,
                "message": f"Contract amendment[{idx}] is missing required field '{field}'",
            })


def _manifest_supports_surface(manifest: dict[str, Any], surface: str) -> bool:
    if surface in {"config", "state", "session"}:
        return bool(manifest.get("state") or manifest.get("commands") or manifest.get("validation"))
    if surface == "tool":
        return bool(manifest.get("tooling", {}).get("requiredTools"))
    if surface == "middleware":
        return bool(manifest.get("middleware"))
    if surface == "skill":
        return True
    if surface in {"mcp", "connector", "agent-profile", "subagent", "hook", "programmatic", "scratchpad", "agents-md", "todo", "user-question", "plan-mode", "event", "source", "backend-boundary", "not-feasible"}:
        return True
    return False


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonempty_list(value: Any) -> bool:
    return isinstance(value, list) and any(_nonempty_text(item) for item in value)


def _canonical_surface(surface: Any) -> str | None:
    value = str(surface or "").strip().lower().replace("_", "-")
    aliases = {
        "tools": "tool",
        "tooling": "tool",
        "skills": "skill",
        "skill-only": "skill",
        "mcp-server": "mcp",
        "mcp-servers": "mcp",
        "mistral-connector": "connector",
        "mistral-connectors": "connector",
        "connectors": "connector",
        "agents": "agent-profile",
        "profiles": "agent-profile",
        "agent": "agent-profile",
        "subagents": "subagent",
        "task": "subagent",
        "task-tool": "subagent",
        "middleware-level": "middleware",
        "hooks": "hook",
        "post-agent-turn": "hook",
        "programmatic-mode": "programmatic",
        "streaming-output": "programmatic",
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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: design-contract-linter.py <manifest.json|manifest.yaml> [WORKFLOW_CONTRACT.json]")
        sys.exit(1)

    try:
        result = lint_design_contract(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    except Exception as exc:
        result = {
            "pass": False,
            "violations": [{"rule": "design-contract-parse-error", "message": str(exc)}],
            "warnings": [],
        }

    print(json.dumps(result, indent=2))
    sys.exit(0 if result["pass"] else 1)
