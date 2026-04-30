#!/usr/bin/env python3
"""VibeFlow Gate Engine - validates workflow gates."""

import json
import sys

from workflow_manifest import load_workflow_manifest

def _sandbox_safe(workflow):
    sandbox = workflow.get("sandbox")
    return isinstance(sandbox, dict) and sandbox.get("isolation") in ["container", "tempdir"]


def _patch_minimal(workflow):
    patch = workflow.get("patch", {})
    if not patch:
        return True
    if not isinstance(patch, dict):
        return False
    forbidden = patch.get("forbiddenPaths", [])
    changed = patch.get("changedPaths", [])
    max_files = patch.get("maxFiles")
    if not isinstance(forbidden, list) or not isinstance(changed, list):
        return False
    if set(changed) & set(forbidden):
        return False
    if max_files is not None and len(changed) > int(max_files):
        return False
    return True


GATE_CHECKS = {
    "structure": lambda w: "phases" in w and len(w.get("phases", [])) > 0,
    "sandbox-safety": _sandbox_safe,
    "patch-minimality": _patch_minimal,
    "test-evidence": lambda w: "evidence" in w and "require" in w.get("evidence", {}),
    "no-user-deferral": lambda w: "no_user_deferral_guard" in w.get("middleware", []),
    "convergence": lambda w: all("retryLimit" in p and int(p.get("retryLimit")) >= 0 for p in w.get("phases", [])),
    "relevance": lambda w: "goal" in w and len(w.get("goal", "")) > 10,
}

def check_gates(manifest_path):
    workflow, warnings = load_workflow_manifest(manifest_path)

    results = {"pass": True, "gates": [], "warnings": warnings}

    for gate_id, check_fn in GATE_CHECKS.items():
        try:
            passed = check_fn(workflow)
            results["gates"].append({
                "id": gate_id,
                "passed": passed,
                "type": gate_id.split("-")[-1] if "-" in gate_id else gate_id
            })
            if not passed:
                results["pass"] = False
        except Exception as e:
            results["gates"].append({
                "id": gate_id,
                "passed": False,
                "error": str(e)
            })
            results["pass"] = False

    return results

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: gate-engine.py <manifest.json|manifest.yaml>")
        sys.exit(1)

    result = check_gates(sys.argv[1])
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["pass"] else 1)
