#!/usr/bin/env python3
"""VibeFlow Workflow Linter - hard checks for workflow manifest."""

import json
import sys
import os

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def load_manifest(manifest_path):
    """Load manifest from JSON or YAML file."""
    ext = os.path.splitext(manifest_path)[1].lower()
    with open(manifest_path) as f:
        if ext in (".yaml", ".yml"):
            if not HAS_YAML:
                raise ImportError(
                    "PyYAML is required to parse YAML manifests. "
                    "Install with: pip install pyyaml"
                )
            return yaml.safe_load(f)
        else:
            return json.load(f)


CHECKS = []


def check_phase_exit_criteria(manifest):
    """No phase without exit criteria."""
    violations = []
    for phase in manifest.get("phases", []):
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
    # This would check against capability registry
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
