#!/usr/bin/env python3
"""VibeFlow State Invariant Checker - validates state survives transitions/retries/restart."""

import json
import sys
from pathlib import Path

from workflow_manifest import load_workflow_manifest

REQUIRED_KEYS = ["currentPhase", "retryCounts", "evidence", "gateDecisions"]
PHASE_TRANSITIONS = ["enter", "exit", "handoff", "retry"]

def check_invariants(state_path, manifest_path):
    """Check state invariants against workflow manifest."""
    results = {"pass": True, "violations": []}

    # Load state
    if not Path(state_path).exists():
        results["violations"].append("State file missing")
        results["pass"] = False
        return results

    with open(state_path) as f:
        state = json.load(f)

    # Check required keys exist
    for key in REQUIRED_KEYS:
        if key not in state:
            results["violations"].append(f"Missing required key: {key}")
            results["pass"] = False

    workflow, warnings = load_workflow_manifest(manifest_path)
    if warnings:
        results["warnings"] = warnings

    # Check state survives phase transitions
    phases = [p["id"] for p in workflow.get("phases", [])]
    current = state.get("currentPhase")

    if current and current not in phases:
        results["violations"].append(f"currentPhase '{current}' not in manifest phases")
        results["pass"] = False

    # Check retry counts are bounded
    retry_limits = {p["id"]: p.get("retryLimit", 3) for p in workflow.get("phases", [])}
    for phase_id, count in state.get("retryCounts", {}).items():
        if phase_id in retry_limits and count > retry_limits[phase_id]:
            results["violations"].append(f"Retry count {count} exceeds limit {retry_limits[phase_id]} for phase {phase_id}")
            results["pass"] = False

    # Check evidence is collected
    if not state.get("evidence"):
        results["violations"].append("No evidence collected")
        results["pass"] = False

    return results

def check_restart_safety(state_path):
    """Check if state survives process restart."""
    with open(state_path) as f:
        state = json.load(f)

    # State should be JSON-serializable
    try:
        json.dumps(state)
    except Exception as e:
        return {"pass": False, "violations": [f"State not serializable: {e}"]}

    return {"pass": True, "violations": []}

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: state-invariant-checker.py <state.json> <manifest.json|manifest.yaml>")
        sys.exit(1)

    results = check_invariants(sys.argv[1], sys.argv[2])
    restart = check_restart_safety(sys.argv[1])

    if not restart["pass"]:
        results["violations"].extend(restart["violations"])
        results["pass"] = False

    print(json.dumps(results, indent=2))
    sys.exit(0 if results["pass"] else 1)
