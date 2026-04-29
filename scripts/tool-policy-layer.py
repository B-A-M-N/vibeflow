#!/usr/bin/env python3
"""VibeFlow Tool-Call Policy Layer - defines allowed/forbidden tools per phase."""

import json
import sys

DEFAULT_POLICY = {
    "discover": {
        "allowed": ["github_search", "repo_inspect", "read_files", "grep"],
        "forbidden": ["edit_files", "write_file"],
        "sandbox_only": []
    },
    "diagnose": {
        "allowed": ["read_files", "grep", "test_runner"],
        "forbidden": ["edit_files"],
        "sandbox_only": []
    },
    "patch": {
        "allowed": ["edit_files", "write_file"],
        "forbidden": ["github_search"],
        "sandbox_only": ["edit_files"]
    },
    "validate": {
        "allowed": ["test_runner", "typecheck", "lint"],
        "forbidden": ["edit_files"],
        "sandbox_only": []
    }
}

def check_policy(manifest_path, phase_id, tool_name):
    """Check if tool is allowed in phase per policy."""
    with open(manifest_path) as f:
        workflow = json.load(f)

    # Get policy from manifest or use default
    policies = workflow.get("tool_policy", DEFAULT_POLICY)
    phase_policy = policies.get(phase_id, {})

    allowed = phase_policy.get("allowed", [])
    forbidden = phase_policy.get("forbidden", [])
    sandbox_only = phase_policy.get("sandbox_only", [])

    if tool_name in forbidden:
        return {"allowed": False, "reason": f"Tool '{tool_name}' forbidden in phase '{phase_id}'"}

    if allowed and tool_name not in allowed:
        return {"allowed": False, "reason": f"Tool '{tool_name}' not in allowed list for phase '{phase_id}'"}

    if tool_name in sandbox_only:
        return {"allowed": True, "sandbox_required": True}

    return {"allowed": True, "sandbox_required": False}

def validate_manifest_policies(manifest_path):
    """Validate all tool calls in manifest against policies."""
    with open(manifest_path) as f:
        workflow = json.load(f)

    violations = []
    policies = workflow.get("tool_policy", DEFAULT_POLICY)

    for phase in workflow.get("phases", []):
        phase_id = phase["id"]
        for tool in phase.get("tools", []):
            result = check_policy(manifest_path, phase_id, tool)
            if not result["allowed"]:
                violations.append({
                    "phase": phase_id,
                    "tool": tool,
                    "reason": result["reason"]
                })

    return {"pass": len(violations) == 0, "violations": violations}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: tool-policy-layer.py <manifest.json> [phase tool]")
        sys.exit(1)

    if len(sys.argv) >= 4:
        result = check_policy(sys.argv[1], sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2))
    else:
        result = validate_manifest_policies(sys.argv[1])
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["pass"] else 1)
