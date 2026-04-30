#!/usr/bin/env python3
"""VibeFlow Workflow Linter - hard checks for workflow manifest."""

import sys
import json

from workflow_manifest import load_workflow_manifest


def load_manifest(manifest_path):
    """Load manifest from JSON or YAML file."""
    workflow, warnings = load_workflow_manifest(manifest_path)
    workflow["_normalization_warnings"] = warnings
    return workflow


CHECKS = []


def check_phase_exit_criteria(manifest):
    """No phase without exit criteria."""
    violations = []
    for phase in manifest.get("phases", []):
        if "id" not in phase or not str(phase["id"]).strip():
            violations.append({
                "rule": "phase-missing-id",
                "phase": "?",
                "message": "Phase has no canonical id field"
            })
        if "entry" not in phase or not str(phase["entry"]).strip():
            violations.append({
                "rule": "phase-missing-entry",
                "phase": phase.get("id", "?"),
                "message": f"Phase '{phase.get('id')}' has no entry criteria"
            })
        if "exit" not in phase or not str(phase["exit"]).strip():
            violations.append({
                "rule": "no-phase-without-exit",
                "phase": phase.get("id", "?"),
                "message": f"Phase '{phase.get('id')}' has no exit criteria"
            })
    return violations


def check_retry_limits(manifest):
    """No retry loop without max attempts."""
    violations = []
    for phase in manifest.get("phases", []):
        if "retryLimit" not in phase:
            violations.append({
                "rule": "no-retry-without-max",
                "phase": phase.get("id", "?"),
                "message": f"Phase '{phase.get('id')}' has no retryLimit"
            })
        elif int(phase["retryLimit"]) < 0:
            violations.append({
                "rule": "invalid-retry-limit",
                "phase": phase.get("id", "?"),
                "message": f"Phase '{phase.get('id')}' retryLimit must be >= 0"
            })
    return violations


def check_evidence_requirements(manifest):
    """No final answer without evidence."""
    violations = []
    evidence_req = manifest.get("evidence", {}).get("require", [])
    if not evidence_req:
        violations.append({
            "rule": "no-final-without-evidence",
            "message": "No evidence requirements defined"
        })
    return violations


def check_user_deferral(manifest):
    """No user-deferral during autonomous mode."""
    violations = []
    middleware = manifest.get("middleware", [])
    if "no_user_deferral_guard" not in middleware:
        violations.append({
            "rule": "no-user-deferral",
            "message": "Missing no_user_deferral_guard in middleware"
        })
    return violations


def check_middleware_hooks(manifest):
    """No middleware hook referencing missing interface."""
    violations = []
    # This would check against capability registry
    return violations


def check_reachable_phases(manifest):
    """No workflow phase that cannot be reached."""
    violations = []
    phases = manifest.get("phases", [])
    phase_ids = {p["id"] for p in phases}

    # Check for duplicate phase IDs
    seen_ids = set()
    for phase in phases:
        pid = phase.get("id", "?")
        if pid in seen_ids:
            violations.append({
                "rule": "duplicate-phase-id",
                "phase": pid,
                "message": f"Duplicate phase ID: '{pid}'"
            })
        seen_ids.add(pid)

    # Check handoff references
    for phase in phases:
        handoff = phase.get("handoff")
        if handoff and handoff not in phase_ids:
            violations.append({
                "rule": "no-unreachable-phase",
                "phase": phase["id"],
                "message": f"Handoff references unknown phase '{handoff}'"
            })
    return violations


def check_tool_availability(manifest):
    """No tool dependency that is unavailable."""
    violations = []
    tooling = manifest.get("tooling")
    if not isinstance(tooling, dict):
        return [{
            "rule": "missing-tooling-contract",
            "message": "Workflow has no tooling contract"
        }]

    required_fields = [
        "requiredTools",
        "entrypoint",
        "inputs",
        "outputs",
        "evidenceOutput",
        "failureSemantics",
    ]
    for field in required_fields:
        if field not in tooling or tooling.get(field) in ("", [], {}):
            violations.append({
                "rule": "tooling-contract-missing-field",
                "field": field,
                "message": f"Tooling contract missing required field '{field}'"
            })

    required_tools = tooling.get("requiredTools", [])
    if not isinstance(required_tools, list) or not required_tools:
        violations.append({
            "rule": "tooling-contract-no-required-tools",
            "message": "Tooling contract must name required tools"
        })
    else:
        for idx, tool in enumerate(required_tools):
            if not isinstance(tool, dict) or not tool.get("name") or not tool.get("purpose"):
                violations.append({
                    "rule": "tooling-contract-invalid-tool",
                    "tool": idx,
                    "message": "Each required tool must include name and purpose"
                })

    used_tools = {tool for phase in manifest.get("phases", []) for tool in phase.get("tools", [])}
    declared_tools = {tool.get("name") for tool in required_tools if isinstance(tool, dict)}
    missing = sorted(used_tools - declared_tools)
    for tool in missing:
        violations.append({
            "rule": "phase-tool-not-declared",
            "tool": tool,
            "message": f"Phase uses tool '{tool}' but tooling.requiredTools does not declare it"
        })

    failure_semantics = tooling.get("failureSemantics", {})
    for field in ["onSchemaError", "onToolError", "onValidationError"]:
        if not isinstance(failure_semantics, dict) or not failure_semantics.get(field):
            violations.append({
                "rule": "tooling-contract-missing-failure-semantics",
                "field": field,
                "message": f"Tooling contract missing failure semantics '{field}'"
            })

    return violations


def lint_workflow(manifest_path):
    """Run all lint checks."""
    manifest = load_manifest(manifest_path)

    all_violations = []
    for check_fn in [
        check_phase_exit_criteria,
        check_retry_limits,
        check_evidence_requirements,
        check_user_deferral,
        check_middleware_hooks,
        check_reachable_phases,
        check_tool_availability,
    ]:
        violations = check_fn(manifest)
        all_violations.extend(violations)

    return {
        "valid": len(all_violations) == 0,
        "violations": all_violations,
        "warnings": manifest.get("_normalization_warnings", []),
        "count": len(all_violations)
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: workflow-linter.py <manifest.json|manifest.yaml>")
        sys.exit(1)

    try:
        result = lint_workflow(sys.argv[1])
    except ImportError as e:
        print(json.dumps({"valid": False, "violations": [{"rule": "import-error", "message": str(e)}], "count": 1}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"valid": False, "violations": [{"rule": "parse-error", "message": str(e)}], "count": 1}))
        sys.exit(1)

    print(json.dumps(result, indent=2))
    sys.exit(0 if result["valid"] else 1)
