#!/usr/bin/env python3
"""
VibeFlow Dry-Run Simulator
Simulates workflow execution with mocked tools.
"""

import json
import sys
from pathlib import Path

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
    with open(manifest_path) as f:
        workflow = json.load(f)

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
        "workflow": workflow["name"],
        "scenario": scenario,
        "timeline": timeline,
        "tools_called": {k: len(v.calls) for k, v in mock_tools.items() if v.calls},
        "status": "completed"
    }

def _get_all_tools(workflow):
    tools = set()
    for phase in workflow.get("phases", []):
        tools.update(phase.get("tools", []))
    return list(tools)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: dry-run-simulator.py <manifest.json> [scenario]")
        sys.exit(1)

    manifest = sys.argv[1]
    scenario = sys.argv[2] if len(sys.argv) > 2 else "default"

    result = simulate_workflow(manifest, scenario)
    print(json.dumps(result, indent=2))
