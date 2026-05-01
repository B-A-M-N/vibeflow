#!/usr/bin/env python3
"""VibeFlow Workflow Linter - hard checks for workflow manifest."""

import sys
import json

from workflow_manifest import load_workflow_manifest

try:
    from capability_registry import build_registry, tool_available
except ImportError:  # pragma: no cover - direct script fallback for hyphenated filename
    import importlib.util
    from pathlib import Path

    _registry_path = Path(__file__).with_name("capability-registry.py")
    _spec = importlib.util.spec_from_file_location("capability_registry", _registry_path)
    capability_registry = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(capability_registry)
    build_registry = capability_registry.build_registry
    tool_available = capability_registry.tool_available


def load_manifest(manifest_path):
    """Load manifest from JSON or YAML file."""
    workflow, warnings = load_workflow_manifest(manifest_path)
    workflow["_normalization_warnings"] = warnings
    return workflow


CHECKS = []


REQUIRED_TOP_LEVEL_SECTIONS = [
    "name",
    "goal",
    "phases",
    "tooling",
    "state",
    "middleware",
    "approval_gates",
    "evidence",
    "failure_policy",
    "commands",
    "validation",
]


def check_required_manifest_sections(manifest):
    """Require the complete executable workflow contract, not just phase prose."""
    violations = []
    for section in REQUIRED_TOP_LEVEL_SECTIONS:
        if section not in manifest:
            violations.append({
                "rule": "missing-manifest-section",
                "section": section,
                "message": f"Workflow manifest missing required top-level section '{section}'"
            })
    return violations


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


def check_approval_gates(manifest):
    """Lifecycle approval gates must be explicit."""
    violations = []
    gates = manifest.get("approval_gates")
    if not isinstance(gates, list):
        return [{
            "rule": "missing-approval-gates",
            "message": "Workflow must define approval_gates as a list"
        }]
    for idx, gate in enumerate(gates):
        if not isinstance(gate, dict) or not gate.get("id") or not gate.get("type") or not gate.get("requires"):
            violations.append({
                "rule": "invalid-approval-gate",
                "gate": idx,
                "message": "Each approval gate must include id, type, and requires"
            })
    return violations


def check_failure_policy(manifest):
    """Failure handling must distinguish tooling defects from workflow defects."""
    violations = []
    policy = manifest.get("failure_policy")
    if not isinstance(policy, dict):
        return [{
            "rule": "missing-failure-policy",
            "message": "Workflow must define failure_policy"
        }]
    classifications = policy.get("classification", [])
    required = {"plugin_tooling", "generated_workflow", "user_spec", "environment", "external_dependency"}
    if not isinstance(classifications, list) or not required.issubset(set(classifications)):
        violations.append({
            "rule": "incomplete-failure-classification",
            "message": "failure_policy.classification must include plugin_tooling, generated_workflow, user_spec, environment, and external_dependency"
        })
    if not policy.get("onFailure"):
        violations.append({
            "rule": "missing-failure-action",
            "message": "failure_policy.onFailure must define the safe next action"
        })
    return violations


def check_commands_contract(manifest):
    """Runnable command contract must name deterministic validation commands."""
    violations = []
    commands = manifest.get("commands")
    if not isinstance(commands, dict):
        return [{
            "rule": "missing-commands-contract",
            "message": "Workflow must define commands"
        }]
    for field in ["lint", "dryRun", "validate"]:
        if not commands.get(field):
            violations.append({
                "rule": "commands-contract-missing-field",
                "field": field,
                "message": f"commands.{field} is required"
            })
    return violations


def check_validation_contract(manifest):
    """Validation must be serial, evidence-bearing, and non-mutating."""
    violations = []
    validation = manifest.get("validation")
    if not isinstance(validation, dict):
        return [{
            "rule": "missing-validation-contract",
            "message": "Workflow must define validation"
        }]
    expected = {
        "serial": True,
        "evidenceRequired": True,
        "mutatesWorkflow": False,
    }
    for field, expected_value in expected.items():
        if validation.get(field) is not expected_value:
            violations.append({
                "rule": "invalid-validation-contract",
                "field": field,
                "message": f"validation.{field} must be {expected_value}"
            })
    return violations


def check_middleware_hooks(manifest):
    """No middleware hook referencing missing interface."""
    violations = []
    registry = build_registry()
    known_middleware = registry.get("middleware", {})
    allowed_hooks = {"before_turn"}

    middleware_entries = manifest.get("middleware", [])
    if not isinstance(middleware_entries, list):
        return [{
            "rule": "invalid-middleware-contract",
            "message": "Workflow middleware must be a list"
        }]

    for idx, entry in enumerate(middleware_entries):
        if isinstance(entry, str):
            name = entry
            hooks = known_middleware.get(name, {}).get("hooks", ["before_turn"])
        elif isinstance(entry, dict):
            name = entry.get("name")
            hooks = entry.get("hooks", [])
        else:
            violations.append({
                "rule": "invalid-middleware-contract",
                "middleware": idx,
                "message": "Middleware entries must be names or objects with name/hooks"
            })
            continue

        if not name:
            violations.append({
                "rule": "middleware-missing-name",
                "middleware": idx,
                "message": "Middleware entry missing name"
            })
            continue

        custom_examples = registry.get("custom_middleware_examples", {})
        if name not in known_middleware:
            if name in custom_examples:
                violations.append({
                    "rule": "middleware-requires-source-registration",
                    "middleware": name,
                    "severity": "warning",
                    "message": (
                        f"Middleware '{name}' is a Tier D custom middleware. "
                        "Ensure it is registered in _setup_middleware() in AgentLoop source."
                    ),
                })
            else:
                violations.append({
                    "rule": "middleware-unrecognized",
                    "middleware": name,
                    "severity": "warning",
                    "message": (
                        f"Middleware '{name}' is not in the capability registry. "
                        "If this is custom middleware, ensure it is registered via _setup_middleware()."
                    ),
                })
            # Fall through — still validate hooks even for custom/unrecognized middleware.

        if not isinstance(hooks, list) or not hooks:
            violations.append({
                "rule": "middleware-missing-hook",
                "middleware": name,
                "message": f"Middleware '{name}' must declare hook(s)"
            })
            continue

        invalid_hooks = sorted(set(hooks) - allowed_hooks)
        if invalid_hooks:
            violations.append({
                "rule": "middleware-invalid-hook",
                "middleware": name,
                "hooks": invalid_hooks,
                "message": f"Middleware '{name}' declares unsupported hook(s): {', '.join(invalid_hooks)}"
            })
    return violations


def check_reachable_phases(manifest):
    """No workflow phase that cannot be reached."""
    violations = []
    phases = manifest.get("phases", [])
    phase_ids = {p.get("id") for p in phases if isinstance(p, dict) and p.get("id")}

    # Check for duplicate phase IDs
    seen_ids = set()
    for phase in phases:
        if not isinstance(phase, dict):
            continue
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
        if not isinstance(phase, dict):
            continue
        handoff = phase.get("handoff")
        if handoff and handoff not in phase_ids:
            violations.append({
                "rule": "no-unreachable-phase",
                "phase": phase.get("id", "?"),
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
            elif not tool_available(tool.get("name")):
                violations.append({
                    "rule": "tool-unavailable",
                    "tool": tool.get("name"),
                    "message": f"Tool '{tool.get('name')}' is not available in the capability registry"
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
    all_warnings: list = []
    for check_fn in [
        check_required_manifest_sections,
        check_phase_exit_criteria,
        check_retry_limits,
        check_evidence_requirements,
        check_user_deferral,
        check_approval_gates,
        check_failure_policy,
        check_commands_contract,
        check_validation_contract,
        check_middleware_hooks,
        check_reachable_phases,
        check_tool_availability,
    ]:
        for v in check_fn(manifest):
            if isinstance(v, dict) and v.get("severity") == "warning":
                all_warnings.append(v)
            else:
                all_violations.append(v)

    return {
        "valid": len(all_violations) == 0,
        "violations": all_violations,
        "warnings": manifest.get("_normalization_warnings", []) + [
            w["message"] if isinstance(w, dict) else w for w in all_warnings
        ],
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
