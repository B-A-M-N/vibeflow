#!/usr/bin/env python3
"""
VibeFlow Dry-Run Simulator
Simulates workflow execution with mocked tools.
"""

import json
import sys
from pathlib import Path

from workflow_manifest import load_workflow_manifest, write_json

try:
    from capability_registry import tool_available
except ImportError:  # pragma: no cover - direct script fallback for hyphenated filename
    import importlib.util

    _registry_path = Path(__file__).with_name("capability-registry.py")
    _spec = importlib.util.spec_from_file_location("capability_registry", _registry_path)
    capability_registry = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(capability_registry)
    tool_available = capability_registry.tool_available

class MockTool:
    """Mock tool that records calls without executing."""
    def __init__(self, name):
        self.name = name
        self.calls = []

    def call(self, fail=False, **kwargs):
        self.calls.append(kwargs)
        if fail:
            return {"status": "failed", "tool": self.name, "args": kwargs, "error": "simulated tool failure"}
        return {"status": "mocked", "tool": self.name, "args": kwargs}

def simulate_workflow(manifest_path, scenario="default"):
    """Simulate workflow execution."""
    workflow, warnings = load_workflow_manifest(manifest_path)
    tooling = workflow.get("tooling", {})

    timeline = []
    mock_tools = {t: MockTool(t) for t in _get_all_tools(workflow)}
    declared_tools = {
        t.get("name")
        for t in tooling.get("requiredTools", [])
        if isinstance(t, dict) and t.get("name")
    }
    violations = []
    retry_count = 0

    for phase in workflow.get("phases", []):
        phase_id = phase["id"]
        retry_limit = int(phase.get("retryLimit", 0))
        attempt = 0
        phase_passed = False

        while attempt <= retry_limit and not phase_passed:
            timeline.append({
                "phase": phase_id,
                "event": "enter",
                "entry": phase.get("entry"),
                "attempt": attempt + 1,
            })

            phase_errors = _phase_contract_errors(phase, declared_tools)
            force_tool_failure = _scenario_forces_tool_failure(scenario, phase_id, attempt)

            for error in phase_errors:
                timeline.append({
                    "phase": phase_id,
                    "event": "contract_error",
                    "error": error,
                    "attempt": attempt + 1,
                })

            for tool_name in phase.get("tools", []):
                if tool_name not in mock_tools:
                    continue
                result = mock_tools[tool_name].call(fail=force_tool_failure, scenario=scenario)
                event = "tool_error" if result["status"] == "failed" else "tool_call"
                timeline.append({
                    "phase": phase_id,
                    "event": event,
                    "tool": tool_name,
                    "args": {"scenario": scenario},
                    "attempt": attempt + 1,
                    **({"error": result.get("error")} if result.get("error") else {}),
                })
                if result["status"] == "failed":
                    phase_errors.append(f"Tool '{tool_name}' failed during dry run")

            gate_passed = not phase_errors and not _scenario_forces_gate_failure(scenario, phase_id)
            timeline.append({
                "phase": phase_id,
                "event": "gate_check",
                "result": "continue" if gate_passed else "block",
                "passed": gate_passed,
                "attempt": attempt + 1,
            })

            if gate_passed:
                timeline.append({
                    "phase": phase_id,
                    "event": "exit",
                    "exit": phase.get("exit"),
                    "attempt": attempt + 1,
                })
                phase_passed = True
            elif attempt < retry_limit:
                retry_count += 1
                timeline.append({
                    "phase": phase_id,
                    "event": "retry",
                    "reason": "; ".join(phase_errors) or "gate failed",
                    "attempt": attempt + 1,
                    "next_attempt": attempt + 2,
                })
            else:
                violations.extend({"phase": phase_id, "message": error} for error in (phase_errors or ["gate failed"]))

            attempt += 1

    gates = [entry for entry in timeline if entry.get("event") == "gate_check"]
    gates_passed = bool(gates) and all(gate.get("passed") for gate in gates) and not violations
    verdict = "READY" if gates_passed else "NEEDS_REWORK"
    _write_state_snapshot(workflow, timeline, gates, manifest_path)
    return {
        "workflow_id": workflow["name"],
        "workflow": workflow["name"],
        "scenario": scenario,
        "timeline": timeline,
        "phase_timeline": timeline,
        "tools_called": {k: len(v.calls) for k, v in mock_tools.items() if v.calls},
        "files_read": [],
        "files_changed": [],
        "commands_run": [],
        "tests_passed": [],
        "tests_failed": [],
        "tooling_contract": {
            "entrypoint": tooling.get("entrypoint"),
            "inputs": tooling.get("inputs", []),
            "outputs": tooling.get("outputs", []),
            "evidenceOutput": tooling.get("evidenceOutput"),
            "failureSemantics": tooling.get("failureSemantics", {}),
        },
        "gates": gates,
        "gates_passed": gates_passed,
        "retry_count": retry_count,
        "violations": violations,
        "verdict": verdict,
        "status": "completed" if gates_passed else "failed",
        "normalization_warnings": warnings,
    }

def _get_all_tools(workflow):
    tools = set()
    for phase in workflow.get("phases", []):
        tools.update(phase.get("tools", []))
    return list(tools)


def _phase_contract_errors(phase, declared_tools):
    errors = []
    if not phase.get("entry"):
        errors.append("Phase missing entry criteria")
    if not phase.get("exit"):
        errors.append("Phase missing exit criteria")
    for tool_name in phase.get("tools", []):
        if tool_name not in declared_tools:
            errors.append(f"Tool '{tool_name}' is used by phase but not declared in tooling.requiredTools")
        elif not tool_available(tool_name):
            errors.append(f"Tool '{tool_name}' is not available")
    return errors


def _scenario_forces_tool_failure(scenario, phase_id, attempt):
    parts = str(scenario).split(":")
    if parts[0] != "tool-failure":
        return False
    if len(parts) == 1:
        return attempt == 0
    return parts[1] == phase_id and attempt == 0


def _scenario_forces_gate_failure(scenario, phase_id):
    parts = str(scenario).split(":")
    if parts[0] != "gate-failure":
        return False
    return len(parts) == 1 or parts[1] == phase_id


def _write_state_snapshot(workflow, timeline, gates, manifest_path):
    state = workflow.get("state", {})
    state_path = state.get("path") if isinstance(state, dict) else None
    if not state_path:
        return
    state_path = _resolve_manifest_relative(manifest_path, state_path)
    retry_counts = {}
    for event in timeline:
        if event.get("event") == "retry":
            retry_counts[event["phase"]] = retry_counts.get(event["phase"], 0) + 1
    phase_entries = [event["phase"] for event in timeline if event.get("event") == "enter"]
    snapshot = {
        "currentPhase": phase_entries[-1] if phase_entries else None,
        "retryCounts": retry_counts,
        "evidence": {
            "manifest": str(manifest_path),
            "timelineEvents": len(timeline),
        },
        "gateDecisions": gates,
    }
    write_json(state_path, snapshot)


def _resolve_manifest_relative(manifest_path, path):
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(manifest_path).resolve().parent / candidate

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: dry-run-simulator.py <manifest.json|manifest.yaml> [scenario] [evidence_out]")
        sys.exit(1)

    manifest = sys.argv[1]
    scenario = sys.argv[2] if len(sys.argv) > 2 else "default"

    result = simulate_workflow(manifest, scenario)
    workflow, _warnings = load_workflow_manifest(manifest)
    evidence_out = sys.argv[3] if len(sys.argv) > 3 else workflow.get("tooling", {}).get("evidenceOutput", ".vibe-workflow/evidence/latest.json")
    evidence_out = _resolve_manifest_relative(manifest, evidence_out)
    result["evidence_path"] = write_json(evidence_out, result)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["verdict"] == "READY" else 1)
