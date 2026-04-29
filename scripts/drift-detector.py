#!/usr/bin/env python3
"""VibeFlow Drift Detector - compares manifest intent vs simulated execution vs trace."""

import json
import sys
from pathlib import Path

def detect_drift(manifest_path, simulation_path, trace_path=None):
    """Detect drift between manifest intent, simulation, and actual traces."""
    with open(manifest_path) as f:
        manifest = json.load(f)
    with open(simulation_path) as f:
        simulation = json.load(f)

    drift_report = {"drifts": [], "severity": "none"}

    # Build expected vs actual maps
    expected_phases = {p["id"]: p for p in manifest.get("phases", [])}
    simulated_phases = {}
    for entry in simulation.get("timeline", []):
        if entry.get("event") == "enter":
            phase_id = entry.get("phase")
            if phase_id not in simulated_phases:
                simulated_phases[phase_id] = {"entered": True, "tools": []}
        elif entry.get("event") == "tool_call":
            phase_id = entry.get("phase")
            if phase_id in simulated_phases:
                simulated_phases[phase_id]["tools"].append(entry.get("tool"))

    # Check 1: Phase skipped unexpectedly
    for phase_id in expected_phases:
        if phase_id not in simulated_phases:
            drift_report["drifts"].append({
                "type": "phase_skipped",
                "phase": phase_id,
                "expected": "entered",
                "actual": "not entered",
                "severity": "high"
            })

    # Check 2: Tool used outside policy
    tool_policy = manifest.get("tool_policy", {})
    for phase_id, sim_data in simulated_phases.items():
        phase_policy = tool_policy.get(phase_id, {})
        forbidden = phase_policy.get("forbidden", [])
        for tool in sim_data.get("tools", []):
            if tool in forbidden:
                drift_report["drifts"].append({
                    "type": "tool_outside_policy",
                    "phase": phase_id,
                    "tool": tool,
                    "policy": "forbidden",
                    "severity": "high"
                })

    # Check 3: Middleware not firing when expected
    if trace_path and Path(trace_path).exists():
        with open(trace_path) as f:
            trace_data = json.load(f)

        expected_middleware = set(manifest.get("middleware", []))
        fired_middleware = set()
        for entry in trace_data.get("trace", []):
            if entry.get("type") == "middleware":
                fired_middleware.add(entry.get("middleware"))

        missing = expected_middleware - fired_middleware
        for mw in missing:
            drift_report["drifts"].append({
                "type": "middleware_not_fired",
                "middleware": mw,
                "expected": "fired",
                "actual": "not fired",
                "severity": "medium"
            })

    # Check 4: State mutation outside contract
    # (Would need trace data with state_mutation events)

    # Determine severity
    severities = [d["severity"] for d in drift_report["drifts"]]
    if "high" in severities:
        drift_report["severity"] = "high"
    elif "medium" in severities:
        drift_report["severity"] = "medium"
    elif drift_report["drifts"]:
        drift_report["severity"] = "low"

    drift_report["drift_count"] = len(drift_report["drifts"])
    drift_report["pass"] = len(drift_report["drifts"]) == 0

    return drift_report


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: drift-detector.py <manifest.json> <simulation.json> [trace.json]")
        sys.exit(1)

    result = detect_drift(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["pass"] else 1)
