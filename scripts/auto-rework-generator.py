#!/usr/bin/env python3
"""VibeFlow Auto-Rework Generator - generates corrections from failure output."""

import json
import sys
from copy import deepcopy

from workflow_manifest import load_workflow_manifest, write_json

def generate_rework(failure_data, gate_results, contract_results):
    """Generate manifest patches from failure/classification data."""
    patches = []

    # From failure classifier
    for failure in failure_data.get("failures", []):
        ftype = failure.get("type", "")
        rework = failure.get("rework", "")

        if ftype == "bad workflow topology":
            patches.append({
                "type": "add_missing_phase",
                "description": rework,
                "action": {"op": "add_phase", "phase": {"id": "fixme", "entry": "TBD", "exit": "TBD", "retryLimit": 3, "tools": []}}
            })

        elif ftype == "missing Vibe extension point":
            patches.append({
                "type": "update_source_map",
                "description": rework,
                "action": {"op": "regenerate_source_map"}
            })

        elif ftype == "loop has no convergence":
            patches.append({
                "type": "add_retry_limit",
                "description": rework,
                "action": {"op": "set_field", "path": "phases[*].retryLimit", "value": 3}
            })

        elif ftype == "tool unavailable":
            patches.append({
                "type": "remove_unavailable_tools",
                "description": rework,
                "action": {"op": "filter_tools", "remove_unavailable": True}
            })

        elif ftype == "state not persisted":
            patches.append({
                "type": "enable_persistence",
                "description": rework,
                "action": {"op": "set_field", "path": "state.persist", "value": True}
            })

    # From gate engine
    for gate in gate_results.get("gates", []):
        if not gate.get("passed"):
            gate_type = gate.get("type", "")
            if gate_type == "structure":
                patches.append({
                    "type": "fix_structure",
                    "description": "Fix manifest structure issues",
                    "action": {"op": "validate_schema"}
                })
            elif gate_type == "no-user-deferral":
                patches.append({
                    "type": "add_middleware",
                    "description": "Add no_user_deferral_guard middleware",
                    "action": {"op": "add_middleware", "middleware": "no_user_deferral_guard"}
                })
            elif gate_type == "convergence":
                patches.append({
                    "type": "fix_convergence",
                    "description": "Add retry limits to phases",
                    "action": {"op": "set_field", "path": "phases[*].retryLimit", "value": 3}
                })

    return patches


def apply_patches(manifest_path, patches):
    """Apply patches to manifest and write reworked version."""
    manifest, warnings = load_workflow_manifest(manifest_path)

    reworked = deepcopy(manifest)
    applied = []
    applied.extend(f"Normalized manifest: {warning}" for warning in warnings)

    for patch in patches:
        action = patch.get("action", {})
        op = action.get("op", "")

        try:
            if op == "add_middleware":
                middleware = reworked.get("middleware", [])
                if action["middleware"] not in middleware:
                    middleware.append(action["middleware"])
                    reworked["middleware"] = middleware
                    applied.append(f"Added middleware: {action['middleware']}")

            elif op == "set_field":
                path = action["path"].split(".")
                target = reworked
                for p in path[:-1]:
                    if p == "*" and isinstance(target, list):
                        for item in target:
                            item[path[-1]] = action["value"]
                    else:
                        target = target[p]
                target[path[-1]] = action["value"]
                applied.append(f"Set {action['path']} = {action['value']}")

        except Exception as e:
            applied.append(f"Failed to apply {op}: {e}")

    # Write reworked manifest
    output_path = _reworked_path(manifest_path)
    write_json(output_path, reworked)

    return {"reworked_path": output_path, "applied": applied}


def _reworked_path(manifest_path):
    if manifest_path.endswith((".yaml", ".yml")):
        return manifest_path.rsplit(".", 1)[0] + "-reworked.json"
    return manifest_path.replace(".json", "-reworked.json")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: auto-rework-generator.py <manifest.json|manifest.yaml> <failure.json> <gates.json> [contract.json]")
        sys.exit(1)

    with open(sys.argv[2]) as f:
        failures = json.load(f)
    with open(sys.argv[3]) as f:
        gates = json.load(f)

    contracts = {"tests": []}
    if len(sys.argv) > 4:
        with open(sys.argv[4]) as f:
            contracts = json.load(f)

    patches = generate_rework(failures, gates, contracts)
    result = apply_patches(sys.argv[1], patches)

    print(json.dumps({"patches_generated": len(patches), **result}, indent=2))
