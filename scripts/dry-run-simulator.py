#!/usr/bin/env python3
"""
VibeFlow Dry-Run Simulator
Simulates workflow execution with mocked tools.
"""

import json
import sys
from pathlib import Path

from workflow_manifest import load_workflow_manifest, write_json

class MockTool:
    """Mock tool that records calls without executing."""
    def __init__(self, name):
        self.name = name
        self.calls = []

    def call(self, **kwargs):
        self.calls.append(kwargs)
        return {"status": "mocked", "tool": self.name, "args": kwargs}

def simulate_workflow(manifest_path, scenario="default"):
    """Simulate workflow execution."""
    workflow, warnings = load_workflow_manifest(manifest_path)
    tooling = workflow.get("tooling", {})

    timeline = []
    mock_tools = {t: MockTool(t) for t in _get_all_tools(workflow)}

    for phase in workflow.get("phases", []):
        phase_id = phase["id"]
        timeline.append({
            "phase": phase_id,
            "event": "enter",
            "entry": phase.get("entry")
        })

        # Mock tool calls for this phase
        for tool_name in phase.get("tools", []):
            if tool_name in mock_tools:
                mock_tools[tool_name].call(scenario=scenario)
                timeline.append({
                    "phase": phase_id,
                    "event": "tool_call",
                    "tool": tool_name,
                    "args": {"scenario": scenario}
                })

        timeline.append({
            "phase": phase_id,
            "event": "exit",
            "exit": phase.get("exit")
        })

        # Check gate
        timeline.append({
            "phase": phase_id,
            "event": "gate_check",
            "result": "continue"  # Mock always continues
        })

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
        "gates": [entry for entry in timeline if entry.get("event") == "gate_check"],
        "gates_passed": True,
        "retry_count": 0,
        "verdict": "READY",
        "status": "completed",
        "normalization_warnings": warnings,
    }

def _get_all_tools(workflow):
    tools = set()
    for phase in workflow.get("phases", []):
        tools.update(phase.get("tools", []))
    return list(tools)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: dry-run-simulator.py <manifest.json|manifest.yaml> [scenario] [evidence_out]")
        sys.exit(1)

    manifest = sys.argv[1]
    scenario = sys.argv[2] if len(sys.argv) > 2 else "default"

    result = simulate_workflow(manifest, scenario)
    workflow, _warnings = load_workflow_manifest(manifest)
    evidence_out = sys.argv[3] if len(sys.argv) > 3 else workflow.get("tooling", {}).get("evidenceOutput", ".vibe-workflow/evidence/latest.json")
    result["evidence_path"] = write_json(evidence_out, result)
    print(json.dumps(result, indent=2))
