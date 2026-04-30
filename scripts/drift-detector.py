#!/usr/bin/env python3
"""VibeFlow Drift Detector - compares manifest intent vs simulated execution vs trace."""

import json
import sys
from pathlib import Path
from workflow_manifest import load_workflow_manifest

def detect_drift(manifest_path, simulation_path, trace_path=None, contract_path=None):
    """Detect drift between manifest intent, simulation, and actual traces."""
    manifest, warnings = load_workflow_manifest(manifest_path)
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
    contract = _load_contract(contract_path, manifest_path)
    if contract:
        _check_contract_surfaces(contract, manifest, drift_report)
        _check_contract_components(contract, manifest, drift_report)

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
    drift_report["normalization_warnings"] = warnings

    return drift_report


def _load_contract(contract_path, manifest_path):
    candidates = []
    if contract_path:
        candidates.append(Path(contract_path))
    manifest_dir = Path(manifest_path).resolve().parent
    candidates.extend([
        manifest_dir / "WORKFLOW_CONTRACT.json",
        manifest_dir.parent / "WORKFLOW_CONTRACT.json",
        Path.cwd() / "WORKFLOW_CONTRACT.json",
    ])
    for candidate in candidates:
        if candidate.exists():
            with candidate.open() as f:
                return json.load(f)
    return None


def _contract_values(contract, keys):
    values = []
    stack = [contract]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                if key in keys:
                    if isinstance(value, list):
                        values.extend(value)
                    else:
                        values.append(value)
                elif isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(item, list):
            stack.extend(item)
    return values


def _check_contract_surfaces(contract, manifest, drift_report):
    selected = _normalize_values(_contract_values(contract, {
        "selected_runtime_surfaces",
        "selectedRuntimeSurfaces",
        "runtime_surfaces",
        "runtimeSurfaces",
        "selected_surfaces",
        "selectedSurfaces",
    }))
    if not selected:
        return
    manifest_surfaces = set()
    if manifest.get("tooling", {}).get("requiredTools"):
        manifest_surfaces.add("tool")
    if manifest.get("middleware"):
        manifest_surfaces.add("middleware")
    if manifest.get("state"):
        manifest_surfaces.add("state")
        manifest_surfaces.add("session")
    if manifest.get("commands") or manifest.get("validation"):
        manifest_surfaces.add("config")
    if manifest.get("skills"):
        manifest_surfaces.add("skill")

    for surface in selected:
        canonical = _canonical_surface(surface)
        if canonical and canonical not in manifest_surfaces:
            drift_report["drifts"].append({
                "type": "contract_surface_missing",
                "surface": canonical,
                "expected": "present in manifest",
                "actual": "not present",
                "severity": "high"
            })


def _check_contract_components(contract, manifest, drift_report):
    selected = _normalize_values(_contract_values(contract, {
        "approved_components",
        "approvedComponents",
        "selected_components",
        "selectedComponents",
        "components",
    }))
    if not selected:
        return
    manifest_components = set(manifest.get("middleware", []))
    manifest_components.update(
        tool.get("name")
        for tool in manifest.get("tooling", {}).get("requiredTools", [])
        if isinstance(tool, dict) and tool.get("name")
    )
    for component in selected:
        if component and component not in manifest_components:
            drift_report["drifts"].append({
                "type": "contract_component_missing",
                "component": component,
                "expected": "present in manifest middleware or requiredTools",
                "actual": "not present",
                "severity": "medium"
            })


def _normalize_values(values):
    normalized = []
    for value in values:
        if isinstance(value, str):
            normalized.append(value)
        elif isinstance(value, dict):
            for key in ("name", "id", "surface", "type"):
                if isinstance(value.get(key), str):
                    normalized.append(value[key])
                    break
    return normalized


def _canonical_surface(surface):
    value = str(surface).strip().lower().replace("_", "-")
    aliases = {
        "tools": "tool",
        "tooling": "tool",
        "middleware-level": "middleware",
        "skills": "skill",
        "skill-only": "skill",
        "sessions": "session",
        "source-changes": "source",
    }
    value = aliases.get(value, value)
    return value if value in {"config", "skill", "tool", "middleware", "event", "session", "state", "source"} else None


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: drift-detector.py <manifest.json|manifest.yaml> <simulation.json> [trace.json] [WORKFLOW_CONTRACT.json]")
        sys.exit(1)

    result = detect_drift(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3] if len(sys.argv) > 3 else None,
        sys.argv[4] if len(sys.argv) > 4 else None,
    )
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["pass"] else 1)
